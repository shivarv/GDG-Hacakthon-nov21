"""Shared data/split/metric code for the experimental track. Mirrors triage/train.py exactly."""
import hashlib
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score

ROOT = os.environ.get("EXP_ROOT", os.path.expanduser("~/sentineldesk-exp"))
DATA = os.path.join(ROOT, "data")
HEADS = ["type", "queue", "priority", "hp", "queue_all"]
MAIN = ["type", "queue", "priority"]

SPLIT_SHA = {"dev_cal": "03cf8046f3af0c39e10580d48448decd5a265d0f",
             "dev_tune": "434bc8d08752ec677085a73123d91bc3cfd60742"}


def load_kb():
    kb = pd.read_parquet(f"{DATA}/kb_train.parquet",
                         columns=["ticket_id", "subject", "body", "text", "type", "queue", "queue_core",
                                  "priority", "language", "split", "has_answer"])
    base = kb[kb["split"] == "base"].reset_index(drop=True)
    dev = kb[kb["split"] == "dev"].reset_index(drop=True)
    is_cal = np.random.default_rng(11).random(len(dev)) < 0.5  # identical to triage/train.py
    for name, m in (("dev_cal", is_cal), ("dev_tune", ~is_cal)):
        sha = hashlib.sha1("\n".join(dev.loc[m, "ticket_id"]).encode()).hexdigest()
        assert sha == SPLIT_SHA[name], f"{name} split mismatch: {sha}"
    return kb, base, dev, is_cal


def label_space(kb):
    typed = kb["type"].notna()
    return {
        "type": sorted(kb.loc[typed, "type"].unique()),
        "queue": sorted(kb.loc[kb["queue_core"], "queue"].unique()),
        "priority": sorted(kb["priority"].unique()),
        "hp": [0, 1],
        "queue_all": sorted(kb["queue"].unique()),
    }


def targets(df, space):
    """head -> int array, -1 where masked (null type rows excluded from type/hp; non-core from queue)."""
    out = {}
    typed = df["type"].notna().to_numpy()
    idx = {h: {c: i for i, c in enumerate(space[h])} for h in space}
    out["type"] = np.where(typed, df["type"].map(idx["type"]).fillna(-1), -1).astype(int)
    out["queue"] = np.where(df["queue_core"].to_numpy(), df["queue"].map(idx["queue"]).fillna(-1), -1).astype(int)
    out["priority"] = df["priority"].map(idx["priority"]).astype(int).to_numpy()
    hp = ((df["type"] == "Incident") & (df["priority"] == "high")).astype(int).to_numpy()
    out["hp"] = np.where(typed, hp, -1)
    out["queue_all"] = df["queue"].map(idx["queue_all"]).astype(int).to_numpy()
    return out


def softmax(z, T=1.0):
    z = z / T
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def top_label_ece(P, y_idx, bins=15):  # verbatim logic from triage/train.py
    conf, pred = P.max(1), P.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs((pred[m] == y_idx[m]).mean() - conf[m].mean())
    return float(ece)


def fit_temperature(logits, y):
    """Scalar T minimizing NLL (grid + refine). logits [n,k], y int."""
    best = (1e9, 1.0)
    for T in np.exp(np.linspace(np.log(0.3), np.log(8), 60)):
        p = softmax(logits, T)[np.arange(len(y)), y]
        nll = -np.log(np.clip(p, 1e-12, 1)).mean()
        best = min(best, (nll, T))
    return float(best[1])


def head_metrics(P, y, head):
    m = y >= 0
    P, y = P[m], y[m]
    if head == "hp":
        p1 = P[:, 1] if P.ndim == 2 else P
        return {"ap": round(float(average_precision_score(y, p1)), 4)}
    return {"macro_f1": round(float(f1_score(y, P.argmax(1), average="macro")), 4),
            "acc": round(float((P.argmax(1) == y).mean()), 4),
            "ece": round(top_label_ece(P, y), 4)}


def hp_threshold(p_hp, y_hp, recall=0.95):
    """Baseline formula: tau = sorted positive probs at floor((1-recall)*n). Returns tau, recall, flag rate (all rows)."""
    pos = np.sort(p_hp[y_hp == 1])
    tau = float(pos[int(np.floor((1 - recall) * len(pos)))])
    return {"tau": round(tau, 5), "recall": round(float((pos >= tau).mean()), 4),
            "flag_rate": round(float((p_hp >= tau).mean()), 4)}


def dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=float)
