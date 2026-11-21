"""Box-side: apply the frozen decision (sources, weights, policy) to ALL official test inputs. No labels here.

  python make_test_preds.py --lb lb_final --ft ft:e5b_long --far 0.93
Writes probs/test_preds.npz: per system (tfidf, best ft head, fused, policy) the label probs + hp flag.
"""
import argparse
import json

import numpy as np

from common import MAIN, ROOT, label_space, load_kb, softmax
from fuse import FUSE_HEADS, pool
from policy import FAR_W


def load_test_source(name, space):
    if name == "tfidf":
        z = np.load(f"{ROOT}/probs/tfidf.npz", allow_pickle=True)  # our own file
        return {h: z[f"test_{h}"][:, [list(z[f"{h}_classes"]).index(str(c)) for c in space[h]]] for h in FUSE_HEADS}, z["test_ticket_id"]
    if name.startswith("knn_"):
        z = np.load(f"{ROOT}/probs/{name}.npz")
        return {h: z[f"test_{h}"] for h in FUSE_HEADS}, None
    if name.startswith("ft:"):
        z = np.load(f"{ROOT}/runs/{name[3:]}/test_logits.npz", allow_pickle=True)  # our own file
        out = {h: softmax(z[h]) for h in MAIN}
        p1 = 1 / (1 + np.exp(-z["hp"][:, 0]))
        out["hp"] = np.column_stack([1 - p1, p1])
        return out, z["ticket_id"]
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lb", required=True)
    ap.add_argument("--ft", required=True)
    ap.add_argument("--far", type=float, default=0.93)
    a = ap.parse_args()
    lb = json.load(open(f"{ROOT}/results/{a.lb}.json"))
    kb, _, _, _ = load_kb()
    space = label_space(kb)
    srcs = list(lb["sources"].keys())
    P, ids = {}, None
    for s in srcs:
        P[s], i = load_test_source(s, space)
        if i is not None:
            assert ids is None or (ids == i).all(), "test row order mismatch"
            ids = i
    sim = np.load(f"{ROOT}/probs/knn_e5-small.npz")
    W = lb["fused"]["weights"]
    fused, policy = {}, {}
    for h in FUSE_HEADS:
        top1 = sim[f"test_{h}_top1sim"]
        near = top1 >= lb["gate"]
        f = np.zeros_like(P[srcs[0]][h])
        for regime, m in (("near", near), ("novel", ~near)):
            f[m] = pool([np.log(np.clip(P[s][h][m], 1e-9, 1)) for s in srcs], [W[h][regime][s] for s in srcs])
        fused[h] = f
        pol = f.copy()
        far = top1 < a.far
        kft = [s for s in srcs if s.startswith("knn_ft_")][0]
        if h == "hp":
            pol[far] = P[a.ft][h][far]
        elif far.any():
            pol[far] = pool([np.log(np.clip(P[kft][h][far], 1e-9, 1)), np.log(np.clip(P[a.ft][h][far], 1e-9, 1))], [FAR_W, 1 - FAR_W])
        policy[h] = pol
    pol_rep = json.load(open(f"{ROOT}/results/policy_{a.lb}.json"))
    out = {"ticket_id": np.asarray(ids).astype("U9"), "classes_json": json.dumps({h: [str(c) for c in space[h]] for h in FUSE_HEADS})}
    taus = {"tfidf": lb["sources"]["tfidf"]["hp_gate_dedicated"]["tau"],
            a.ft: lb["sources"][a.ft]["hp_gate_dedicated"]["tau"],
            "fused": lb["fused"]["hp_gate_dedicated"]["tau"],
            "policy": json.load(open(f"{ROOT}/artifacts/bundle/config.json"))["hp_tau"]}  # served threshold
    for name, Ps in (("tfidf", P["tfidf"]), (a.ft, P[a.ft]), ("fused", fused), ("policy", policy)):
        key = name.replace(":", "_")
        for h in FUSE_HEADS:
            out[f"{key}|{h}"] = Ps[h].astype(np.float32)
        out[f"{key}|hp_flag"] = Ps["hp"][:, 1] >= taus[name]
    out["taus_json"] = json.dumps(taus)
    out["policy_note"] = json.dumps({"far": a.far, "gate": lb["gate"], "dev_policy_results": pol_rep})
    np.savez_compressed(f"{ROOT}/probs/test_preds.npz", **out)
    print("wrote test_preds.npz", len(ids), "rows; systems:", [k.split("|")[0] for k in out if k.endswith("|type")])


if __name__ == "__main__":
    main()
