"""Score every run x epoch (and the baseline sources) on the dev_tune 'far' slice: rows whose e5-small
top-1 similarity to base is < --far (no close precedent). This is our held-out generalization measure.

  python far_eval.py            # prints a table, writes results/far_eval.json
"""
import argparse
import glob
import json
import os

import numpy as np

from common import MAIN, ROOT, dump, head_metrics, label_space, load_kb, softmax, targets
from fuse import load_source


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--far", type=float, default=0.93)
    a = ap.parse_args()
    kb, base, dev, is_cal = load_kb()
    space = label_space(kb)
    yd = targets(dev, space)
    tune = ~is_cal
    sim = np.load(f"{ROOT}/probs/knn_e5-small.npz")
    far = {h: tune & (sim[f"dev_{h}_top1sim"] < a.far) for h in MAIN + ["hp"]}
    n = {h: int((far[h] & (yd[h] >= 0)).sum()) for h in MAIN + ["hp"]}

    def score(P):
        r = {h: head_metrics(P[h][far[h]], yd[h][far[h]], h)["macro_f1"] for h in MAIN}
        r["mean"] = round(float(np.mean([r[h] for h in MAIN])), 4)
        r["hp_ap"] = head_metrics(P["hp"][far["hp"]], yd["hp"][far["hp"]], "hp")["ap"]
        return r

    rows = []
    for s in ["tfidf", "knn_e5-small"] + [f"knn_ft_{os.path.basename(d)}" for d in sorted(glob.glob(f"{ROOT}/runs/*"))
                                           if os.path.exists(f"{ROOT}/probs/knn_ft_{os.path.basename(d)}.npz")]:
        rows.append({"source": s, **score(load_source(s, space, len(dev)))})
    for d in sorted(glob.glob(f"{ROOT}/runs/*")):
        rid = os.path.basename(d)
        for f in sorted(glob.glob(f"{d}/dev_logits_ep*.npz"), key=lambda x: int(x.split("ep")[-1][:-4])):
            z = np.load(f)
            P = {h: softmax(z[h]) for h in MAIN}
            p1 = 1 / (1 + np.exp(-z["hp"][:, 0]))
            P["hp"] = np.column_stack([1 - p1, p1])
            ep = int(f.split("ep")[-1][:-4])
            allm = float(np.mean([head_metrics(P[h][tune], yd[h][tune], h)["macro_f1"] for h in MAIN]))
            rows.append({"source": f"{rid}@ep{ep}", "dev_all_mean": round(allm, 4), **score(P)})
    print(f"far slice (top-1 < {a.far}) labelled rows: {n}")
    print(f"{'source':26s} {'far mean':>8s} {'type':>6s} {'queue':>6s} {'prio':>6s} {'hpAP':>6s} {'all-dev':>8s}")
    for r in rows:
        print(f"{r['source']:26s} {r['mean']:8.4f} {r['type']:6.3f} {r['queue']:6.3f} {r['priority']:6.3f} "
              f"{r['hp_ap']:6.3f} {r.get('dev_all_mean', float('nan')):8.4f}")
    dump({"far": a.far, "n": n, "rows": rows}, f"{ROOT}/results/far_eval.json")


if __name__ == "__main__":
    main()
