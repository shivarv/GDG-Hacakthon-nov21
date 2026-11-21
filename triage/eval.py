"""One-shot holdout evaluation. The ONLY script allowed to read test labels.

Run from the repo root after train.py:
  python3 triage/eval.py
Writes triage/reports/{metrics.json, reliability.png}. Reports the clean test set (headline)
and the full official 20% test set (comparable with other teams), plus a per-duplicate-subset breakdown.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model import TriageModel  # noqa: E402

DATA = "dataset/data"


def top_label_ece(P, y_idx, bins=15):
    conf, pred = P.max(1), P.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    ece, curve = 0.0, []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            acc, c = (pred[m] == y_idx[m]).mean(), conf[m].mean()
            ece += m.mean() * abs(acc - c)
            curve.append((float(c), float(acc), int(m.sum())))
    return float(ece), curve


def evaluate(tm, qa, inputs, labels, with_breakdown=False):
    assert (inputs["ticket_id"].to_numpy() == labels["ticket_id"].to_numpy()).all()
    X = tm.transform(inputs["text"].tolist())
    out, curves = {"n": len(inputs)}, {}
    preds = {}
    for head, col, mask in [
        ("type", "type", labels["type"].notna()),
        ("queue", "queue", labels["queue_core"]),
        ("priority", "priority", pd.Series(True, index=labels.index)),
    ]:
        m = mask.to_numpy()
        P = tm.proba(X, head)
        cls = tm.classes(head)
        pred = np.array(cls)[P.argmax(1)]
        preds[head] = pred
        y = labels[col].to_numpy()[m]
        y_idx = np.array([cls.index(v) for v in y])
        ece, curve = top_label_ece(P[m], y_idx)
        curves[head] = curve
        out[head] = {
            "n_scored": int(m.sum()),
            "macro_f1": round(f1_score(y, pred[m], average="macro"), 4),
            "accuracy": round(float((pred[m] == y).mean()), 4),
            "ece": round(ece, 4),
            "per_class_f1": {c: round(v, 4) for c, v in zip(cls, f1_score(y, pred[m], labels=cls, average=None))},
            "confusion": {"labels": cls, "matrix": confusion_matrix(y, pred[m], labels=cls).tolist()},
        }
    if qa is not None:
        P = qa.proba(X, "queue_all")
        cls = qa.classes("queue_all")
        pred = np.array(cls)[P.argmax(1)]
        y = labels["queue"].to_numpy()
        out["queue_all"] = {"n_scored": len(y), "macro_f1": round(f1_score(y, pred, average="macro"), 4),
                            "accuracy": round(float((pred == y).mean()), 4),
                            "ece": round(top_label_ece(P, np.array([cls.index(v) for v in y]))[0], 4)}

    # High-Priority Incident recall (positives = typed rows with type Incident and priority high).
    pos = ((labels["type"] == "Incident") & (labels["priority"] == "high")).to_numpy()
    typed = labels["type"].notna().to_numpy()
    p_hp = tm.proba(X, "hp_incident")[:, list(tm.classes("hp_incident")).index(1)]
    flag = p_hp >= tm.gate["hp_incident_threshold"]
    clf_hp = (preds["type"] == "Incident") & (preds["priority"] == "high")
    esc = flag.copy()
    for head in ("type", "queue"):
        esc |= tm.proba(X, head).max(1) < tm.gate["conf_threshold"][head]
    out["hp_incident"] = {
        "n_positive": int(pos.sum()),
        "classifier_recall": round(float(clf_hp[pos].mean()), 4),
        "hp_head_recall": round(float(flag[pos].mean()), 4),
        "hp_head_precision": round(float(precision_score(pos[typed], flag[typed], zero_division=0)), 4),
        "gate_recall_any_classifier_rule": round(float(esc[pos].mean()), 4),
        "hp_flag_rate": round(float(flag.mean()), 4),
        "escalation_rate_classifier_rules": round(float(esc.mean()), 4),
        "threshold": tm.gate["hp_incident_threshold"],
    }
    if with_breakdown and "eval_subset" in inputs:
        bd = {}
        for sub, g in inputs.groupby("eval_subset"):
            idx = inputs.index.get_indexer(g.index)
            row = {"n": len(g)}
            for head, col in (("type", "type"), ("queue", "queue"), ("priority", "priority")):
                lab = labels[col].to_numpy()[idx]
                pr = preds[head][idx]
                m = pd.notna(lab) & ((labels["queue_core"].to_numpy()[idx]) if head == "queue" else True)
                row[f"{head}_accuracy"] = round(float((pr[m] == lab[m]).mean()), 4) if m.any() else None
            p = pos[idx]
            row["hp_head_recall"] = round(float(flag[idx][p].mean()), 4) if p.any() else None
            bd[sub] = row
        out["by_eval_subset"] = bd
    return out, curves


def latency(tm, inputs, n=200):
    ts = []
    for _, r in inputs.head(n).iterrows():
        t = time.perf_counter()
        tm.predict(r["subject"], r["body"])
        ts.append((time.perf_counter() - t) * 1000)
    return {"n": n, "p50_ms": round(float(np.percentile(ts, 50)), 1), "p95_ms": round(float(np.percentile(ts, 95)), 1)}


def plot(curves, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(curves), figsize=(4 * len(curves), 4))
    for ax, (head, curve) in zip(axes, curves.items()):
        c, a, n = zip(*curve)
        ax.plot([0, 1], [0, 1], "--", color="#999", lw=1)
        ax.plot(c, a, "o-", color="#2a6fdb")
        for ci, ai, ni in zip(c, a, n):
            ax.annotate(str(ni), (ci, ai), fontsize=6, alpha=0.6, xytext=(2, -8), textcoords="offset points")
        ax.set(title=f"{head} (clean test)", xlabel="calibrated confidence", ylabel="accuracy", xlim=(0, 1), ylim=(0, 1))
    fig.tight_layout()
    fig.savefig(path, dpi=130)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["lr", "blend"], default="lr")
    args = ap.parse_args()
    suffix = "" if args.model == "lr" else "_blend"
    if args.model == "blend":
        from blend import BlendModel
        tm = BlendModel.load(f"{HERE}/models/blend.joblib")
    else:
        tm = TriageModel.load(f"{HERE}/models/triage.joblib")
    qa_path = f"{HERE}/models/queue_all.joblib"
    qa = TriageModel.load(qa_path) if os.path.exists(qa_path) else None
    res = {"gate": tm.gate}
    ci, cl = pd.read_parquet(f"{DATA}/test_inputs.parquet"), pd.read_parquet(f"{DATA}/test_labels.parquet")
    res["clean_test"], curves = evaluate(tm, qa, ci, cl)
    ai, al = pd.read_parquet(f"{DATA}/test_inputs_all.parquet"), pd.read_parquet(f"{DATA}/test_labels_all.parquet")
    ai = ai[ai["eval_subset"] != "empty_body"].reset_index(drop=True)
    al = al.set_index("ticket_id").loc[ai["ticket_id"]].reset_index()
    res["full_official_test"], _ = evaluate(tm, qa, ai, al, with_breakdown=True)
    res["full_official_test"]["note"] = "excludes the 2 empty-body rows"
    res["latency_single_ticket"] = latency(tm, ci)
    os.makedirs(f"{HERE}/reports", exist_ok=True)
    res["model"] = args.model
    with open(f"{HERE}/reports/metrics{suffix}.json", "w") as f:
        json.dump(res, f, indent=2)
    plot(curves, f"{HERE}/reports/reliability{suffix}.png")
    for name in ("clean_test", "full_official_test"):
        r = res[name]
        print(f"\n== {name} (n={r['n']:,})")
        for h in ("type", "queue", "queue_all", "priority"):
            if h in r:
                print(f"  {h:9s} macroF1 {r[h]['macro_f1']:.3f}  acc {r[h]['accuracy']:.3f}  ECE {r[h]['ece']:.3f}")
        print("  hp_incident", json.dumps(r["hp_incident"]))
    print("\nby eval_subset:", json.dumps(res["full_official_test"]["by_eval_subset"], indent=1))
    print("latency", res["latency_single_ticket"])


if __name__ == "__main__":
    main()
