"""SentinelDesk triage model, served on Cloud Run (POST {TRIAGE_URL}/triage).

The service returns TriageModel.predict() JSON from the triage/ package: type/queue/priority with
calibrated confidence, hp_incident, explicit EN/DE urgency rules and gate_hints. Here it maps to:
  should_escalate  = urgency rule fired (outage + scope/impact, security, ...)
                     OR (likely high-priority Incident AND predicted priority is high)
  priority         = urgent when escalating, else the predicted high/medium/low
Any HTTP error falls back to the keyword dummy so email intake never breaks.
"""

from __future__ import annotations

import logging

import requests

from app.core.config import get_settings
from app.models import TicketPriority
from app.services.triage.base import TriageDecision
from app.services.triage.dummy import DummyTriageModel

logger = logging.getLogger(__name__)

_PRIORITY = {"high": TicketPriority.HIGH, "medium": TicketPriority.MEDIUM, "low": TicketPriority.LOW}


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

        pri = out["priority"]
        urgent = bool(out.get("urgency", {}).get("urgent"))
        hp = bool(out.get("hp_incident", {}).get("flag")) and pri["label"] == "high"
        should_escalate = urgent or hp
        priority = TicketPriority.URGENT if should_escalate else _PRIORITY.get(pri["label"], TicketPriority.MEDIUM)
        reasons = [f"Type {out['type']['label']} ({out['type']['conf']:.2f}), queue {out['queue']['label']} "
                   f"({out['queue']['conf']:.2f}), priority {pri['label']} ({pri['conf']:.2f})"]
        reasons += out.get("gate_hints", {}).get("reasons", [])
        rag = out.get("rag") if isinstance(out.get("rag"), dict) else None
        if rag:
            try:
                if (rag.get("reply") or {}).get("needs_human"):
                    reasons.append("RAG: " + ((rag["reply"].get("reason")) or "no grounded reply: needs a human"))
            except Exception:
                logger.warning("Malformed rag block ignored")
        reasons.append("Escalate automatically" if should_escalate else "Not severe → normal queue")
        return TriageDecision(priority=priority, should_escalate=should_escalate,
                              confidence=float(pri["conf"]), model=self.name, reasons=reasons, rag=rag)
