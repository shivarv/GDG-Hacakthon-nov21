"""SentinelDesk orchestrator."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .burst import BurstDetector
from .classifier import TriageClassifier
from .config import SETTINGS, Settings
from .data import build_text
from .gate import decide
from .generator import Generator
from .lang import detect_language
from .pii import mask_pii
from .retriever import E5Encoder, Retriever


class SentinelDesk:
    def __init__(self, settings: Settings = SETTINGS, classifier=None, retriever=None, generator=None):
        self.s = settings
        art = Path(settings.artifacts_dir)
        self.classifier = classifier or TriageClassifier.load(art / "classifier.joblib")
        self.retriever = retriever or Retriever.load(art / "index", E5Encoder(settings.embed_model))
        self.generator = generator or Generator(settings.llm_provider, settings.llm_model,
                                                settings.openai_base_url, settings.llm_timeout_s)
        # Thresholds tuned on the KB split by scripts/tune_gate.py. Env vars win over the tuned file.
        self.sim_threshold, self.risk_threshold = settings.sim_threshold, None
        tuned = art / "gate_thresholds.json"
        if tuned.exists():
            cfg = json.loads(tuned.read_text())
            if "SIM_THRESHOLD" not in os.environ:
                self.sim_threshold = cfg["sim_threshold"]
            self.risk_threshold = cfg.get("risk_threshold")
        self.burst = BurstDetector(settings.burst_sim, settings.burst_min, settings.burst_window_min)

    def triage(self, subject: str | None, body: str | None, generate: bool = True,
               track_burst: bool = True) -> dict:
        t0 = time.perf_counter()
        text = build_text(subject, body)
        if not text:
            raise ValueError("Ticket has no subject and no body.")
        timings = {}

        t = time.perf_counter()
        lang = detect_language(text)
        preds = self.classifier.predict_one(text)
        timings["classify_ms"] = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        hits, qvec = self.retriever.search(text, self.s.top_k)
        timings["retrieve_ms"] = (time.perf_counter() - t) * 1000

        gate = decide(text, preds, hits, self.s.conf_threshold, self.sim_threshold,
                      self.risk_threshold)

        outage = None
        if track_burst:
            outage = self.burst.observe(qvec, (subject or body or "")[:80])
            if outage:
                gate.add(f"Major incident: {outage['count']} similar tickets in {outage['window_min']:.0f} min")

        draft = None
        if generate:
            t = time.perf_counter()
            draft = self.generator.generate(subject or "", body or "", lang, hits, escalated=gate.escalate)
            timings["generate_ms"] = (time.perf_counter() - t) * 1000
            for w in draft.warnings:
                if w.startswith(("Unsupported numeric", "Draft does not cite")):
                    gate.add(f"Draft guardrail: {w}")

        _, pii = mask_pii(text)
        return {
            "language": lang,
            "predictions": preds,
            "gate": gate.to_dict(),
            "hits": hits,
            "draft": draft.to_dict() if draft else None,
            "outage": outage,
            "pii_detected": pii,
            "timings_ms": timings,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
