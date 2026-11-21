"""CLEAN split: the brief's official shuffle/IDs/80-20 boundary, then sanitize + de-duplicate.

What this does on top of the official split (see CLEANING.md for the numbers):
  * Text: literal "\\n" and <br> -> real newlines, NFKC, whitespace collapse,
    "[Your Name]" / "[Ihr Name]" / ... -> "<name>" (same token the dataset already uses).
  * Labels: priority 5 -> 3 (critical->high, very_low->low; original kept in `priority_raw`),
    `queue_core` = queue is one of the 10 queues used by typed rows, cleaned `tags` list.
  * kb_train: exact duplicate bodies collapsed to one row (labels by majority vote, first answer),
    `n_copies` / `dup_ticket_ids` keep the provenance. Empty bodies dropped.
  * dev (15% of the de-duplicated 80%): dev rows with a near-copy in base (char TF-IDF cos >= 0.90)
    are moved back to base, so calibration/thresholds are tuned on genuinely unseen tickets.
  * test: rows that copy kb (exact or near, cos >= 0.90) or copy an earlier test row are removed
    from the clean test set. They are still kept in *_all files with an `eval_subset` tag so the
    full official 20% can also be reported. Only test INPUTS are compared; labels are never read.

Outputs in ./data/:
  kb_train.parquet          de-duplicated 80%: `split` in {base, dev}, `has_answer` for indexing
  test_inputs.parquet       CLEAN test inputs (ticket_id, subject, body, text)
  test_labels.parquet       CLEAN test labels: eval.py ONLY
  test_inputs_all.parquet   all official test inputs + eval_subset + max_sim_kb_tfidf
  test_labels_all.parquet   all official test labels: eval.py ONLY
  split_meta.json
"""
import argparse
import json
import os
import re
import time
import unicodedata

import numpy as np
import pandas as pd
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer

PRIORITY_MAP = {"critical": "high", "high": "high", "medium": "medium", "low": "low", "very_low": "low"}
NAME_PLACEHOLDER = r"\[\s*(?:your|ihr|ihre|dein|deine)?\s*name\s*\]"
LABEL_COLS = ["type", "queue", "queue_core", "priority", "priority_raw", "language"]
TAG_COLS = [f"tag_{i}" for i in range(1, 9)]


def clean_text(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str).map(lambda x: unicodedata.normalize("NFKC", x))
    s = s.str.replace(r"\\r\\n|\\n|\\r", "\n", regex=True)  # literal backslash-n sequences
    s = s.str.replace(r"<br\s*/?>", "\n", regex=True, case=False)
    s = s.str.replace(NAME_PLACEHOLDER, "<name>", regex=True, case=False)
    s = s.str.replace(r"[ \t ]+", " ", regex=True)
    s = s.str.replace(r" *\n *", "\n", regex=True)
    s = s.str.replace(r"\n{3,}", "\n\n", regex=True)
    return s.str.strip()


def dedup_key(s: pd.Series) -> pd.Series:
    """Body identity: case, punctuation and whitespace insensitive."""
    return s.str.lower().str.replace(r"[^\w<>]+", " ", regex=True).str.strip()


def build_text(df: pd.DataFrame) -> pd.Series:
    return (df["subject"].fillna("") + "\n\n" + df["body"]).str.strip()


def clean_tags(row) -> list:
    seen, out = set(), []
    for t in row:
        if isinstance(t, str) and t.strip():
            k = t.strip().lower()
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


def mode_first(s: pd.Series):
    s = s.dropna()
    if s.empty:
        return None
    counts = s.value_counts()
    return s[s.map(counts) == counts.max()].iloc[0]  # tie -> earliest ticket_id


def first_nonnull(s: pd.Series):
    s = s.dropna()
    return s.iloc[0] if len(s) else None


def max_sim(vec, a_text, b_text, chunk: int = 500) -> np.ndarray:
    A, B = vec.transform(a_text), vec.transform(b_text)
    out = np.zeros(A.shape[0], dtype=np.float32)
    for s in range(0, A.shape[0], chunk):
        out[s : s + chunk] = (A[s : s + chunk] @ B.T).max(axis=1).toarray().ravel()
    return out


