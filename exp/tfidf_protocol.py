"""TF-IDF + LR (same features/C as triage/train.py's chosen values) on the neighbour-removed base; scores dev_tune."""
import sys, numpy as np, pandas as pd
from joblib import Parallel, delayed
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion
from common import MAIN, ROOT, dump, head_metrics, label_space, load_kb, targets
kb, base, dev, is_cal = load_kb(); space = label_space(kb)
drop = set(pd.read_parquet(sys.argv[1])["ticket_id"]); base = base[~base.ticket_id.isin(drop)].reset_index(drop=True)
fu = FeatureUnion([("w", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=150000, sublinear_tf=True, dtype=np.float32)),
                   ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, max_features=250000, sublinear_tf=True, dtype=np.float32))])
Xb = fu.fit_transform(base.text); Xd = fu.transform(dev.text)
yb, yd = targets(base, space), targets(dev, space); tune = ~is_cal
Cs = {"type": 8, "queue": 32, "priority": 32}
def fit(h):
    m = yb[h] >= 0
    return h, LogisticRegression(C=Cs[h], class_weight="balanced", solver="saga", max_iter=50, tol=1e-3).fit(Xb[m], yb[h][m])
res = {}
for h, lr in Parallel(n_jobs=3)(delayed(fit)(h) for h in MAIN):
    P = np.zeros((len(dev), len(space[h]))); P[:, lr.classes_] = lr.predict_proba(Xd)
    res[h] = head_metrics(P[tune], yd[h][tune], h)["macro_f1"]
res["mean"] = round(float(np.mean([res[h] for h in MAIN])), 4)
print("tfidf protocol", len(base), res); dump(res, f"{ROOT}/results/protocol_tfidf.json")
