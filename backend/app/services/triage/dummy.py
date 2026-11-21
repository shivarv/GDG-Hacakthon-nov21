"""Placeholder triage model: keyword rules. Replace with a trained classifier later."""

from __future__ import annotations

import re

from app.models import TicketPriority
from app.services.email_parser import detect_priority
from app.services.triage.base import TriageDecision

# Severe topics: escalate even when the wording isn't "urgent".
_SEVERE = {
    "outage": ("outage", "is down", "are down", "service down", "site down", "production down", "not loading for anyone"),
    "security": ("security breach", "breach", "hacked", "compromised", "phishing", "data leak", "ransomware"),
    "data loss": ("data loss", "lost all", "deleted all", "data deleted"),
}


class DummyTriageModel:
    name = "dummy-v0"

    def assess(self, subject: str, body: str) -> TriageDecision:
        text = f"{subject}\n{body}".lower()
        priority = detect_priority(subject, body)
        reasons: list[str] = [f"Keywords suggest {priority.value} priority"]

        topic = next((name for name, words in _SEVERE.items()
                      if any(re.search(rf"(?<!\w){re.escape(w)}", text) for w in words)), None)
        if topic:
            reasons.append(f"Severe topic detected: {topic}")
            priority = TicketPriority.URGENT

        should_escalate = priority == TicketPriority.URGENT
        reasons.append("Urgent → escalate automatically" if should_escalate else "Not severe → normal queue")
        return TriageDecision(priority=priority, should_escalate=should_escalate,
                              confidence=0.5, model=self.name, reasons=reasons)
