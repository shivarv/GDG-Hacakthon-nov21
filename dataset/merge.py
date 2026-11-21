"""Merge embedding shards into separate kb / test files and run a near-duplicate (twin) check.

Run in Cloud Shell after the embed job, on locally copied shards. Outputs in --out:
  kb_emb.npy + kb_ids.parquet      the ONLY files the FAISS index / classifiers should load for training
  test_emb.npy + test_ids.parquet  ALL official test rows (eval_subset says which are clean); eval.py only
  twin_report.parquet              per test ticket: max cosine similarity to any kb_train ticket
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd


def max_sim(a: np.ndarray, b: np.ndarray, chunk: int = 512) -> np.ndarray:
    out = np.empty(len(a), dtype=np.float32)
    for s in range(0, len(a), chunk):
        out[s : s + chunk] = (a[s : s + chunk] @ b.T).max(axis=1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", default="emb_shards")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="emb")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    files = sorted(glob.glob(os.path.join(args.shards, "shard_*.npy")))
    assert files, f"no shards found in {args.shards}"
    embs = [np.load(f) for f in files]
    ids = [pd.read_parquet(f[: -len(".npy")] + "_ids.parquet") for f in files]
    E = np.concatenate(embs)
    I = pd.concat(ids, ignore_index=True)
    assert len(E) == len(I), "shard/id length mismatch"

    order = np.argsort(I["ticket_id"].to_numpy())
    E, I = E[order], I.iloc[order].reset_index(drop=True)
    assert I["ticket_id"].is_unique, "duplicate ticket_ids across shards"

    kb_meta = pd.read_parquet(f"{args.data}/kb_train.parquet", columns=["ticket_id", "split", "has_answer"])
    te_meta = pd.read_parquet(f"{args.data}/test_inputs_all.parquet", columns=["ticket_id", "eval_subset"])
    kb_ids, te_ids = set(kb_meta["ticket_id"]), set(te_meta["ticket_id"])
    assert len(I) == len(kb_ids) + len(te_ids), (
        f"expected {len(kb_ids) + len(te_ids):,} rows, got {len(I):,} (a task probably failed)"
    )

    norms = np.linalg.norm(E, axis=1)
    print(f"{len(files)} shards, {E.shape}, norm min/max {norms.min():.3f}/{norms.max():.3f}")

    is_kb = I["ticket_id"].isin(kb_ids).to_numpy()
    kb_E, te_E = E[is_kb], E[~is_kb]
    np.save(f"{args.out}/kb_emb.npy", kb_E)
    # kb_ids carries split/has_answer so the index can drop dev rows while tuning and keep answer-bearing rows.
    I[is_kb].merge(kb_meta, on="ticket_id", how="left").to_parquet(f"{args.out}/kb_ids.parquet", index=False)
    np.save(f"{args.out}/test_emb.npy", te_E)
    I[~is_kb].merge(te_meta, on="ticket_id", how="left").to_parquet(f"{args.out}/test_ids.parquet", index=False)
    print(f"kb: {kb_E.shape}  test: {te_E.shape}")

    sims = max_sim(te_E, kb_E)
    report = pd.DataFrame({"ticket_id": I[~is_kb]["ticket_id"].to_numpy(), "max_sim_to_kb": sims})
    report = report.merge(te_meta, on="ticket_id", how="left")
    report.to_parquet(f"{args.out}/twin_report.parquet", index=False)
    clean = report["eval_subset"] == "clean"
    for t in (0.95, 0.98, 0.995):
        print(f"e5 cos >= {t}: all test {(sims >= t).sum():,} / {len(sims):,}   "
              f"clean test {(report.loc[clean, 'max_sim_to_kb'] >= t).sum():,} / {clean.sum():,}")


if __name__ == "__main__":
    main()
