"""Live outage / burst detection over a sliding window of recent tickets."""
from __future__ import annotations

import threading
import time
from collections import deque

import numpy as np


class BurstDetector:
    def __init__(self, sim: float = 0.88, min_count: int = 3, window_min: float = 15):
        self.sim, self.min_count, self.window_s = sim, min_count, window_min * 60
        self._recent: deque = deque()  # (timestamp, vector, label)
        self._lock = threading.Lock()

    def observe(self, vec: np.ndarray, label: str, now: float | None = None) -> dict | None:
        """Record a ticket; return a banner dict when a cluster reaches min_count."""
        now = time.time() if now is None else now
        with self._lock:
            while self._recent and now - self._recent[0][0] > self.window_s:
                self._recent.popleft()
            similar = [lbl for ts, v, lbl in self._recent if float(np.dot(v, vec)) >= self.sim]
            self._recent.append((now, vec, label))
        count = len(similar) + 1
        if count >= self.min_count:
            return {"count": count, "window_min": self.window_s / 60,
                    "examples": (similar + [label])[-5:]}
        return None

    def reset(self):
        with self._lock:
            self._recent.clear()