def audit(df: pd.DataFrame, name: str) -> None:
    print(f"\n=== {name}: {len(df):,} rows ===")
    for c in ["type", "priority", "language"]:
        if c in df:
            print(f"{c}: {df[c].value_counts(dropna=False).to_dict()}")
    if "queue" in df:
        print(f"queue: {df['queue'].nunique(dropna=True)} distinct")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--dev-frac", type=float, default=0.15)
    ap.add_argument("--dev-seed", type=int, default=7)
    ap.add_argument("--near", type=float, default=0.90, help="char TF-IDF cosine for a near-copy")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    # ---- The brief's official split (unchanged): same shuffle, same ticket_ids, same boundary. ----
    ds = load_dataset("Tobi-Bueck/customer-support-tickets")
    df = ds["train"].to_pandas()
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    split_idx = int(len(df) * 0.8)
    # ----------------------------------------------------------------------------------------------
    df["official_split"] = np.where(np.arange(len(df)) < split_idx, "kb", "test")
    n_raw = len(df)

    # ---- Sanitize ----
    for c in ["subject", "body", "answer"]:
        df[c] = clean_text(df[c])
    for c in ["subject", "answer"]:
        df[c] = df[c].replace("", None)
    df["priority_raw"] = df["priority"]
    df["priority"] = df["priority"].map(PRIORITY_MAP)
    df["tags"] = df[TAG_COLS].apply(clean_tags, axis=1)
    for c in TAG_COLS:
        df[c] = df[c].where(df[c].isna(), df[c].astype(str).str.strip().str.lower())
    is_kb = df["official_split"] == "kb"
    core_queues = sorted(df.loc[is_kb & df["type"].notna(), "queue"].unique())  # from the 80% only
    df["queue_core"] = df["queue"].isin(core_queues)
    df["text"] = build_text(df)
    df["key"] = dedup_key(df["body"])
    df["short_body"] = df["body"].str.len() < 20

    kb = df[is_kb].copy()
    test = df[~is_kb].copy()

    # ---- kb: drop empty bodies, collapse exact duplicates ----
    n_kb_empty = int((kb["key"] == "").sum())
    kb = kb[kb["key"] != ""]
    dup = kb[kb["key"].duplicated(keep=False)]
    vote_cols = ["type", "queue", "priority", "priority_raw"]
    agg = dup.groupby("key").agg(
        n_copies=("ticket_id", "size"),
        dup_ticket_ids=("ticket_id", lambda x: list(x)[1:]),
        answer=("answer", first_nonnull),
        **{c: (c, mode_first) for c in vote_cols},
    )
    agg["label_conflict"] = dup.groupby("key")[["type", "queue", "priority"]].nunique().gt(1).any(axis=1)
    kb = kb.drop_duplicates("key", keep="first").set_index("key")
    kb["n_copies"], kb["dup_ticket_ids"], kb["label_conflict"] = 1, [[] for _ in range(len(kb))], False
    for c in ["n_copies", "dup_ticket_ids", "answer", "label_conflict"] + vote_cols:
        kb.loc[agg.index, c] = agg[c]
    kb["queue_core"] = kb["queue"].isin(core_queues)
    kb = kb.reset_index().sort_values("ticket_id").reset_index(drop=True)
    kb["n_copies"] = kb["n_copies"].astype(int)
    kb["label_conflict"] = kb["label_conflict"].astype(bool)
    kb["has_answer"] = kb["answer"].notna()

    # ---- Near-copy detector, fit on kb text only ----
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True, dtype=np.float32)
    vec.fit(kb["key"])

    # ---- test: tag exact / near / internal copies (inputs only) ----
    kb_keys = set(kb["key"])
    test["eval_subset"] = "clean"
    test.loc[test["key"] == "", "eval_subset"] = "empty_body"
    test.loc[(test["eval_subset"] == "clean") & test["key"].isin(kb_keys), "eval_subset"] = "exact_kb_twin"
    test.loc[(test["eval_subset"] == "clean") & test["key"].duplicated(keep="first"), "eval_subset"] = "test_internal_dup"
    test["max_sim_kb_tfidf"] = np.float32(np.nan)
    m = test["eval_subset"] == "clean"
    print(f"near-copy check: {m.sum():,} test rows vs {len(kb):,} kb rows ...", flush=True)
    test.loc[m, "max_sim_kb_tfidf"] = max_sim(vec, test.loc[m, "key"], kb["key"])
    test.loc[m & (test["max_sim_kb_tfidf"] >= args.near), "eval_subset"] = "near_kb_twin"
    test.loc[test["eval_subset"] == "exact_kb_twin", "max_sim_kb_tfidf"] = 1.0

    # ---- dev slice from the de-duplicated 80%; near-copies of base go back to base ----
    dev_ids = set(kb.sample(frac=args.dev_frac, random_state=args.dev_seed)["ticket_id"])
    kb["split"] = np.where(kb["ticket_id"].isin(dev_ids), "dev", "base")
    d = kb["split"] == "dev"
    print(f"near-copy check: {d.sum():,} dev rows vs {(~d).sum():,} base rows ...", flush=True)
    dev_sim = max_sim(vec, kb.loc[d, "key"], kb.loc[~d, "key"])
    kb["max_sim_base_tfidf"] = np.float32(np.nan)
    kb.loc[d, "max_sim_base_tfidf"] = dev_sim
    n_dev_moved = int((dev_sim >= args.near).sum())
    kb.loc[d & (kb["max_sim_base_tfidf"] >= args.near), "split"] = "base"

    # ---- Leak guards ----
    kb_num = kb["ticket_id"].str[4:].astype(int)
    te_num = test["ticket_id"].str[4:].astype(int)
    assert kb_num.max() < split_idx <= te_num.min(), "split boundary violated"
    assert set(kb["ticket_id"]).isdisjoint(test["ticket_id"]), "ticket_id overlap"
    clean = test[test["eval_subset"] == "clean"]
    assert not clean["key"].isin(kb_keys).any(), "clean test still has exact kb twins"
    assert (clean["max_sim_kb_tfidf"] < args.near).all(), "clean test still has near kb twins"
    assert clean["key"].is_unique, "clean test has internal duplicates"
    dv = kb[kb["split"] == "dev"]
    assert not dv["key"].isin(set(kb.loc[kb["split"] == "base", "key"])).any(), "dev/base exact overlap"
    assert (dv["max_sim_base_tfidf"] < args.near).all(), "dev/base near overlap"

    # ---- Write ----
    kb_cols = ["ticket_id", "subject", "body", "answer", "text", "type", "queue", "queue_core", "priority",
               "priority_raw", "language", "version", "tags"] + TAG_COLS + [
               "split", "has_answer", "n_copies", "dup_ticket_ids", "label_conflict", "short_body",
               "max_sim_base_tfidf"]
    kb[kb_cols].to_parquet(f"{args.out}/kb_train.parquet", index=False)
    in_cols = ["ticket_id", "subject", "body", "text"]
    clean[in_cols].to_parquet(f"{args.out}/test_inputs.parquet", index=False)
    clean[["ticket_id"] + LABEL_COLS].to_parquet(f"{args.out}/test_labels.parquet", index=False)
    test[in_cols + ["eval_subset", "max_sim_kb_tfidf", "short_body"]].to_parquet(
        f"{args.out}/test_inputs_all.parquet", index=False)
    test[["ticket_id"] + LABEL_COLS].to_parquet(f"{args.out}/test_labels_all.parquet", index=False)

    audit(kb, "kb_train (clean, de-duplicated)")
    audit(clean, "test (clean)")
    meta = {
        "n_rows_raw": n_raw,
        "split_idx": split_idx,
        "shuffle_seed": 42,
        "dev_frac": args.dev_frac,
        "dev_seed": args.dev_seed,
        "near_copy_threshold_char_tfidf": args.near,
        "kb_raw": int(is_kb.sum()),
        "kb_empty_body_dropped": n_kb_empty,
        "kb_exact_dups_collapsed": int(is_kb.sum()) - n_kb_empty - len(kb),
        "kb_clean": len(kb),
        "kb_label_conflict_groups": int(kb["label_conflict"].sum()),
        "n_base": int((kb["split"] == "base").sum()),
        "n_dev": int((kb["split"] == "dev").sum()),
        "dev_moved_to_base_near_copy": n_dev_moved,
        "n_kb_with_answer": int(kb["has_answer"].sum()),
        "test_raw": len(test),
        "test_eval_subset": test["eval_subset"].value_counts().to_dict(),
        "n_test_clean": len(clean),
        "core_queues": core_queues,
        "seconds": round(time.time() - t0),
    }
    with open(f"{args.out}/split_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("\n" + json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
