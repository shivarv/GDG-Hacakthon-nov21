"""Evidence for the "ticket families" finding: family clustering, family-held-out evaluation, figures.

Uses ONLY the 80% kb split (kb_train.parquet) for clustering and the held-out experiments; the existing
test-set numbers are read from triage/reports/*.json (already computed once by eval.py / knn_eval.py).

Run from the repo root (uses all CPU cores):  python3 findings/analyze.py
Outputs: findings/out/*.png, findings/out/findings.json, findings/out/families.parquet
"""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "triage"))
OUT = os.path.join(ROOT, "findings", "out")
REP = os.path.join(ROOT, "triage", "reports")
NCPU = os.cpu_count() or 8
CORE_Q = None

_X = _XT = None  # shared with forked workers


def _nb_chunk(args):
    s, e, k = args
    S = (_X[s:e] @ _XT).toarray() / 2.0  # FeatureUnion of 2 L2-normalized blocks -> cosine = dot / 2
    for i in range(e - s):
        S[i, s + i] = -1.0  # drop self
    part = np.argpartition(-S, k, axis=1)[:, :k]
    sims = np.take_along_axis(S, part, 1)
    return s, part.astype(np.int32), sims.astype(np.float32)


def neighbours(X, k=10, chunk=400):
    global _X, _XT
    _X, _XT = X, X.T.tocsc()
    jobs = [(s, min(s + chunk, X.shape[0]), k) for s in range(0, X.shape[0], chunk)]
    idx = np.empty((X.shape[0], k), np.int32)
    sim = np.empty((X.shape[0], k), np.float32)
    with mp.get_context("fork").Pool(NCPU) as pool:
        for s, p, v in pool.imap_unordered(_nb_chunk, jobs):
            idx[s:s + len(p)], sim[s:s + len(p)] = p, v
    return idx, sim


def families(idx, sim, thr):
    n = idx.shape[0]
    m = sim >= thr
    rows = np.repeat(np.arange(n), idx.shape[1])[m.ravel()]
    cols = idx.ravel()[m.ravel()]
    G = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, lab = connected_components(G, directed=False)
    return lab


# ---------------- held-out experiment (one task = one split x one head) ----------------
def _run_task(args):
    split_name, head, train_idx, hold_idx, blend_params = args
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from train import make_features
    kb = _KB
    tr, ho = kb.iloc[train_idx], kb.iloc[hold_idx]
    col = {"type": "type", "queue": "queue", "priority": "priority"}[head]
    if head == "type":
        mtr, mho = tr["type"].notna().to_numpy(), ho["type"].notna().to_numpy()
    elif head == "queue":
        mtr, mho = tr["queue_core"].to_numpy(), ho["queue_core"].to_numpy()
    else:
        mtr, mho = np.ones(len(tr), bool), np.ones(len(ho), bool)
    tr, ho = tr[mtr], ho[mho]
    feats = make_features()
    Xtr = feats.fit_transform(tr["text"]).tocsr()
    Xho = feats.transform(ho["text"]).tocsr()
    ytr, yho = tr[col].to_numpy(), ho[col].to_numpy()
    C = {"type": 8.0, "queue": 32.0, "priority": 32.0}[head]
    lr = LogisticRegression(C=C, class_weight="balanced", solver="saga", max_iter=50, tol=1e-3,
                            random_state=0).fit(Xtr, ytr)
    P_lr = lr.predict_proba(Xho)
    cls = list(lr.classes_)
    ytr_idx = np.array([cls.index(v) for v in ytr])
    # kNN neighbours of held-out rows among train rows
    XT = Xtr.T.tocsc()
    K = 50
    nb = np.empty((Xho.shape[0], K), np.int64)
    sv = np.empty((Xho.shape[0], K), np.float32)
    for s in range(0, Xho.shape[0], 500):
        S = (Xho[s:s + 500] @ XT).toarray()
        part = np.argpartition(-S, K, axis=1)[:, :K]
        ps = np.take_along_axis(S, part, 1)
        o = np.argsort(-ps, axis=1)
        nb[s:s + 500], sv[s:s + 500] = np.take_along_axis(part, o, 1), np.take_along_axis(ps, o, 1)
    nb_y = ytr_idx[nb]
    p1 = np.array(cls)[nb_y[:, 0]]
    bp = blend_params[head]
    k, beta, alpha = bp["k"], bp["beta"], bp["alpha"]
    w = np.exp(beta * (sv[:, :k] - sv[:, :1]))
    Pk = np.zeros_like(P_lr)
    np.add.at(Pk, (np.repeat(np.arange(len(nb_y)), k), nb_y[:, :k].ravel()), w.ravel())
    Pk /= Pk.sum(1, keepdims=True)
    pb = np.array(cls)[((1 - alpha) * P_lr + alpha * Pk).argmax(1)]
    pl = np.array(cls)[P_lr.argmax(1)]
    res = {}
    for name, p in (("lr", pl), ("knn1", p1), ("blend", pb)):
        res[name] = {"macro_f1": round(float(f1_score(yho, p, average="macro")), 4),
                     "accuracy": round(float((p == yho).mean()), 4)}
    res["n_train"], res["n_holdout"] = int(len(tr)), int(len(ho))
    res["top1_sim_median"] = round(float(np.median(sv[:, 0]) / 2), 4)
    return split_name, head, res


