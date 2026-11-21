"""kNN baseline + Bayes-error (ceiling) estimate, using the same TF-IDF features as the LR heads.

  1. On dev_tune (no test data): k-NN label vote over base for k in {1,5,10,25,50}; pick k per head.
     Cover-Hart bound from the 1-NN error, plus a 1-NN learning curve (10/25/50/100% of base).
  2. Once, on test: kNN with the chosen k, on the clean and the full official test set.
     (Step 2 reads test labels, so like eval.py this is evaluation-only code.)

Run from the repo root after train.py:  python3 triage/knn_eval.py
Writes triage/reports/knn_report.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from model import TriageModel  # noqa: E402

DATA = "dataset/data"
KS = [1, 5, 10, 25, 50]
FRACS = [0.1, 0.25, 0.5, 1.0]


def targets(df):
    typed = df["type"].notna().to_numpy()
    return {
        "type": (typed, df["type"].to_numpy()),
        "queue": (df["queue_core"].to_numpy(), df["queue"].to_numpy()),
        "priority": (np.ones(len(df), bool), df["priority"].to_numpy()),
    }


def topk_neighbors(Xq, Xb, cols, kmax, chunk=400):
    """Indices (into cols) and sims of the kmax most similar base rows, restricted to `cols`."""
    Xb = Xb[cols]
    idx = np.empty((Xq.shape[0], kmax), dtype=np.int64)
    sim = np.empty((Xq.shape[0], kmax), dtype=np.float32)
    for s in range(0, Xq.shape[0], chunk):
        S = (Xq[s:s + chunk] @ Xb.T).toarray()
        part = np.argpartition(-S, kmax, axis=1)[:, :kmax]
        ps = np.take_along_axis(S, part, 1)
        order = np.argsort(-ps, axis=1)
        idx[s:s + chunk] = np.take_along_axis(part, order, 1)
        sim[s:s + chunk] = np.take_along_axis(ps, order, 1)
    return idx, sim


def vote(nb_labels, nb_sims, k):
    """Similarity-weighted vote over the top k neighbours (k=1: plain 1-NN)."""
    out = []
    for labs, sims in zip(nb_labels[:, :k], nb_sims[:, :k]):
        acc = {}
        for l, w in zip(labs, sims):
            acc[l] = acc.get(l, 0.0) + float(w)
        out.append(max(acc, key=acc.get))
    return np.array(out, dtype=object)


def cover_hart(r_nn, K):
    """Asymptotic bounds on the Bayes error R* from the 1-NN error: lower <= R* <= r_nn."""
    a = K / (K - 1)
    lower = (1 / a) * (1 - np.sqrt(max(0.0, 1 - a * r_nn)))
    return float(lower), float(r_nn)


def main():
    tm = TriageModel.load(f"{HERE}/models/triage.joblib")
    kb = pd.read_parquet(f"{DATA}/kb_train.parquet",
                         columns=["ticket_id", "text", "type", "queue", "queue_core", "priority", "split"])
    base = kb[kb["split"] == "base"].reset_index(drop=True)
    dev = kb[kb["split"] == "dev"].reset_index(drop=True)
    is_cal = np.random.default_rng(11).random(len(dev)) < 0.5  # same split as train.py
    dev_tune = dev[~is_cal].reset_index(drop=True)
    print(f"base {len(base):,} dev_tune {len(dev_tune):,}", flush=True)

    Xb = tm.transform(base["text"]).tocsr()
    Xt = tm.transform(dev_tune["text"]).tocsr()
    Tb, Tt = targets(base), targets(dev_tune)
    rng = np.random.default_rng(0)
    report = {"dev_tune": {}, "test": {}}
    best_k = {}

    for head in ["type", "queue", "priority"]:
        mb, yb = Tb[head]
        mt, yt = Tt[head]
        cols = np.where(mb)[0]
        idx, sim = topk_neighbors(Xt[mt], Xb, cols, max(KS))
        labs = yb[cols][idx]
        y = yt[mt]
        K = len(np.unique(yb[cols]))
        r = {"n": int(mt.sum()), "n_classes": K, "by_k": {}}
        for k in KS:
            p = vote(labs, sim, k)
            r["by_k"][k] = {"macro_f1": round(f1_score(y, p, average="macro"), 4),
                            "accuracy": round(float((p == y).mean()), 4)}
        best_k[head] = max(KS, key=lambda k: r["by_k"][k]["macro_f1"])
        r["best_k"] = best_k[head]
        r_nn = 1 - r["by_k"][1]["accuracy"]
        lo, hi = cover_hart(r_nn, K)
        r["cover_hart"] = {"one_nn_error": round(r_nn, 4), "bayes_error_lower": round(lo, 4),
                           "bayes_error_upper": round(hi, 4),
                           "max_accuracy_upper_bound": round(1 - lo, 4),
                           "note": "asymptotic, within this TF-IDF representation only"}
        # 1-NN learning curve: does the NN error keep falling with more data?
        curve = {}
        for f in FRACS:
            sub = cols if f == 1.0 else np.sort(rng.choice(cols, int(len(cols) * f), replace=False))
            i1, _ = topk_neighbors(Xt[mt], Xb, sub, 1)
            curve[f] = round(float((yb[sub][i1[:, 0]] != y).mean()), 4)
        r["one_nn_error_curve"] = curve
        report["dev_tune"][head] = r
        print(f"{head:9s} K={K:<3} " + "  ".join(f"k={k}: F1 {v['macro_f1']:.3f}/acc {v['accuracy']:.3f}"
                                               for k, v in r["by_k"].items()), flush=True)
        print(f"          1-NN err {r_nn:.3f} -> Bayes error in [{lo:.3f}, {hi:.3f}] "
              f"(accuracy ceiling <= {1 - lo:.3f});  1-NN error vs data fraction {curve}", flush=True)

    # ---- one-shot test evaluation with the chosen k ----
    sets = {
        "clean_test": (pd.read_parquet(f"{DATA}/test_inputs.parquet"), pd.read_parquet(f"{DATA}/test_labels.parquet")),
    }
    ai = pd.read_parquet(f"{DATA}/test_inputs_all.parquet")
    ai = ai[ai["eval_subset"] != "empty_body"].reset_index(drop=True)
    al = pd.read_parquet(f"{DATA}/test_labels_all.parquet").set_index("ticket_id").loc[ai["ticket_id"]].reset_index()
    sets["full_official_test"] = (ai, al)
    for name, (inp, lab) in sets.items():
        Xq = tm.transform(inp["text"]).tocsr()
        Tq = targets(lab)
        res = {"n": len(inp)}
        for head in ["type", "queue", "priority"]:
            mb, yb = Tb[head]
            mq, yq = Tq[head]
            cols = np.where(mb)[0]
            k = best_k[head]
            idx, sim = topk_neighbors(Xq[mq], Xb, cols, k)
            p = vote(yb[cols][idx], sim, k)
            res[head] = {"k": k, "macro_f1": round(f1_score(yq[mq], p, average="macro"), 4),
                         "accuracy": round(float((p == yq[mq]).mean()), 4)}
            if "eval_subset" in inp:
                sub = inp["eval_subset"].to_numpy()[mq]
                res[head]["accuracy_by_eval_subset"] = {
                    s: round(float((p[sub == s] == yq[mq][sub == s]).mean()), 4) for s in np.unique(sub)}
        report["test"][name] = res
        print(f"\n== kNN {name} (n={len(inp):,})", flush=True)
        for head in ["type", "queue", "priority"]:
            print(f"  {head:9s} k={res[head]['k']:<3} macroF1 {res[head]['macro_f1']:.3f}  acc {res[head]['accuracy']:.3f}"
                  + (f"  by subset {res[head]['accuracy_by_eval_subset']}" if "accuracy_by_eval_subset" in res[head] else ""))

    with open(f"{HERE}/reports/knn_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)


if __name__ == "__main__":
    main()
