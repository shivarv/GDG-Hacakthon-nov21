"""Tune gate thresholds using ONLY the 80% KB split (the holdout is never read).

A temporary classifier is trained on 80% of the KB; the other 20% of the KB is the validation slice.
Validation tickets look up precedents among the 80% fit part only, reusing vectors already in the index.

Usage:  python scripts/tune_gate.py [--target-recall 0.95]
Writes: artifacts/gate_thresholds.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentineldesk.classifier import TriageClassifier  # noqa: E402
from sentineldesk.config import SETTINGS  # noqa: E402
from sentineldesk.data import TARGETS  # noqa: E402
from sentineldesk.gate import HIGH_PRIORITY, risk_score  # noqa: E402
from sentineldesk.retriever import Retriever  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-recall", type=float, default=0.95)
    ap.add_argument("--sim-percentile", type=float, default=5.0)
    args = ap.parse_args()

    art = Path(SETTINGS.artifacts_dir)
    kb = pd.read_parquet(art / "kb_train.parquet")
    r = Retriever.load(art / "index", encoder=None)
    assert list(r.meta["ticket_id"]) == list(kb["ticket_id"]), "index/KB order mismatch"
    vecs = r.index.reconstruct_n(0, r.index.ntotal) if r.index is not None else r.vectors

    rng = np.random.RandomState(SETTINGS.seed + 1)
    perm = rng.permutation(len(kb))
    n_val = len(kb) // 5
    val_i, fit_i = np.sort(perm[:n_val]), np.sort(perm[n_val:])
    fit, val = kb.iloc[fit_i], kb.iloc[val_i]
    print(f"fit {len(fit):,} / validation {len(val):,} (both from the KB split)")

    clf = TriageClassifier().fit(fit["text"].tolist(), {t: fit[t].tolist() for t in TARGETS})
    preds = clf.predict(val["text"].tolist())

    top_sim = np.empty(len(val), dtype="float32")
    fv = vecs[fit_i]
    for s in range(0, len(val), 2000):
        top_sim[s:s + 2000] = (vecs[val_i[s:s + 2000]] @ fv.T).max(axis=1)

    risk = np.array([risk_score(p) for p in preds])
    true_hi = (val["priority"].isin(HIGH_PRIORITY) & (val["type"] == "Incident")).to_numpy()
    pred_hi = np.array([p["priority"]["label"] in HIGH_PRIORITY and p["type"]["label"] == "Incident" for p in preds])
    conf_low = np.array([any(v["confidence"] < SETTINGS.conf_threshold for v in p.values()) for p in preds])

    sim_th = float(np.percentile(top_sim, args.sim_percentile))
    base = pred_hi | conf_low | (top_sim < sim_th)
    print(f"sim threshold (p{args.sim_percentile:g}): {sim_th:.3f}")
    print(f"baseline gate: recall {base[true_hi].mean():.3f}, escalation rate {base.mean():.3f}")

    chosen = None
    for tau in [x / 100 for x in range(50, 0, -1)]:   # strictest first, loosen until target recall
        esc = base | (risk >= tau)
        if esc[true_hi].mean() >= args.target_recall:
            chosen = (tau, float(esc[true_hi].mean()), float(esc.mean()))
            break
    if chosen is None:
        tau = 0.01
        esc = base | (risk >= tau)
        chosen = (tau, float(esc[true_hi].mean()), float(esc.mean()))
        print("target recall not reached; using the loosest tau")
    tau, rec, rate = chosen
    print(f"risk threshold {tau:.2f}: recall {rec:.3f}, escalation rate {rate:.3f}")

    out = {"sim_threshold": round(sim_th, 4), "risk_threshold": tau,
           "val_recall": round(rec, 4), "val_escalation_rate": round(rate, 4),
           "target_recall": args.target_recall, "val_size": len(val)}
    (art / "gate_thresholds.json").write_text(json.dumps(out, indent=2))
    print("Saved", art / "gate_thresholds.json")


if __name__ == "__main__":
    main()
