"""Diverse top-k over FAISS candidates, so a reply cites k distinct precedents instead of k rewordings
of the same ticket family.

Greedy: walk candidates by descending similarity to the query; keep a hit unless its cosine to any
already-kept hit is >= max_cos. Vectors are re-normalized defensively (FAISS IP on e5 is already cosine).
"""
from __future__ import annotations

import numpy as np


def diverse_topk(cand_ids, cand_vecs, cand_sims, k: int = 5, max_cos: float = 0.95):
    """cand_ids: [n] ids; cand_vecs: [n, d] embeddings; cand_sims: [n] query similarities (FAISS scores).

    Returns (ids, sims, skipped): kept ids and their query sims (best first, at most k), plus a list of
    (skipped_id, kept_id_it_duplicates, cos) for logging/explanations. Fewer than k ids come back
    when the candidates hold fewer than k distinct precedents.
    """
    ids = list(cand_ids)
    vecs = np.asarray(cand_vecs, dtype=np.float32).reshape(len(ids), -1)
    sims = np.asarray(cand_sims, dtype=np.float32).reshape(-1)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / np.where(norms > 0, norms, 1.0)

    order = np.argsort(-sims, kind="stable")
    kept: list[int] = []
    skipped = []
    for i in order:
        if len(kept) >= k:
            break
        if ids[i] in (ids[j] for j in kept):
            continue  # same id returned twice
        if kept:
            cos = vecs[kept] @ vecs[i]
            j = int(np.argmax(cos))
            if cos[j] >= max_cos:
                skipped.append((ids[i], ids[kept[j]], round(float(cos[j]), 4)))
                continue
        kept.append(int(i))
    return [ids[i] for i in kept], [float(sims[i]) for i in kept], skipped
