"""LR + kNN blend: p = (1 - alpha) * p_LR + alpha * p_kNN, then a temperature on the mixture.

p_kNN is a similarity-weighted vote of the k most similar base tickets (TF-IDF cosine, same features
as the LR heads), with weights exp(beta * sim). alpha, k and beta are tuned per head on dev_cal; the
temperature is fitted on dev_cal; everything is reported on dev_tune. Test data is never read here.

Run from the repo root after train.py:
  python3 triage/blend.py            # writes triage/models/blend.joblib + triage/reports/blend_dev_report.json
  python3 triage/eval.py --model blend   # one-shot test evaluation (same metrics as the LR model)

Serving: BlendModel has the same interface as TriageModel (transform / proba / classes / gate / predict).
"""
import argparse
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.optimize import minimize_scalar
from sklearn.metrics import average_precision_score, f1_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model import CONTRACT_HEADS, TriageModel  # noqa: E402

HEADS = ["type", "queue", "priority", "hp_incident"]
KMAX = 50


def head_targets(df: pd.DataFrame) -> dict:
    typed = df["type"].notna().to_numpy()
    hp = ((df["type"] == "Incident") & (df["priority"] == "high")).astype(int).to_numpy()
    return {"type": (typed, df["type"].to_numpy()),
            "queue": (df["queue_core"].to_numpy(), df["queue"].to_numpy()),
            "priority": (np.ones(len(df), bool), df["priority"].to_numpy()),
            "hp_incident": (typed, hp)}


def _topk_chunk(Xq, XbT, kmax):
    S = (Xq @ XbT).toarray()
    part = np.argpartition(-S, kmax, axis=1)[:, :kmax]
    ps = np.take_along_axis(S, part, 1)
    order = np.argsort(-ps, axis=1)
    return np.take_along_axis(part, order, 1), np.take_along_axis(ps, order, 1).astype(np.float32)


def topk(Xq, Xb, kmax=KMAX, chunk=300, n_jobs=1):
    XbT = Xb.T.tocsc()
    chunks = [Xq[s:s + chunk] for s in range(0, Xq.shape[0], chunk)]
    if n_jobs == 1 or len(chunks) == 1:
        res = [_topk_chunk(c, XbT, kmax) for c in chunks]
    else:
        res = Parallel(n_jobs=n_jobs)(delayed(_topk_chunk)(c, XbT, kmax) for c in chunks)
    return np.vstack([r[0] for r in res]), np.vstack([r[1] for r in res])


def knn_proba(nb_y_idx, nb_sim, n_classes, k, beta):
    """nb_y_idx: (n, KMAX) class indices of neighbours (sorted by sim). Returns (n, C) vote distribution."""
    y, s = nb_y_idx[:, :k], nb_sim[:, :k]
    w = np.exp(beta * (s - s[:, :1]))  # relative to the top sim: numerically safe
    P = np.zeros((len(y), n_classes), dtype=np.float64)
    np.add.at(P, (np.repeat(np.arange(len(y)), k), y.ravel()), w.ravel())
    return P / P.sum(1, keepdims=True)


def temper(P, T):
    L = np.log(np.clip(P, 1e-9, None)) / T
    L -= L.max(1, keepdims=True)
    E = np.exp(L)
    return E / E.sum(1, keepdims=True)


