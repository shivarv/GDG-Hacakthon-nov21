"""kNN label vote on frozen (or fine-tuned) embeddings. Dev rows search base only; test rows search base+dev.

Picks (k, tau) per head on dev_cal, reports dev_tune, and a 1-NN accuracy-by-similarity table
(how much of the score is near-paraphrase memorization). Writes probs/knn_<name>.npz + results/knn_<name>.json.
"""
import argparse

import numpy as np
import pandas as pd
import torch

from common import HEADS, MAIN, ROOT, dump, head_metrics, label_space, load_kb, targets

KS = [1, 3, 5, 10, 25]
TAUS = [0.01, 0.03, 0.1]
EPS = 0.02  # probability floor mixed in so 1-NN votes aren't 0/1


def vote(sims, nbr_lab, k, tau, n_cls):
    w = torch.exp((sims[:, :k] - sims[:, :1]) / tau)  # relative to top-1, numerically safe
    P = torch.zeros(sims.shape[0], n_cls, device=sims.device)
    P.scatter_add_(1, nbr_lab[:, :k], w)
    P = P / P.sum(1, keepdim=True)
    return (1 - EPS) * P + EPS / n_cls


def topk(Q, B, k=25, chunk=2048):
    S, I = [], []
    for i in range(0, len(Q), chunk):
        s, j = (Q[i:i + chunk] @ B.T).topk(k, dim=1)
        S.append(s); I.append(j)
    return torch.cat(S), torch.cat(I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", default="e5-small")
    ap.add_argument("--exclude", default="", help="parquet of base ticket_ids to remove from the index")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    kb, base, dev, is_cal = load_kb()
    space = label_space(kb)
    E = np.load(f"{ROOT}/emb/{a.emb}/kb_emb.npy")
    ids = pd.read_parquet(f"{ROOT}/emb/{a.emb}/kb_ids.parquet")
    assert (ids["ticket_id"].to_numpy() == kb["ticket_id"].to_numpy()).all()
    E = torch.from_numpy(E).cuda()
    is_base = torch.from_numpy((kb["split"] == "base").to_numpy()).cuda()
    Eb, Ed = E[is_base], E[~is_base]
    Et = torch.from_numpy(np.load(f"{ROOT}/emb/{a.emb}/test_emb.npy")).cuda()
    yb, yd = targets(base, space), targets(dev, space)
    if a.exclude:
        drop = base["ticket_id"].isin(set(pd.read_parquet(a.exclude)["ticket_id"])).to_numpy()
        for h in yb:
            yb[h] = np.where(drop, -1, yb[h])  # masked rows never enter the index
    ykb = targets(kb, space)
    cal, tune = is_cal, ~is_cal
    out, rep = {}, {"emb": a.emb, "heads": {}}
    for h in HEADS:
        n_cls = len(space[h])
        lab_b = torch.from_numpy(yb[h]).cuda()
        ok = lab_b >= 0
        Bh, Lh = Eb[ok], lab_b[ok]
        S, I = topk(Ed, Bh)
        NL = Lh[I]
        best = None
        for k in KS:
            for tau in TAUS:
                P = vote(S, NL, k, tau, n_cls).cpu().numpy()
                m = head_metrics(P[cal], yd[h][cal], h)
                key = m["ap"] if h == "hp" else m["macro_f1"]
                if best is None or key > best[0]:
                    best = (key, k, tau, P)
        _, k, tau, P = best
        rep["heads"][h] = {"k": k, "tau": tau, "dev_tune": head_metrics(P[tune], yd[h][tune], h)}
        out[f"dev_{h}"] = P.astype(np.float32)
        out[f"dev_{h}_top1sim"] = S[:, 0].cpu().numpy()
        # 1-NN accuracy by similarity bucket on dev_tune (main heads)
        if h in MAIN:
            s1 = S[:, 0].cpu().numpy()
            pred = NL[:, 0].cpu().numpy()
            y = yd[h]
            m = tune & (y >= 0)
            edges = [0, 0.85, 0.9, 0.93, 0.95, 0.97, 1.01]
            rep["heads"][h]["nn1_by_sim"] = [
                {"sim": f"{lo:.2f}-{hi:.2f}", "share": round(float((m & (s1 >= lo) & (s1 < hi)).sum() / m.sum()), 3),
                 "acc": round(float((pred == y)[m & (s1 >= lo) & (s1 < hi)].mean()), 3)
                 if (m & (s1 >= lo) & (s1 < hi)).any() else None}
                for lo, hi in zip(edges[:-1], edges[1:])]
        # test: search base+dev with the chosen k, tau
        lab_kb = torch.from_numpy(ykb[h]).cuda()
        okk = lab_kb >= 0
        St, It = topk(Et, E[okk])
        out[f"test_{h}"] = vote(St, lab_kb[okk][It], k, tau, n_cls).cpu().numpy().astype(np.float32)
        out[f"test_{h}_top1sim"] = St[:, 0].cpu().numpy()
        print(h, rep["heads"][h], flush=True)
    rep["dev_tune_mean_main_f1"] = round(float(np.mean([rep["heads"][h]["dev_tune"]["macro_f1"] for h in MAIN])), 4)
    np.savez_compressed(f"{ROOT}/probs/knn_{a.emb}{a.tag}.npz", **out)
    dump(rep, f"{ROOT}/results/knn_{a.emb}{a.tag}.json")
    print("mean main F1 (dev_tune):", rep["dev_tune_mean_main_f1"])


if __name__ == "__main__":
    main()
