"""Holdout evaluation. Only subject + body of holdout tickets are given to the pipeline.

Usage:
    python scripts/evaluate.py                     # classifier on full holdout, gate+latency on 500 sample
    python scripts/evaluate.py --gate-sample 2000 --with-llm
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, f1_score, recall_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentineldesk.classifier import TriageClassifier  # noqa: E402
from sentineldesk.config import SETTINGS  # noqa: E402
from sentineldesk.data import TARGETS, build_text  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate-sample", type=int, default=500)
    ap.add_argument("--with-llm", action="store_true", help="include generation in latency")
    args = ap.parse_args()

    art = Path(SETTINGS.artifacts_dir)
    test = pd.read_parquet(art / "test_holdout.parquet")
    gold = test[TARGETS + ["ticket_id"]].copy()          # labels kept aside, never passed to the pipeline
    inputs = test[["subject", "body"]].copy()            # the ONLY columns the system sees
    texts = [build_text(s, b) for s, b in zip(inputs["subject"], inputs["body"])]

    report: dict = {"n_holdout": len(test)}
    print(f"Classifier on {len(test):,} holdout tickets")
    clf = TriageClassifier.load(art / "classifier.joblib")
    preds = clf.predict(texts)
    for t in TARGETS:
        y, p = gold[t].tolist(), [x[t]["label"] for x in preds]
        report[f"{t}_macro_f1"] = round(f1_score(y, p, average="macro"), 4)
        report[f"{t}_accuracy"] = round(float(np.mean(np.array(y) == np.array(p))), 4)
        print(f"\n=== {t} === macro-F1 {report[f'{t}_macro_f1']:.4f}")
        print(classification_report(y, p, digits=3, zero_division=0))

    yp = gold["priority"].tolist()
    pp = [x["priority"]["label"] for x in preds]
    hi = {"high", "critical"}
    report["high_priority_recall"] = round(recall_score([v in hi for v in yp], [v in hi for v in pp], zero_division=0), 4)
    true_hi = gold["priority"].isin(["high", "critical"]) & (gold["type"] == "Incident")
    pred_hi = np.array([x["priority"]["label"] in ("high", "critical") and x["type"]["label"] == "Incident" for x in preds])
    report["high_priority_incident_recall_classifier"] = round(float(pred_hi[true_hi.values].mean()), 4) if true_hi.any() else None
    print("High-priority recall:", report["high_priority_recall"])
    print("High-priority Incident recall (classifier):", report["high_priority_incident_recall_classifier"])

    if args.gate_sample > 0:
        from sentineldesk.generator import Generator
        from sentineldesk.pipeline import SentinelDesk

        n = min(args.gate_sample, len(test))
        idx = test.sample(n=n, random_state=0).index
        print(f"\nFull pipeline on {n} holdout tickets (gate, retrieval, latency)…")
        gen = None if args.with_llm else Generator("none")
        desk = SentinelDesk(classifier=clf, generator=gen)
        assert not (desk.retriever.ticket_ids() & set(test["ticket_id"])), "LEAKAGE: holdout ids in index"

        lat, esc, top_sims = [], [], []
        for i in idx:
            r = desk.triage(inputs.at[i, "subject"], inputs.at[i, "body"], generate=True, track_burst=False)
            lat.append(r["latency_ms"]); esc.append(r["gate"]["escalate"])
            top_sims.append(r["hits"][0]["similarity"] if r["hits"] else 0.0)
        esc = np.array(esc)
        th = true_hi.loc[idx].values
        report["gate_sample"] = n
        report["gate_high_incident_escalation_recall"] = round(float(esc[th].mean()), 4) if th.any() else None
        report["auto_draft_rate"] = round(float(1 - esc.mean()), 4)
        report["latency_ms_p50"] = round(float(np.percentile(lat, 50)), 1)
        report["latency_ms_p95"] = round(float(np.percentile(lat, 95)), 1)
        report["top1_similarity_p10_p50_p90"] = [round(float(x), 3) for x in np.percentile(top_sims, [10, 50, 90])]
        for k in ["gate_high_incident_escalation_recall", "auto_draft_rate", "latency_ms_p50",
                  "latency_ms_p95", "top1_similarity_p10_p50_p90"]:
            print(f"{k}: {report[k]}")

    (art / "eval_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nSaved {art / 'eval_report.json'}")


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"Evaluation took {time.time() - t0:.0f}s")