class BlendModel:
    """Same interface as TriageModel. Pickled content is plain sklearn/scipy/numpy objects only."""

    def __init__(self, lr: TriageModel, Xb, nb_labels: dict, params: dict, gate: dict, meta: dict):
        self.lr = lr
        self.features = lr.features
        self.Xb = Xb.tocsr()              # base TF-IDF rows
        self.nb_labels = nb_labels        # head -> (base row indices usable by the head, class index per row)
        self.params = params              # head -> {alpha, k, beta, T}
        self.gate = gate
        self.meta = meta
        self._Xh = {}  # head -> base rows usable by that head (sliced once)

    def save(self, path):
        joblib.dump({"lr_path": self.meta["lr_path"], "Xb": self.Xb, "nb_labels": self.nb_labels,
                     "params": self.params, "gate": self.gate, "meta": self.meta}, path, compress=3)

    @classmethod
    def load(cls, path, lr_path=None):
        d = joblib.load(path)
        lr = TriageModel.load(lr_path or os.path.join(os.path.dirname(path), os.path.basename(d["lr_path"])))
        return cls(lr, d["Xb"], d["nb_labels"], d["params"], d["gate"], d["meta"])

    def transform(self, texts):
        return self.lr.transform(texts)

    def classes(self, head):
        return self.lr.classes(head)

    def proba(self, X, head, n_jobs=1):
        p = self.params[head]
        P_lr = self.lr.proba(X, head)
        if p["alpha"] > 0:
            rows, yidx = self.nb_labels[head]
            if head not in self._Xh:
                self._Xh[head] = self.Xb[rows]
            idx, sim = topk(X, self._Xh[head], kmax=p["k"], n_jobs=n_jobs)
            P_knn = knn_proba(yidx[idx], sim, P_lr.shape[1], p["k"], p["beta"])
            P = (1 - p["alpha"]) * P_lr + p["alpha"] * P_knn
        else:
            P = P_lr
        return temper(P, p["T"])

    def predict(self, subject, body):
        from textprep import build_text
        from urgency import urgency
        t0 = time.perf_counter()
        text = build_text(subject, body)
        X = self.transform([text])
        out = {}
        for head in CONTRACT_HEADS:
            P = self.proba(X, head)[0]
            cls = self.classes(head)
            i = int(np.argmax(P))
            out[head] = {"label": cls[i], "conf": float(P[i]),
                         "probs": {c: round(float(v), 4) for c, v in sorted(zip(cls, P), key=lambda z: -z[1])}}
        p_hp = float(self.proba(X, "hp_incident")[0][list(self.classes("hp_incident")).index(1)])
        out["hp_incident"] = {"prob": p_hp, "flag": p_hp >= self.gate["hp_incident_threshold"]}
        reasons = []
        u = urgency(text)
        out["urgency"] = {"urgent": u["urgent"], "reason": u["reason"]}
        if u["urgent"]:
            reasons.append(u["reason"])
        if out["hp_incident"]["flag"]:
            reasons.append(f"Likely high-priority Incident (p={p_hp:.2f} >= {self.gate['hp_incident_threshold']:.2f})")
        for head in ("type", "queue"):
            th = self.gate["conf_threshold"][head]
            if out[head]["conf"] < th:
                reasons.append(f"Low {head} confidence ({out[head]['conf']:.3f} < {th:.2f})")
        out["gate_hints"] = {"escalate": bool(reasons), "reasons": reasons}
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out


def top_label_ece(P, y_idx, bins=15):
    conf, pred = P.max(1), P.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs((pred[m] == y_idx[m]).mean() - conf[m].mean())
    return float(e)


