"""Online "Major Incident" burst detector (leader clustering over a rolling window, no clustering library).

Each incoming ticket gets an L2-normalized multilingual-e5-small embedding ("query: " prefix, same as
dataset/embed.py). It joins the nearest *live* cluster if cos(ticket, centroid) >= threshold, else it
opens a new cluster. Window = last `max_items` tickets AND last `window_s` seconds; tickets falling out
of the window leave their cluster and centroids are recomputed from the members still alive.

A cluster is a burst (banner on) when it has >= `min_size` live members and a strict majority of them
are Incident/Problem (the `triage_type` passed in from triage; unknown counts as not-incident).

State lives in this process only. Cloud Run instances don't share memory, so run the service with a
single instance (max-instances=1) or keep one detector per demo session; don't expect bursts to be
seen across instances.

Why the vectors are de-biased first: raw e5-small cosines on this dataset are extremely compressed
(random dev pairs: median 0.85, 39% >= 0.86, 99.5th pct 0.93), so a raw 0.86 threshold chains almost
every ticket into one giant cluster. We remove the corpus mean and the top-2 principal directions
(estimated on kb `base` rows, stored in live/e5_debias.npz; "all-but-the-top") and re-normalize.
In that space random dev pairs centre on 0 and the default threshold is calibrated to < 0.5% random
pairs above it: see live/calibrate.py and live/calibration.json. Pass space="raw" to get the plain
cosine behaviour (threshold then means raw e5 cosine).
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np

MODEL_NAME = "intfloat/multilingual-e5-small"
PREFIX = "query: "
INCIDENT_TYPES = {"incident", "problem"}
DEBIAS_PATH = Path(__file__).resolve().parent / "e5_debias.npz"
DEFAULT_THRESHOLD = 0.45  # in de-biased space; chosen from live/calibration.json

_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(MODEL_NAME, device="cpu")
            _model.max_seq_length = 512
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalized e5 vectors, float32 [n, 384]. Adds the "query: " prefix."""
    m = get_model()
    v = m.encode([PREFIX + (t or "") for t in texts], batch_size=64, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(v, dtype=np.float32)


def _to_seconds(ts) -> float:
    if isinstance(ts, datetime):
        return ts.timestamp()
    return float(ts)


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class Debias:
    """x -> normalize((x - mu) minus its projection on the top-k PCs)."""

    def __init__(self, mu: np.ndarray, pcs: np.ndarray):
        self.mu = np.asarray(mu, dtype=np.float32)
        self.pcs = np.asarray(pcs, dtype=np.float32).reshape(-1, self.mu.shape[0])

    @classmethod
    def load(cls, path=DEBIAS_PATH):
        z = np.load(path)
        return cls(z["mu"], z["pcs"])

    def __call__(self, x: np.ndarray) -> np.ndarray:
        y = np.asarray(x, dtype=np.float32) - self.mu
        if len(self.pcs):
            y = y - (y @ self.pcs.T) @ self.pcs
        n = np.linalg.norm(y, axis=-1, keepdims=True)
        return y / np.where(n > 0, n, 1.0)


class _Cluster:
    __slots__ = ("cid", "members", "vsum", "first_text")

    def __init__(self, cid: int, first_text: str):
        self.cid = cid
        self.members: dict[str, tuple[np.ndarray, Optional[str], float]] = {}  # ticket_id -> (vec, type, ts)
        self.vsum: Optional[np.ndarray] = None
        self.first_text = first_text

    def centroid(self) -> np.ndarray:
        return _unit(self.vsum)

    def add(self, tid, vec, ttype, ts):
        self.members[tid] = (vec, ttype, ts)
        self.vsum = vec.copy() if self.vsum is None else self.vsum + vec

    def remove(self, tid):
        vec, _, _ = self.members.pop(tid)
        self.vsum = self.vsum - vec if self.members else None

    def n_incident(self) -> int:
        return sum(1 for _, t, _ in self.members.values() if isinstance(t, str) and t.strip().lower() in INCIDENT_TYPES)


class BurstDetector:
    def __init__(self, threshold: Optional[float] = None, max_items: int = 200, window_s: float = 900.0,
                 min_size: int = 3, embed_fn: Optional[Callable[[list[str]], np.ndarray]] = None,
                 space: str = "debiased", debias: Optional[Debias] = None):
        if space not in ("debiased", "raw"):
            raise ValueError("space must be 'debiased' or 'raw'")
        self.space = space
        self.debias = (debias or Debias.load()) if space == "debiased" else None
        self.threshold = threshold if threshold is not None else (DEFAULT_THRESHOLD if space == "debiased" else 0.86)
        self.max_items = max_items
        self.window_s = window_s
        self.min_size = min_size
        self.embed_fn = embed_fn or embed
        self._buf: deque = deque()  # (ticket_id, ts, cluster_id, seq) in arrival order
        self._clusters: dict[int, _Cluster] = {}
        self._where: dict[str, int] = {}  # ticket_id -> cluster_id
        self._seq: dict[str, int] = {}  # ticket_id -> arrival number of its live copy
        self._n = 0
        self._next_cid = 1
        self._lock = threading.Lock()

    # ---- window maintenance -------------------------------------------------
    def _evict(self, now: float):
        while self._buf and (len(self._buf) > self.max_items or now - self._buf[0][1] > self.window_s):
            tid, _, cid, seq = self._buf.popleft()
            if self._seq.get(tid) != seq:
                continue  # stale entry (ticket was re-added later)
            del self._where[tid], self._seq[tid]
            c = self._clusters[cid]
            c.remove(tid)
            if not c.members:
                del self._clusters[cid]

    def _is_burst(self, c: _Cluster) -> bool:
        n = len(c.members)
        return n >= self.min_size and c.n_incident() * 2 > n

    def _banner(self, c: _Cluster) -> str:
        mins = int(round(self.window_s / 60))
        head = " ".join(c.first_text.split())[:90]
        return (f"MAJOR INCIDENT: {len(c.members)} related tickets in the last {mins} min "
                f"(cluster #{c.cid}): \"{head}\"")

    # ---- public API ---------------------------------------------------------
    def add(self, ticket_id, text: str, ts, triage_type: Optional[str] = None, vec=None) -> dict:
        """Add one ticket. `vec` (a raw L2-normalized e5 "query: " vector, as used for FAISS) skips
        re-embedding when the app already embedded the ticket for retrieval. `cos_to_centroid` in the
        result is in the detector's space (de-biased by default)."""
        tid = str(ticket_id)
        now = _to_seconds(ts)
        v = _unit(vec) if vec is not None else self.embed_fn([text])[0]  # raw e5 vector
        if self.debias is not None:
            v = self.debias(v)
        with self._lock:
            if tid in self._where:  # re-submission: drop the old copy first
                c = self._clusters[self._where.pop(tid)]
                c.remove(tid)
                if not c.members:
                    del self._clusters[c.cid]
            self._evict(now)
            best, best_cos = None, -1.0
            for c in self._clusters.values():
                cos = float(c.centroid() @ v)
                if cos > best_cos:
                    best, best_cos = c, cos
            if best is None or best_cos < self.threshold:
                best = _Cluster(self._next_cid, text or "")
                self._clusters[best.cid] = best
                self._next_cid += 1
                best_cos = 1.0
            best.add(tid, v, triage_type, now)
            self._where[tid] = best.cid
            self._n += 1
            self._seq[tid] = self._n
            self._buf.append((tid, now, best.cid, self._n))
            self._evict(now)  # enforce max_items after the append

            size = len(best.members)
            burst = self._is_burst(best)
            return {
                "in_burst": burst,
                "cluster_id": best.cid,
                "size": size,
                "cos_to_centroid": round(best_cos, 4),
                "banner": self._banner(best) if burst else None,
                "reason": f"Part of active outage cluster (n={size})" if burst else None,
            }

    def active_bursts(self, now=None) -> list[dict]:
        """Bursting clusters right now (for a page-level banner poll)."""
        with self._lock:
            if now is not None:
                self._evict(_to_seconds(now))
            out = []
            for c in self._clusters.values():
                if self._is_burst(c):
                    out.append({"cluster_id": c.cid, "size": len(c.members), "n_incident": c.n_incident(),
                                "ticket_ids": list(c.members), "banner": self._banner(c)})
            return sorted(out, key=lambda d: -d["size"])

    def status(self, ticket_id) -> dict:
        """Current burst status of a ticket already added (it may join a burst after its own add())."""
        with self._lock:
            cid = self._where.get(str(ticket_id))
            if cid is None:
                return {"in_burst": False, "cluster_id": None, "size": 0, "banner": None, "reason": None}
            c = self._clusters[cid]
            burst = self._is_burst(c)
            return {"in_burst": burst, "cluster_id": cid, "size": len(c.members),
                    "banner": self._banner(c) if burst else None,
                    "reason": f"Part of active outage cluster (n={len(c.members)})" if burst else None}

    def __len__(self):
        return len(self._where)
