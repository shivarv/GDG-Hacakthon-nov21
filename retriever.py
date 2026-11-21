"""
SentinelDesk retriever: FAISS search over historical tickets.

Follows dataset/README.md:
- Index only rows with has_answer
- Tune the similarity threshold on dev, searching the base-only index
- Live demo uses the base + dev index ("all")
- Skip a hit whose similarity to an already-picked hit is >= 0.95 (diverse top-k)

Needs in data/:  kb_base.index, kb_base_ids.parquet, kb_all.index, kb_all_ids.parquet
Run from the repo root:  python retriever.py
  -> tunes the threshold on dev, saves data/retriever_config.json, runs a few demo queries

Use in the app:
  from retriever import retrieve, load_threshold
  hits = retrieve("VPN is down", k=5)          # list of dicts
  no_precedent = hits[0]["score"] < load_threshold()
"""
import json
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

DATA = "data"
KB_PATH = "dataset/data/kb_train.parquet"
CONFIG = f"{DATA}/retriever_config.json"
MODEL = "intfloat/multilingual-e5-small"
MAX_SEQ = 256        # must match the setting used when building the index
DEDUP_SIM = 0.95     # skip near-identical hits
DEFAULT_THRESHOLD = 0.85

# Clearly out-of-scope probes (EN + DE) used to sanity-check the threshold
OUT_OF_SCOPE = [
    "What is the best pizza recipe?",
    "Write me a poem about the ocean.",
    "Who won the football game yesterday?",
    "Can you recommend a good movie for tonight?",
    "Wie wird das Wetter morgen in Berlin?",
    "Was ist das beste Rezept für Apfelkuchen?",
]

_cache = {}


def _embedder():
    if "emb" not in _cache:
        m = SentenceTransformer(MODEL)
        m.max_seq_length = MAX_SEQ
        _cache["emb"] = m
    return _cache["emb"]


def _kb():
    if "kb" not in _cache:
        _cache["kb"] = pd.read_parquet(KB_PATH).set_index("ticket_id")
    return _cache["kb"]


def _index(which):
    key = f"idx_{which}"
    if key not in _cache:
        idx = faiss.read_index(f"{DATA}/kb_{which}.index")
        ids = pd.read_parquet(f"{DATA}/kb_{which}_ids.parquet")["ticket_id"].tolist()
        assert idx.ntotal == len(ids), "index and ids file do not match"
        _cache[key] = (idx, ids)
    return _cache[key]


def encode_queries(texts):
    return _embedder().encode(["query: " + t for t in texts], batch_size=64,
                              normalize_embeddings=True,
                              show_progress_bar=False).astype("float32")


def _clean(x):
    return x if isinstance(x, str) else ""


def retrieve(text, k=5, which="all"):
    """Top-k most similar historical tickets, skipping near-identical hits."""
    idx, ids = _index(which)
    scores, pos = idx.search(encode_queries([text]), k * 4)
    kb = _kb()
    hits, picked_vecs = [], []
    for s, p in zip(scores[0], pos[0]):
        if p < 0:
            continue
        v = idx.reconstruct(int(p))
        if any(float(v @ pv) >= DEDUP_SIM for pv in picked_vecs):
            continue
        tid = ids[p]
        r = kb.loc[tid]
        hits.append({
            "ticket_id": tid,
            "score": round(float(s), 3),
            "subject": _clean(r.get("subject")),
            "answer": _clean(r.get("answer")),
            "language": _clean(r.get("language")),
            "queue": _clean(r.get("queue")),
        })
        picked_vecs.append(v)
        if len(hits) == k:
            break
    return hits


def load_threshold():
    try:
        with open(CONFIG) as f:
            return json.load(f)["sim_threshold"]
    except (FileNotFoundError, KeyError):
        return DEFAULT_THRESHOLD


def tune(n_dev=500, seed=0):
    """Pick the similarity threshold on dev queries against the base-only index."""
    kb = _kb().reset_index()
    dev = kb[kb["split"] == "dev"]
    dev = dev.sample(min(n_dev, len(dev)), random_state=seed)
    idx, ids = _index("base")

    print(f"Encoding {len(dev)} dev queries...", flush=True)
    scores, pos = idx.search(encode_queries(dev["text"].fillna("").tolist()), 1)
    top1 = scores[:, 0]
    print("\nDev top-1 similarity:")
    print(pd.Series(top1).describe(percentiles=[0.01, 0.05, 0.1, 0.25, 0.5]).round(3))

    # Proxy quality check: does the top-1 precedent share the query's labels?
    nb = kb.set_index("ticket_id").loc[[ids[p] for p in pos[:, 0]]]
    typed = dev["type"].notna().values
    core = (dev["queue_core"] == True).values
    print("\nTop-1 precedent label agreement on dev:")
    print(f"  type     {np.mean(dev['type'].values[typed] == nb['type'].values[typed]):.3f}")
    print(f"  queue    {np.mean(dev['queue'].values[core] == nb['queue'].values[core]):.3f}")
    print(f"  priority {np.mean(dev['priority'].values == nb['priority'].values):.3f}")

    oos = idx.search(encode_queries(OUT_OF_SCOPE), 1)[0][:, 0]
    print("\nOut-of-scope probes:")
    for t, s in zip(OUT_OF_SCOPE, oos):
        print(f"  {s:.3f}  {t}")

    p5, oos_max = float(np.percentile(top1, 5)), float(oos.max())
    if p5 > oos_max:
        thr = round((p5 + oos_max) / 2, 3)
    else:
        thr = round(p5, 3)
        print("\nWarning: dev 5th percentile overlaps out-of-scope scores; using the 5th percentile.")
    print(f"\nChosen threshold: {thr}  (dev p5={p5:.3f}, out-of-scope max={oos_max:.3f})")

    with open(CONFIG, "w") as f:
        json.dump({"sim_threshold": thr, "dev_p5": round(p5, 3),
                   "oos_max": round(oos_max, 3), "n_dev": int(len(dev))}, f, indent=2)
    print("Saved", CONFIG)
    return thr


if __name__ == "__main__":
    thr = tune()
    print("\n===== Demo queries (base + dev index) =====")
    for q in ["Our VPN is down and the hospital cannot reach the EMR system. Urgent!",
              "Mein VPN funktioniert nicht, ich kann mich nicht verbinden.",
              "What is the best pizza recipe?"]:
        hits = retrieve(q, k=5, which="all")
        flag = "NO PRECEDENT" if hits[0]["score"] < thr else "ok"
        print(f"\n[{flag}] {q}")
        for h in hits:
            print(f"  {h['ticket_id']} | {h['score']} | {h['language']} | {h['subject'][:60]}")