def head_score(head, P, y_idx):
    if head == "hp_incident":
        return average_precision_score(y_idx, P[:, 1])
    return f1_score(y_idx, P.argmax(1), average="macro")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset/data/kb_train.parquet")
    ap.add_argument("--lr", default=f"{HERE}/models/triage.joblib")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--hp-recall", type=float, default=0.90)
    ap.add_argument("--escalation-budget", type=float, default=0.35,
                    help="max share of dev_tune tickets escalated by the classifier rules")
    args = ap.parse_args()
    t0 = time.time()
    lr = TriageModel.load(args.lr)

    kb = pd.read_parquet(args.data, columns=["ticket_id", "text", "type", "queue", "queue_core", "priority", "split"])
    base = kb[kb["split"] == "base"].reset_index(drop=True)
    dev = kb[kb["split"] == "dev"].reset_index(drop=True)
    is_cal = np.random.default_rng(11).random(len(dev)) < 0.5  # same halves as train.py
    sets = {"cal": dev[is_cal].reset_index(drop=True), "tune": dev[~is_cal].reset_index(drop=True)}

    Xb = lr.transform(base["text"]).tocsr()
    X = {k: lr.transform(v["text"]).tocsr() for k, v in sets.items()}
    Tb = head_targets(base)
    T = {k: head_targets(v) for k, v in sets.items()}
    print(f"features ready in {time.time() - t0:.0f}s", flush=True)

    params, nb_labels, report = {}, {}, {}
    for head in HEADS:
        th = time.time()
        cls = lr.classes(head)
        mb, yb = Tb[head]
        rows = np.where(mb)[0]
        yb_idx = np.array([cls.index(v) for v in yb[rows]])
        nb_labels[head] = (rows, yb_idx)
        cache = {}
        for name in ("cal", "tune"):
            m, y = T[name][head]
            idx, sim = topk(X[name][m], Xb[rows], n_jobs=args.jobs)
            cache[name] = {"P_lr": lr.proba(X[name][m], head), "nb": yb_idx[idx], "sim": sim,
                           "y": np.array([cls.index(v) for v in y[m]])}
        c = cache["cal"]
        best = (-1, None)
        grid = []
        for k in (1, 3, 5, 10, 20, 50):
            for beta in (0.0, 10.0, 30.0, 100.0):
                if k == 1 and beta > 0:
                    continue
                Pk = knn_proba(c["nb"], c["sim"], len(cls), k, beta)
                for alpha in np.round(np.arange(0, 1.01, 0.1), 2):
                    s = head_score(head, (1 - alpha) * c["P_lr"] + alpha * Pk, c["y"])
                    grid.append((k, beta, float(alpha), s))
                    if s > best[0]:
                        best = (s, (k, beta, float(alpha)))
        k, beta, alpha = best[1]
        Pk_cal = knn_proba(c["nb"], c["sim"], len(cls), k, beta)
        P_cal = (1 - alpha) * c["P_lr"] + alpha * Pk_cal

        def nll(logT):
            P = temper(P_cal, float(np.exp(logT)))
            return -np.log(np.clip(P[np.arange(len(c["y"])), c["y"]], 1e-12, None)).mean()

        Tm = float(np.exp(minimize_scalar(nll, bounds=(-3, 3), method="bounded").x))
        params[head] = {"alpha": alpha, "k": int(k), "beta": beta, "T": Tm}

        t = cache["tune"]
        P_lr_t = t["P_lr"]
        P_bl_t = temper((1 - alpha) * P_lr_t + alpha * knn_proba(t["nb"], t["sim"], len(cls), k, beta), Tm)
        P_knn1 = knn_proba(t["nb"], t["sim"], len(cls), 1, 0.0)
        report[head] = {
            "params": params[head],
            "dev_tune": {"lr": round(head_score(head, P_lr_t, t["y"]), 4),
                         "knn1": round(head_score(head, P_knn1, t["y"]), 4),
                         "blend": round(head_score(head, P_bl_t, t["y"]), 4),
                         "metric": "average_precision" if head == "hp_incident" else "macro_f1",
                         "ece_lr": round(top_label_ece(P_lr_t, t["y"]), 4),
                         "ece_blend": round(top_label_ece(P_bl_t, t["y"]), 4)},
            "secs": round(time.time() - th),
        }
        cache["tune"]["P_blend"] = P_bl_t
        report[head]["_P_tune"] = P_bl_t  # removed before writing
        print(f"{head:12s} alpha={alpha} k={k} beta={beta} T={Tm:.2f} | dev_tune LR {report[head]['dev_tune']['lr']:.3f} "
              f"1NN {report[head]['dev_tune']['knn1']:.3f} BLEND {report[head]['dev_tune']['blend']:.3f} "
              f"| ECE {report[head]['dev_tune']['ece_lr']:.3f}->{report[head]['dev_tune']['ece_blend']:.3f} ({report[head]['secs']}s)",
              flush=True)

    # ---- Gate on dev_tune: HP threshold for the recall target; confidence thresholds within the budget ----
    tune = sets["tune"]
    full = {}
    blend = BlendModel(lr, Xb, nb_labels, params, {}, {})
    for head in ("type", "queue", "hp_incident"):
        full[head] = blend.proba(X["tune"], head, n_jobs=args.jobs)
    hp_true = ((tune["type"] == "Incident") & (tune["priority"] == "high")).to_numpy()
    p_hp = full["hp_incident"][:, 1]
    pos = np.sort(p_hp[hp_true])
    tau_hp = float(pos[int(np.floor((1 - args.hp_recall) * len(pos)))])
    hp_flag = p_hp >= tau_hp
    curve = [{"recall_target": r, "threshold": round(float(pos[int(np.floor((1 - r) * len(pos)))]), 4),
              "flag_rate": round(float((p_hp >= pos[int(np.floor((1 - r) * len(pos)))]).mean()), 4)}
             for r in (0.80, 0.85, 0.90, 0.95, 0.98)]
    # largest common confidence threshold such that the total escalation rate stays within budget
    conf_t = conf_q = 0.0
    for th in np.round(np.arange(0.95, 0.0, -0.05), 2):
        esc = hp_flag | (full["type"].max(1) < th) | (full["queue"].max(1) < th)
        if esc.mean() <= args.escalation_budget:
            conf_t = conf_q = float(th)
            break
    esc = hp_flag | (full["type"].max(1) < conf_t) | (full["queue"].max(1) < conf_q)
    gate = {"hp_incident_threshold": round(tau_hp, 4), "conf_threshold": {"type": conf_t, "queue": conf_q}}
    gate_report = {**gate, "dev_tune_hp_recall": round(float(hp_flag[hp_true].mean()), 4),
                   "dev_tune_hp_flag_rate": round(float(hp_flag.mean()), 4),
                   "dev_tune_escalation_rate_classifier_rules": round(float(esc.mean()), 4),
                   "hp_recall_vs_flag_rate": curve,
                   "targets": {"hp_recall": args.hp_recall, "escalation_budget": args.escalation_budget}}
    print("gate:", json.dumps(gate_report), flush=True)

    meta = {"lr_path": os.path.basename(args.lr), "knn_features": "same TF-IDF as LR, fit on base",
            "tuned_on": "dev_cal (alpha,k,beta,T); gate on dev_tune", "n_base": len(base)}
    BlendModel(lr, Xb, nb_labels, params, gate, meta).save(f"{HERE}/models/blend.joblib")
    for h in report:
        report[h].pop("_P_tune", None)
    with open(f"{HERE}/reports/blend_dev_report.json", "w") as f:
        json.dump({"heads": report, "gate": gate_report, "secs": round(time.time() - t0)}, f, indent=2)
    print(f"blend.joblib {os.path.getsize(f'{HERE}/models/blend.joblib') / 1e6:.0f} MB, done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
