"""Leaderboard + similarity-gated log-linear fusion of sources, all on dev (fit on dev_cal, report dev_tune).

Sources: tfidf (Mac dump), knn_<emb> (probe_knn.py), ft:<run_id> (fine-tune best-epoch dev logits).
Strata by e5-small top-1 similarity to base: "near" (>= --gate, near-paraphrase exists) vs "novel" (< --gate).
The "novel" stratum is our proxy for judge-typed tickets.

  python fuse.py --sources tfidf knn_e5-small ft:e5s_s13 ft:e5b_s13
"""
import argparse
import json

import numpy as np
from scipy.optimize import minimize

from common import MAIN, ROOT, dump, head_metrics, hp_threshold, label_space, load_kb, softmax, targets

FUSE_HEADS = ["type", "queue", "priority", "hp"]


def load_source(name, space, n_dev):
    """-> {head: P[n_dev, k]} with columns in label_space order."""
    if name == "tfidf":
        z = np.load(f"{ROOT}/probs/tfidf.npz")
        out = {}
        for h in FUSE_HEADS:
            cls = list(z[f"{h}_classes"])
            want = [str(c) for c in space[h]]
            out[h] = z[f"dev_{h}"][:, [cls.index(c) for c in want]]
        return out
    if name.startswith("knn_"):
        z = np.load(f"{ROOT}/probs/{name}.npz")
        return {h: z[f"dev_{h}"] for h in FUSE_HEADS}
    if name.startswith("ft:"):
        rid = name[3:]
        m = json.load(open(f"{ROOT}/runs/{rid}/metrics.json")) if _exists(f"{ROOT}/runs/{rid}/metrics.json") else None
        ep = m["best_epoch"] if m else _best_logged_epoch(rid)
        z = np.load(f"{ROOT}/runs/{rid}/dev_logits_ep{ep}.npz")
        out = {h: softmax(z[h]) for h in ["type", "queue", "priority"]}
        p1 = 1 / (1 + np.exp(-z["hp"][:, 0]))
        out["hp"] = np.column_stack([1 - p1, p1])
        return out
    raise ValueError(name)


def _exists(p):
    import os
    return os.path.exists(p)


def _best_logged_epoch(rid):
    rows = [json.loads(l) for l in open(f"{ROOT}/runs/{rid}/log.jsonl")]
    return max(rows, key=lambda r: r["mean_main_f1"])["epoch"]


def pool(logPs, w):
    z = sum(wi * lp for wi, lp in zip(w, logPs))
    return softmax(z)


def fit_weights(logPs, y):
    m = y >= 0
    L = [lp[m] for lp in logPs]
    yy = y[m]

    def nll(w):
        w = np.abs(w)
        P = pool(L, w)
        return -np.log(np.clip(P[np.arange(len(yy)), yy], 1e-12, 1)).mean()
    r = minimize(nll, x0=np.ones(len(L)) / len(L), method="Nelder-Mead",
                 options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-5})
    return np.abs(r.x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="+", required=True)
    ap.add_argument("--gate", type=float, default=0.97)
    ap.add_argument("--name", default="leaderboard")
    a = ap.parse_args()
    kb, base, dev, is_cal = load_kb()
    space = label_space(kb)
    yd = targets(dev, space)
    sim = np.load(f"{ROOT}/probs/knn_e5-small.npz")
    cal, tune = is_cal, ~is_cal
    src = {s: load_source(s, space, len(dev)) for s in a.sources}
    rep = {"gate": a.gate, "sources": {}, "fused": {}}

    def evaluate(Pd, label):
        r = {}
        for h in FUSE_HEADS:
            near = sim[f"dev_{h}_top1sim"] >= a.gate
            r[h] = {"all": head_metrics(Pd[h][tune], yd[h][tune], h),
                    "novel": head_metrics(Pd[h][tune & ~near], yd[h][tune & ~near], h),
                    "near": head_metrics(Pd[h][tune & near], yd[h][tune & near], h)}
        for part in ("all", "novel", "near"):
            r[f"mean_main_f1_{part}"] = round(float(np.mean([r[h][part]["macro_f1"] for h in MAIN])), 4)
        y = yd["hp"][tune]
        r["hp_gate_dedicated"] = hp_threshold(Pd["hp"][tune][:, 1], y)
        r["hp_gate_incident_only"] = hp_threshold(Pd["type"][tune][:, space["type"].index("Incident")], y)
        print(f"{label:40s} all {r['mean_main_f1_all']:.4f}  novel {r['mean_main_f1_novel']:.4f}  "
              f"near {r['mean_main_f1_near']:.4f} | hp AP {r['hp']['all']['ap']:.3f} "
              f"flag@95 {r['hp_gate_dedicated']['flag_rate']:.3f} (incident-only {r['hp_gate_incident_only']['flag_rate']:.3f})",
              flush=True)
        return r

    for s, P in src.items():
        rep["sources"][s] = evaluate(P, s)

    # Similarity-gated log-linear fusion: separate weights for near / novel regimes, fit on dev_cal by NLL.
    fused, weights = {}, {}
    for h in FUSE_HEADS:
        logPs = [np.log(np.clip(src[s][h], 1e-9, 1)) for s in a.sources]
        near = sim[f"dev_{h}_top1sim"] >= a.gate
        P = np.zeros_like(src[a.sources[0]][h])
        weights[h] = {}
        for regime, m in (("near", near), ("novel", ~near)):
            y = np.where(cal & m, yd[h], -1)
            w = fit_weights(logPs, y)
            weights[h][regime] = dict(zip(a.sources, np.round(w, 3).tolist()))
            P[m] = pool([lp[m] for lp in logPs], w)
        fused[h] = P
    rep["fused"] = evaluate(fused, "FUSED(" + "+".join(a.sources) + ")")
    rep["fused"]["weights"] = weights
    dump(rep, f"{ROOT}/results/{a.name}.json")
    print(json.dumps(weights))


if __name__ == "__main__":
    main()
