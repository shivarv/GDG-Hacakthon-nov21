"""Serving policy on top of the fused blend, evaluated on dev_tune and on the hand-written novel tickets.

  far regime: e5-small top-1 sim < --far  ->  0.7 kNN(fine-tuned emb) + 0.3 fine-tuned head (log-linear); HP from the head
  HP flag:    fused hp >= tau_fused  OR  ft hp >= tau_ft   (taus fitted on dev_tune at 95% recall, as before)
"""
import argparse
import json

import numpy as np

from common import MAIN, ROOT, dump, head_metrics, hp_threshold, label_space, load_kb, targets
from fuse import FUSE_HEADS, load_source, pool

FAR_W = 0.7  # kNN-on-fine-tuned-embeddings weight in the far regime (neighbour-removed sweep: 0.5-1.0 flat, 0.7 best)


def apply(P, top1, lb, ft, far, gate):
    W = lb["fused"]["weights"]
    srcs = list(lb["sources"].keys())
    out = {}
    for h in FUSE_HEADS:
        res = np.zeros_like(P[srcs[0]][h])
        near = top1[h] >= gate
        for regime, m in (("near", near), ("novel", ~near)):
            if m.any():
                res[m] = pool([np.log(np.clip(P[s][h][m], 1e-9, 1)) for s in srcs], [W[h][regime][s] for s in srcs])
        if far is not None:
            f = top1[h] < far
            kft = [s for s in srcs if s.startswith("knn_ft_")][0]
            if h == "hp":
                res[f] = P[ft][h][f]  # kNN HP votes are unreliable far from the kb
            elif f.any():
                res[f] = pool([np.log(np.clip(P[kft][h][f], 1e-9, 1)), np.log(np.clip(P[ft][h][f], 1e-9, 1))], [FAR_W, 1 - FAR_W])
        out[h] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lb", required=True)
    ap.add_argument("--ft", required=True, help="e.g. ft:e5b_s13")
    ap.add_argument("--far", type=float, default=0.93)
    a = ap.parse_args()
    lb = json.load(open(f"{ROOT}/results/{a.lb}.json"))
    kb, base, dev, is_cal = load_kb()
    space = label_space(kb)
    yd = targets(dev, space)
    tune = ~is_cal
    simz = np.load(f"{ROOT}/probs/knn_e5-small.npz")
    Pd = {s: load_source(s, space, len(dev)) for s in lb["sources"]}
    top1d = {h: simz[f"dev_{h}_top1sim"] for h in FUSE_HEADS}
    nz = np.load(f"{ROOT}/probs/novel_{a.lb}.npz")
    Pn = {s: {h: nz[f"{s}|{h}"] for h in FUSE_HEADS} for s in lb["sources"]}
    top1n = {h: nz[f"top1|{h}"] for h in FUSE_HEADS}
    rows = [json.loads(l) for l in open(f"{ROOT}/code/robust/novel_tickets.jsonl")]
    insc = [i for i, r in enumerate(rows) if not r["ood"]]
    hpr = [i for i, r in enumerate(rows) if r["hp_expected"]]
    rep = {}
    for far in (None, a.far):
        for hp_or in (False, True):
            name = f"far={far} hp_or={hp_or}"
            D = apply(Pd, top1d, lb, a.ft, far, lb["gate"])
            N = apply(Pn, top1n, lb, a.ft, far, lb["gate"])
            y = yd["hp"][tune]
            g = hp_threshold(D["hp"][tune][:, 1], y)
            flag_d = D["hp"][tune][:, 1] >= g["tau"]
            flag_n = N["hp"][:, 1] >= g["tau"]
            if hp_or:
                g2 = hp_threshold(Pd[a.ft]["hp"][tune][:, 1], y)
                flag_d |= Pd[a.ft]["hp"][tune][:, 1] >= g2["tau"]
                flag_n |= Pn[a.ft]["hp"][:, 1] >= g2["tau"]
            pos = y == 1
            r = {"dev_mean_main_f1": round(float(np.mean([head_metrics(D[h][tune], yd[h][tune], h)["macro_f1"] for h in MAIN])), 4),
                 "dev_hp_recall": round(float(flag_d[pos].mean()), 4), "dev_hp_flag_rate": round(float(flag_d.mean()), 4),
                 "dev_far_share": round(float((top1d["type"][tune] < far).mean()), 4) if far else 0.0}
            lab = {h: [space[h][j] for j in N[h].argmax(1)] for h in MAIN}
            r |= {"novel_type_acc": round(float(np.mean([lab["type"][i] == rows[i]["type"] for i in insc])), 3),
                  "novel_queue_in_set": round(float(np.mean([lab["queue"][i] in rows[i]["queue_ok"] for i in insc])), 3),
                  "novel_priority_in_set": round(float(np.mean([lab["priority"][i] in rows[i]["priority_ok"] for i in insc])), 3),
                  "novel_hp_recall": round(float(np.mean([flag_n[i] for i in hpr])), 3),
                  "novel_false_flag_rate": round(float(np.mean([flag_n[i] for i in insc if not rows[i]["hp_expected"]])), 3)}
            rep[name] = r
            print(f"{name:28s}", r, flush=True)
    dump(rep, f"{ROOT}/results/policy_{a.lb}.json")


if __name__ == "__main__":
    main()
