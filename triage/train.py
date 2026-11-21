"""Train the triage heads on base, temperature-calibrate on dev_cal, tune C and gate thresholds on dev_tune.

Never reads test files. Run from the repo root:
  python3 triage/train.py            # ~10 min on a laptop CPU
Writes triage/models/{triage.joblib, queue_all.joblib} and triage/reports/dev_report.json.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.optimize import minimize_scalar
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score
from sklearn.pipeline import FeatureUnion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import TriageModel, scaled_proba  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def make_features() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=150_000,
                                 sublinear_tf=True, dtype=np.float32)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, max_features=250_000,
                                 sublinear_tf=True, dtype=np.float32)),
    ])


def head_targets(df: pd.DataFrame) -> dict:
    """head -> (row mask, y). Null types are masked out of type/hp_incident (German file has no type)."""
    typed = df["type"].notna().to_numpy()
    hp = ((df["type"] == "Incident") & (df["priority"] == "high")).astype(int).to_numpy()
    return {
        "type": (typed, df["type"].to_numpy()),
        "queue": (df["queue_core"].to_numpy(), df["queue"].to_numpy()),
        "priority": (np.ones(len(df), bool), df["priority"].to_numpy()),
        "hp_incident": (typed, hp),
        "queue_all": (np.ones(len(df), bool), df["queue"].to_numpy()),
    }


def fit_lr(X, y, C, max_iter):
    return LogisticRegression(C=C, class_weight="balanced", solver="saga", max_iter=max_iter,
                              tol=1e-3, random_state=0).fit(X, y)


def score(head, model, X, y) -> float:
    if head == "hp_incident":
        return average_precision_score(y, model.predict_proba(X)[:, 1])
    return f1_score(y, model.predict(X), average="macro")


def top_label_ece(P: np.ndarray, y_idx: np.ndarray, bins: int = 15) -> float:
    conf, pred = P.max(1), P.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs((pred[m] == y_idx[m]).mean() - conf[m].mean())
    return float(ece)


def fit_temperature(lr, X, y_idx) -> float:
    """Scalar temperature minimizing NLL on the calibration rows (keeps the argmax unchanged)."""
    def nll(logT):
        P = scaled_proba(lr, X, float(np.exp(logT)))
        return -np.log(np.clip(P[np.arange(len(y_idx)), y_idx], 1e-12, None)).mean()
    return float(np.exp(minimize_scalar(nll, bounds=(-3, 3), method="bounded").x))


def coverage_table(P, y_idx, thresholds):
    conf, ok = P.max(1), P.argmax(1) == y_idx
    rows = []
    for t in thresholds:
        keep = conf >= t
        rows.append({"threshold": round(float(t), 2), "coverage": round(float(keep.mean()), 3),
                     "kept_accuracy": round(float(ok[keep].mean()), 3) if keep.any() else None})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset/data/kb_train.parquet")
    ap.add_argument("--grid", default="2,4,8,16,32")
    ap.add_argument("--max-iter", type=int, default=50)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--hp-recall", type=float, default=0.95, help="target HP-Incident recall on dev_tune")
    ap.add_argument("--type-acc", type=float, default=0.85, help="target accuracy of auto-drafted tickets (type)")
    ap.add_argument("--queue-acc", type=float, default=0.80, help="target accuracy of auto-drafted tickets (queue)")
    args = ap.parse_args()
    t_all = time.time()
    os.makedirs(f"{HERE}/models", exist_ok=True)
    os.makedirs(f"{HERE}/reports", exist_ok=True)

    kb = pd.read_parquet(args.data, columns=["ticket_id", "text", "type", "queue", "queue_core",
                                             "priority", "split"])
    base = kb[kb["split"] == "base"].reset_index(drop=True)
    dev = kb[kb["split"] == "dev"].reset_index(drop=True)
    rng = np.random.default_rng(11)
    is_cal = rng.random(len(dev)) < 0.5
    dev_cal, dev_tune = dev[is_cal].reset_index(drop=True), dev[~is_cal].reset_index(drop=True)
    print(f"base {len(base):,}  dev_cal {len(dev_cal):,}  dev_tune {len(dev_tune):,}", flush=True)

    t = time.time()
    features = make_features()
    Xb = features.fit_transform(base["text"]).tocsr()
    Xc = features.transform(dev_cal["text"]).tocsr()
    Xt = features.transform(dev_tune["text"]).tocsr()
    print(f"features {Xb.shape} in {time.time() - t:.0f}s", flush=True)

    Tb, Tc, Tt = head_targets(base), head_targets(dev_cal), head_targets(dev_tune)
    grid = [float(c) for c in args.grid.split(",")]
    report = {"sizes": {"base": len(base), "dev_cal": len(dev_cal), "dev_tune": len(dev_tune)},
              "n_features": int(Xb.shape[1]), "heads": {}}
    best_models, temps = {}, {}

    for head in ["type", "queue", "priority", "hp_incident", "queue_all"]:
        t = time.time()
        mb, yb = Tb[head]
        mt, yt = Tt[head]
        mc, yc = Tc[head]
        Xh, yh = Xb[mb], yb[mb]  # slice once; threads share it (8 GB laptop)
        models = Parallel(n_jobs=args.jobs, prefer="threads")(
            delayed(fit_lr)(Xh, yh, C, args.max_iter) for C in grid)
        del Xh
        scores = [score(head, m, Xt[mt], yt[mt]) for m in models]
        best = int(np.argmax(scores))
        raw = models[best]
        del models
        cls = list(raw.classes_)
        T = fit_temperature(raw, Xc[mc], np.array([cls.index(v) for v in yc[mc]]))
        y_idx = np.array([cls.index(v) for v in yt[mt]])
        P_raw, P_cal = scaled_proba(raw, Xt[mt], 1.0), scaled_proba(raw, Xt[mt], T)
        ece_raw, ece_cal = top_label_ece(P_raw, y_idx), top_label_ece(P_cal, y_idx)
        best_models[head] = raw
        temps[head] = T if ece_cal < ece_raw else 1.0  # keep calibration only if it helps on dev_tune
        r = {
            "C_grid": dict(zip(map(str, grid), [round(s, 4) for s in scores])),
            "C": grid[best],
            "metric": "average_precision" if head == "hp_incident" else "macro_f1",
            "dev_tune_score": round(scores[best], 4),
            "temperature_fit": round(T, 4),
            "temperature_used": round(temps[head], 4),
            "ece_raw": round(ece_raw, 4),
            "ece_temperature": round(ece_cal, 4),
            "n_train": int(mb.sum()), "n_classes": len(cls),
            "secs": round(time.time() - t),
        }
        if head in ("type", "queue"):
            r["coverage_table"] = coverage_table(scaled_proba(raw, Xt[mt], temps[head]), y_idx,
                                                 np.arange(0.3, 0.96, 0.05))
        report["heads"][head] = r
        print(f"{head:12s} C={r['C']:<4} {r['metric']}={r['dev_tune_score']:.3f} "
              f"T={r['temperature_fit']:.2f} ECE {r['ece_raw']:.3f}->{r['ece_temperature']:.3f} used T={r['temperature_used']} "
              f"({r['secs']}s)  grid={r['C_grid']}", flush=True)

    # ---- Gate thresholds (dev_tune, calibrated probabilities) ----
    mt, yt = Tt["hp_incident"]
    p_hp_all = scaled_proba(best_models["hp_incident"], Xt, temps["hp_incident"])[:, 1]
    pos = np.sort(p_hp_all[mt & (yt == 1)])
    k = int(np.floor((1 - args.hp_recall) * len(pos)))
    tau_hp = float(pos[k])
    hp_recall = float((pos >= tau_hp).mean())
    gate = {"hp_incident_threshold": round(tau_hp, 4), "conf_threshold": {}}
    for head, target in (("type", args.type_acc), ("queue", args.queue_acc)):
        tab = report["heads"][head]["coverage_table"]
        ok = [row for row in tab if row["kept_accuracy"] is not None and row["kept_accuracy"] >= target]
        gate["conf_threshold"][head] = ok[0]["threshold"] if ok else tab[-1]["threshold"]
    # Escalation rate of the full gate on dev_tune (classifier rules only; retrieval/guard rules come later).
    esc = p_hp_all >= tau_hp
    for head in ("type", "queue"):
        esc |= scaled_proba(best_models[head], Xt, temps[head]).max(1) < gate["conf_threshold"][head]
    report["gate"] = {**gate, "dev_tune_hp_recall": round(hp_recall, 4),
                      "dev_tune_hp_flag_rate": round(float((p_hp_all >= tau_hp).mean()), 4),
                      "dev_tune_escalation_rate_classifier_rules": round(float(esc.mean()), 4),
                      "targets": {"hp_recall": args.hp_recall, "type_acc": args.type_acc,
                                  "queue_acc": args.queue_acc}}
    print("gate:", json.dumps(report["gate"]), flush=True)

    meta = {"trained_on": "dataset/data/kb_train.parquet split==base",
            "calibrated_on": "dev_cal (50% of dev, seed 11), temperature scaling",
            "tuned_on": "dev_tune", "core_queues": [str(c) for c in best_models["queue"].classes_]}
    serving = ["type", "queue", "priority", "hp_incident"]
    TriageModel(features, {h: best_models[h] for h in serving}, {h: temps[h] for h in serving}, gate,
                meta).save(f"{HERE}/models/triage.joblib")
    TriageModel(features, {"queue_all": best_models["queue_all"]}, {"queue_all": temps["queue_all"]}, gate,
                meta).save(f"{HERE}/models/queue_all.joblib")
    report["secs_total"] = round(time.time() - t_all)
    with open(f"{HERE}/reports/dev_report.json", "w") as f:
        json.dump(report, f, indent=2)
    for p in ["triage.joblib", "queue_all.joblib"]:
        print(p, f"{os.path.getsize(f'{HERE}/models/{p}') / 1e6:.0f} MB")
    print(f"done in {report['secs_total']}s")


if __name__ == "__main__":
    main()