_KB = None


def main():
    global _KB
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    from model import TriageModel
    tm = TriageModel.load(os.path.join(ROOT, "triage", "models", "triage.joblib"))
    kb = pd.read_parquet(os.path.join(ROOT, "dataset", "data", "kb_train.parquet"),
                         columns=["ticket_id", "subject", "body", "text", "type", "queue", "queue_core",
                                  "priority", "language", "split", "n_copies", "tags"])
    kb = kb.reset_index(drop=True)
    _KB = kb
    X = tm.transform(kb["text"]).tocsr()
    print(f"[{time.time() - t0:.0f}s] features {X.shape}", flush=True)
    idx, sim = neighbours(X, k=10)
    print(f"[{time.time() - t0:.0f}s] 10-NN graph done", flush=True)

    # families: connected components of the 10-NN graph above a cosine threshold, avoiding a giant component
    fam_info = {}
    for thr in (0.70, 0.75, 0.80, 0.85):
        lab = families(idx, sim, thr)
        sizes = np.bincount(lab)
        fam_info[thr] = {"n_families": int(len(sizes)), "largest_share": round(float(sizes.max() / len(lab)), 4),
                         "singletons_share": round(float((sizes[lab] == 1).mean()), 4),
                         "rows_in_families_ge5": round(float((sizes[lab] >= 5).mean()), 4)}
        print(f"  thr {thr}: {fam_info[thr]}", flush=True)
    thr = next((t for t in (0.70, 0.75, 0.80, 0.85) if fam_info[t]["largest_share"] <= 0.05), 0.85)
    lab = families(idx, sim, thr)
    kb["family"] = lab
    sizes = np.bincount(lab)
    kb["family_size"] = sizes[lab]
    kb[["ticket_id", "family", "family_size"]].to_parquet(os.path.join(OUT, "families.parquet"), index=False)

    # label agreement within families vs random pairs
    rng = np.random.default_rng(0)
    agree = {}
    multi = kb[kb["family_size"] >= 2]
    g = multi.groupby("family")
    pairs_i, pairs_j = [], []
    for _, rows in g.indices.items():
        if len(rows) >= 2:
            a, b = rng.choice(rows, 2, replace=False)
            pairs_i.append(a)
            pairs_j.append(b)
    pi, pj = multi.index.to_numpy()[pairs_i], multi.index.to_numpy()[pairs_j]
    ri, rj = rng.integers(0, len(kb), len(pi)), rng.integers(0, len(kb), len(pi))
    for col in ("type", "queue", "priority", "language"):
        a, b = kb[col].to_numpy(), kb[col].to_numpy()
        ok = pd.notna(a[pi]) & pd.notna(b[pj])
        okr = pd.notna(a[ri]) & pd.notna(b[rj])
        agree[col] = {"within_family": round(float((a[pi][ok] == b[pj][ok]).mean()), 4),
                      "random_pairs": round(float((a[ri][okr] == b[rj][okr]).mean()), 4)}
    # cross-language families
    lang_mix = g["language"].nunique()
    agree["families_with_both_en_and_de"] = round(float((lang_mix > 1).mean()), 4)
    print("label agreement:", agree, flush=True)

    # ---- held-out experiment: random 15% vs family-held-out 15% (both inside kb) ----
    n = len(kb)
    rand_hold = rng.random(n) < 0.15
    fam_ids = np.unique(lab)
    held_fams = set(rng.choice(fam_ids, int(len(fam_ids) * 0.15), replace=False))
    fam_hold = np.isin(lab, list(held_fams))
    with open(os.path.join(REP, "blend_dev_report.json")) as f:
        bparams = {h: v["params"] for h, v in json.load(f)["heads"].items()}
    tasks = []
    for name, hold in (("random_split", rand_hold), ("family_held_out", fam_hold)):
        for head in ("type", "queue", "priority"):
            tasks.append((name, head, np.where(~hold)[0], np.where(hold)[0], bparams))
    with mp.get_context("fork").Pool(len(tasks)) as pool:
        out = pool.map(_run_task, tasks)
    heldout = {}
    for name, head, res in out:
        heldout.setdefault(name, {})[head] = res
    print(f"[{time.time() - t0:.0f}s] held-out:", json.dumps(heldout), flush=True)

    # an example family with both languages and >= 5 members, for the slide
    cand = g.filter(lambda d: len(d) >= 5 and d["language"].nunique() > 1)
    ex_fam = cand["family"].value_counts().index[0] if len(cand) else int(np.argmax(sizes))
    ex = kb[kb["family"] == ex_fam].head(8)[["ticket_id", "language", "type", "queue", "priority", "subject", "body"]]
    example = ex.assign(body=ex["body"].str.slice(0, 220)).to_dict(orient="records")

    res = {"threshold_used": thr, "family_thresholds": {str(k): v for k, v in fam_info.items()},
           "family_size_hist": {str(k): int(v) for k, v in
                                pd.Series(sizes).value_counts().sort_index().head(40).items()},
           "label_agreement": agree, "heldout": heldout, "example_family": example,
           "secs": round(time.time() - t0)}
    with open(os.path.join(OUT, "findings.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)

    # ---- 2D map sample: 30 largest multi-language-or-not families (+ random singletons) ----
    from sklearn.decomposition import TruncatedSVD
    from sklearn.manifold import TSNE
    big = pd.Series(sizes).sort_values(ascending=False)
    top = big.index[(big.values >= 8)][:60]
    samp = kb[kb["family"].isin(top) & kb["queue_core"]]
    samp = pd.concat([samp, kb[kb["queue_core"] & ~kb["family"].isin(top)].sample(3000, random_state=0)])
    Z = TruncatedSVD(80, random_state=0).fit_transform(X[samp.index.to_numpy()])
    Y = TSNE(2, init="pca", perplexity=30, random_state=0, n_jobs=NCPU).fit_transform(Z)
    samp = samp.assign(x=Y[:, 0], y=Y[:, 1], in_top=samp["family"].isin(top))
    samp[["ticket_id", "family", "queue", "priority", "language", "x", "y", "in_top"]].to_parquet(
        os.path.join(OUT, "map2d.parquet"), index=False)
    print(f"[{time.time() - t0:.0f}s] done", flush=True)


if __name__ == "__main__":
    main()
