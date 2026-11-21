"""Lock the official 80/20 split (the brief's exact code) and carve a dev slice out of the 80%.

Run in Cloud Shell (or any laptop). Outputs go to ./data/:
  kb_train.parquet     the 80% split: all columns + `split` in {base, dev} + `text`
  test_inputs.parquet  the 20% split, INPUTS ONLY (ticket_id, subject, body, text): safe for inference/eval
  test_labels.parquet  the 20% split labels: for eval.py ONLY. Never load this in training/indexing code.
  split_meta.json      sizes and seeds, for the README

Validation comes from inside the 80% (the `dev` rows), never from the 20%.
"""
import argparse
import json
import os

import pandas as pd
from datasets import load_dataset

LABEL_COLS = ["type", "queue", "priority", "language"]


def build_text(df: pd.DataFrame) -> pd.Series:
    """subject (may be null/empty) + body -> one string. Never crashes on missing subjects."""
    subj = df["subject"].fillna("").astype(str).str.strip()
    body = df["body"].fillna("").astype(str).str.strip()
    return (subj + "\n\n" + body).str.strip()


def norm_body(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()


def audit(df: pd.DataFrame, name: str) -> None:
    print(f"\n=== {name}: {len(df):,} rows ===")
    for c in ["type", "priority", "language"]:
        print(f"\n{c}:\n{df[c].value_counts(dropna=False).to_string()}")
    print(f"\nqueue: {df['queue'].nunique(dropna=True)} distinct, null={df['queue'].isna().sum():,}")
    print(f"subject null/empty: {(df['subject'].fillna('').astype(str).str.strip() == '').sum():,}")
    print(f"answer null: {df['answer'].isna().sum():,}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--dev-frac", type=float, default=0.15, help="fraction of the 80%% held out as dev")
    ap.add_argument("--dev-seed", type=int, default=7)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    # ---- The brief's official split. Do not change these lines. ----
    ds = load_dataset("Tobi-Bueck/customer-support-tickets")
    df = ds["train"].to_pandas()
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    split_idx = int(len(df) * 0.8)
    kb = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()
    # -----------------------------------------------------------------

    audit(df, "FULL DATASET (check against the label policy)")

    kb["text"] = build_text(kb)
    test["text"] = build_text(test)

    # Dev slice from the 80%: used for early stopping, calibration, and every threshold.
    dev_ids = set(kb.sample(frac=args.dev_frac, random_state=args.dev_seed)["ticket_id"])
    kb["split"] = "base"
    kb.loc[kb["ticket_id"].isin(dev_ids), "split"] = "dev"

    # Leak guards.
    kb_num = kb["ticket_id"].str[4:].astype(int)
    te_num = test["ticket_id"].str[4:].astype(int)
    assert kb_num.max() < split_idx <= te_num.min(), "split boundary violated"
    assert set(kb["ticket_id"]).isdisjoint(test["ticket_id"]), "ticket_id overlap"

    # Twin report (exact duplicates only; near-duplicates are checked after embedding in merge.py).
    n_exact = norm_body(test["body"]).isin(set(norm_body(kb["body"]))).sum()
    print(f"\nTest bodies that exactly match a kb_train body: {n_exact:,} / {len(test):,}")

    kb.to_parquet(f"{args.out}/kb_train.parquet", index=False)
    test[["ticket_id", "subject", "body", "text"]].to_parquet(f"{args.out}/test_inputs.parquet", index=False)
    test[["ticket_id"] + LABEL_COLS].to_parquet(f"{args.out}/test_labels.parquet", index=False)

    meta = {
        "n_rows": len(df),
        "split_idx": split_idx,
        "shuffle_seed": 42,
        "dev_frac": args.dev_frac,
        "dev_seed": args.dev_seed,
        "n_base": int((kb["split"] == "base").sum()),
        "n_dev": int((kb["split"] == "dev").sum()),
        "n_test": len(test),
        "n_kb_with_answer": int(kb["answer"].notna().sum()),
        "test_exact_body_twins": int(n_exact),
    }
    with open(f"{args.out}/split_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print("\n" + json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
