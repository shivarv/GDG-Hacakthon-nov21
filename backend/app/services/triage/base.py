from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.models import TicketPriority


@dataclass
class TriageDecision:
    priority: TicketPriority  # predicted severity
    should_escalate: bool  # escalate immediately, without waiting for an agent
    confidence: float  # 0..1 (dummy: fixed)
    model: str  # e.g. "dummy-v0"
    reasons: list[str] = field(default_factory=list)


class TriageModel(Protocol):
    name: str

    def assess(self, subject: str, body: str) -> TriageDecision: ...
