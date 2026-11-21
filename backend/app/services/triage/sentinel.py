"""SentinelDesk triage model (the `triage/` package), used two ways:

- SentinelTriageModel ("sentinel"): POST {TRIAGE_URL}/triage on Cloud Run.
- SentinelLocalModel ("sentinel_local"): load the same triage.joblib in-process.

The service returns TriageModel.predict() JSON: type/queue/priority with calibrated confidence,
hp_incident, explicit EN/DE urgency rules and gate_hints. Both variants map it the same way:
  should_escalate  = urgency rule fired (outage + scope/impact, security, ...)
                     OR (likely high-priority Incident AND predicted priority is high)
  priority         = urgent when escalating, else the predicted high/medium/low
  queue / type     = saved on the ticket; auto-assign uses the queue to pick the escalation team
  rag              = grounded suggested reply + cited precedents, attached as an internal note
Any HTTP error falls back to the keyword dummy so email intake never breaks.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

import requests

from app.core.config import get_settings
from app.models import TicketPriority
from app.services.triage.base import TriageDecision
from app.services.triage.dummy import DummyTriageModel

logger = logging.getLogger(__name__)

_PRIORITY = {"high": TicketPriority.HIGH, "medium": TicketPriority.MEDIUM, "low": TicketPriority.LOW}


def decision_from_contract(out: dict, model_name: str) -> TriageDecision:
    """Map the SentinelDesk JSON contract onto a TriageDecision."""
    pri = out["priority"]
    urgent = bool(out.get("urgency", {}).get("urgent"))
    hp = bool(out.get("hp_incident", {}).get("flag")) and pri["label"] == "high"
    should_escalate = urgent or hp
    priority = TicketPriority.URGENT if should_escalate else _PRIORITY.get(pri["label"], TicketPriority.MEDIUM)
    reasons = [f"Type {out['type']['label']} ({out['type']['conf']:.2f}), queue {out['queue']['label']} "
               f"({out['queue']['conf']:.2f}), priority {pri['label']} ({pri['conf']:.2f})"]
    reasons += out.get("gate_hints", {}).get("reasons", [])
    # Optional retrieval-grounded reply + cited precedents (the Cloud Run service returns these).
    rag = out.get("rag") if isinstance(out.get("rag"), dict) else None
    if rag:
        try:
            if (rag.get("reply") or {}).get("needs_human"):
                reasons.append("RAG: " + ((rag["reply"].get("reason")) or "no grounded reply: needs a human"))
        except Exception:
            logger.warning("Malformed rag block ignored")
    reasons.append("Escalate automatically" if should_escalate else "Not severe → normal queue")
    return TriageDecision(
        priority=priority,
        should_escalate=should_escalate,
        confidence=float(pri["conf"]),
        model=model_name,
        reasons=reasons,
        ticket_type=out["type"]["label"],
        queue=out["queue"]["label"],
        queue_confidence=float(out["queue"]["conf"]),
        rag=rag,
    )


class SentinelTriageModel:
    name = "sentinel-tfidf-lr"

    def assess(self, subject: str, body: str) -> TriageDecision:
        s = get_settings()
        try:
            r = requests.post(f"{s.triage_url.rstrip('/')}/triage",
                              json={"subject": subject or "", "body": body or ""}, timeout=s.triage_timeout_s)
            r.raise_for_status()
            out = r.json()
        except Exception as exc:  # network / 5xx: keep intake working
            logger.warning("Sentinel triage unavailable (%s); using dummy rules", exc)
            d = DummyTriageModel().assess(subject, body)
            d.reasons.insert(0, "Sentinel triage unavailable, used keyword fallback")
            return d
        return decision_from_contract(out, self.name)


class SentinelLocalModel:
    name = "sentinel-local"
    _lock = threading.Lock()
    _model = None

    def __init__(self):
        self.path = Path(get_settings().sentinel_model_path)

    def _load(self):
        with self._lock:
            if SentinelLocalModel._model is None:
                repo_root = self.path.resolve().parents[2]  # .../triage/models/triage.joblib -> repo root
                if str(repo_root) not in sys.path:
                    sys.path.insert(0, str(repo_root))
                from triage.model import TriageModel  # the triage/ package, unchanged

                logger.info("Loading SentinelDesk triage model from %s (takes ~40 s)...", self.path)
                SentinelLocalModel._model = TriageModel.load(str(self.path))
                logger.info("SentinelDesk triage model loaded")
            return SentinelLocalModel._model

    def warm_up(self) -> None:
        self._load()

    def assess(self, subject: str, body: str) -> TriageDecision:
        return decision_from_contract(self._load().predict(subject, body), self.name)
