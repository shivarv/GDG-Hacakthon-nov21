"""SentinelDesk triage model: shared TF-IDF features + one calibrated logistic regression per head.

Heads (see train.py):
  type         4 classes, trained on rows with a type label
  queue        10 core queues (the departments in the brief)
  priority     3 classes (critical->high, very_low->low)
  hp_incident  binary: type == Incident AND priority == high (drives the escalation gate)
  queue_all    52 queues, reporting only (saved separately, not used live)

Usage:
  from triage.model import TriageModel
  tm = TriageModel.load("triage/models/triage.joblib")
  tm.predict("VPN down", "Since 8am nobody can connect ...")  # -> dict in the shared JSON contract
"""
import time

import joblib
import numpy as np

try:
    from .textprep import build_text
    from .urgency import urgency
except ImportError:  # run as a script from inside triage/
    from textprep import build_text
    from urgency import urgency

CONTRACT_HEADS = ("type", "queue", "priority")


def scaled_proba(lr, X, T: float = 1.0) -> np.ndarray:
    z = lr.decision_function(X)
    if z.ndim == 1:  # binary: decision_function is the logit of classes_[1]
        p1 = 1.0 / (1.0 + np.exp(-z / T))
        return np.column_stack([1 - p1, p1])
    z = z / T
    z -= z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


class TriageModel:
    def __init__(self, features, heads: dict, temps: dict, gate: dict, meta: dict):
        self.features = features  # fitted FeatureUnion
        self.heads = heads        # name -> fitted LogisticRegression
        self.temps = temps        # name -> temperature fitted on dev_cal (1.0 = uncalibrated)
        self.gate = gate          # thresholds tuned on dev_tune
        self.meta = meta

    # ---------- persistence (only sklearn objects + plain dicts are pickled) ----------
    def save(self, path: str) -> None:
        joblib.dump({"features": self.features, "heads": self.heads, "temps": self.temps,
                     "gate": self.gate, "meta": self.meta}, path, compress=3)

    @classmethod
    def load(cls, path: str) -> "TriageModel":
        d = joblib.load(path)
        return cls(d["features"], d["heads"], d["temps"], d["gate"], d["meta"])

    # ---------- inference ----------
    def transform(self, texts):
        return self.features.transform(texts)

    def proba(self, X, head: str) -> np.ndarray:
        """Temperature-scaled probabilities. Temperature never changes the argmax, so F1 is unaffected."""
        return scaled_proba(self.heads[head], X, self.temps.get(head, 1.0))

    def classes(self, head: str):
        return list(self.heads[head].classes_)

    def predict(self, subject, body) -> dict:
        """One raw ticket -> {"type":{label,conf,probs}, "queue":..., "priority":..., "hp_incident":..., "gate_hints":..., "latency_ms":...}"""
        t0 = time.perf_counter()
        text = build_text(subject, body)
        X = self.transform([text])
        out = {}
        for head in CONTRACT_HEADS:
            p = self.proba(X, head)[0]
            cls = self.classes(head)
            i = int(np.argmax(p))
            out[head] = {
                "label": cls[i],
                "conf": float(p[i]),
                "probs": {c: round(float(v), 4) for c, v in sorted(zip(cls, p), key=lambda z: -z[1])},
            }
        p_hp = float(self.proba(X, "hp_incident")[0][list(self.classes("hp_incident")).index(1)])
        g = self.gate
        out["hp_incident"] = {"prob": p_hp, "flag": p_hp >= g["hp_incident_threshold"]}
        reasons = []
        u = urgency(text)
        out["urgency"] = {"urgent": u["urgent"], "reason": u["reason"]}
        if u["urgent"]:
            reasons.append(u["reason"])
        if out["hp_incident"]["flag"]:
            reasons.append(f"Likely high-priority Incident (p={p_hp:.2f} >= {g['hp_incident_threshold']:.2f})")
        for head in ("type", "queue"):
            th = g["conf_threshold"][head]
            if out[head]["conf"] < th:
                reasons.append(f"Low {head} confidence ({out[head]['conf']:.2f} < {th:.2f})")
        out["gate_hints"] = {"escalate": bool(reasons), "reasons": reasons}
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out
