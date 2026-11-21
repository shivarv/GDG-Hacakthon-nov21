"""Embedding retrieval over the historical KB split (FAISS, NumPy fallback)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import META_COLS, build_text

try:
    import faiss
except ImportError:
    faiss = None

MAX_CHARS = 2000  # keep encoder input bounded (~512 tokens)


class E5Encoder:
    """Wraps sentence-transformers. e5 models expect a 'query: ' prefix for symmetric search."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.prefix = "query: " if "e5" in model_name.lower() else ""

    def encode(self, texts: list[str], batch_size: int = 64, show_progress: bool = False) -> np.ndarray:
        texts = [self.prefix + t[:MAX_CHARS] for t in texts]
        return self.model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                                 show_progress_bar=show_progress, convert_to_numpy=True).astype("float32")


def _text(x) -> str:
    """Null-safe string: missing subjects (None/NaN) become an empty string."""
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else str(x)


def select_cross_lingual(pool: list[dict], k: int, lang: str, min_other: int) -> list[dict]:
    """Pick k hits from a similarity-sorted pool, keeping the best hit and >= min_other other-language hits."""
    chosen = list(pool[:k])
    need = min_other - sum(1 for h in chosen if h.get("language") and h["language"] != lang)
    if need > 0:
        extra = [h for h in pool[k:] if h.get("language") and h["language"] != lang][:need]
        for h in extra:  # replace the weakest same-language hits, never the top hit
            for i in range(len(chosen) - 1, 0, -1):
                if chosen[i].get("language") == lang:
                    chosen[i] = h
                    break
    return sorted(chosen, key=lambda h: -h["similarity"])


class Retriever:
    def __init__(self, encoder):
        self.encoder = encoder
        self.index = None
        self.vectors: np.ndarray | None = None  # used when faiss is missing
        self.meta: pd.DataFrame | None = None

    # ---------- build ----------
    def build(self, kb_df: pd.DataFrame, show_progress: bool = True):
        texts = [build_text(s, b) for s, b in zip(kb_df["subject"], kb_df["body"])]
        vecs = self.encoder.encode(texts, show_progress=show_progress)
        self._set_vectors(vecs)
        cols = [c for c in META_COLS if c in kb_df.columns]
        self.meta = kb_df[cols].reset_index(drop=True)
        return self

    def _set_vectors(self, vecs: np.ndarray):
        vecs = np.ascontiguousarray(vecs, dtype="float32")
        if faiss is not None:
            self.index = faiss.IndexFlatIP(vecs.shape[1])
            self.index.add(vecs)
        else:
            self.vectors = vecs

    # ---------- query ----------
    def embed(self, text: str) -> np.ndarray:
        return self.encoder.encode([text])[0]

    def search_vector(self, q: np.ndarray, k: int = 5) -> list[dict]:
        q = np.ascontiguousarray(q.reshape(1, -1), dtype="float32")
        if self.index is not None:
            sims, idx = self.index.search(q, k)
            pairs = zip(idx[0], sims[0])
        else:
            scores = self.vectors @ q[0]
            top = np.argsort(-scores)[:k]
            pairs = zip(top, scores[top])
        hits = []
        for i, s in pairs:
            if i < 0:
                continue
            row = self.meta.iloc[int(i)]
            hits.append({
                "ticket_id": row["ticket_id"],
                "similarity": float(s),
                "subject": _text(row.get("subject")),
                "body": _text(row.get("body")),
                "answer": _text(row.get("answer")),
                "type": row.get("type", ""),
                "queue": row.get("queue", ""),
                "priority": row.get("priority", ""),
                "language": row.get("language", ""),
            })
        return hits

    def search(self, text: str, k: int = 5, lang: str | None = None,
               min_other_lang: int = 0) -> tuple[list[dict], np.ndarray]:
        """Top-k hits. With `lang` and `min_other_lang`, guarantee some precedents from the other language
        (cross-lingual matching) by swapping them in for the weakest same-language hits."""
        q = self.embed(text)
        if not (lang and min_other_lang > 0):
            return self.search_vector(q, k), q
        return select_cross_lingual(self.search_vector(q, max(k * 6, 30)), k, lang, min_other_lang), q

    def ticket_ids(self) -> set[str]:
        return set(self.meta["ticket_id"])

    # ---------- persistence ----------
    def save(self, directory: str | Path):
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        if self.index is not None:
            faiss.write_index(self.index, str(d / "kb.faiss"))
        else:
            np.save(d / "kb_vectors.npy", self.vectors)
        self.meta.to_parquet(d / "kb_meta.parquet", index=False)
        (d / "retriever.json").write_text(json.dumps({"model": getattr(self.encoder, "model_name", "custom")}))

    @classmethod
    def load(cls, directory: str | Path, encoder) -> "Retriever":
        d = Path(directory)
        r = cls(encoder)
        r.meta = pd.read_parquet(d / "kb_meta.parquet")
        if (d / "kb.faiss").exists() and faiss is not None:
            r.index = faiss.read_index(str(d / "kb.faiss"))
        elif (d / "kb_vectors.npy").exists():
            r._set_vectors(np.load(d / "kb_vectors.npy"))
        else:
            raise FileNotFoundError("No index found (kb.faiss needs faiss installed). Re-run scripts/build.py.")
        return r
