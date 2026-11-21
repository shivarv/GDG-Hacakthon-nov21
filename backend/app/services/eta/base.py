from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.models import Ticket


@dataclass
class ResolutionEstimate:
    first_response_due_at: datetime  # when the assigned contact should first reply
    resolution_due_at: datetime  # when we expect the ticket to be resolved
    model: str  # e.g. "dummy-v0"; stored with the escalation for traceability
    confidence: float  # 0..1, how sure the model is (dummy: fixed)
    factors: list[str] = field(default_factory=list)  # human-readable explanation


class EtaModel(Protocol):
    """Interface every resolution-time model implements."""

    name: str

    def estimate(self, ticket: Ticket, level: int, now: datetime) -> ResolutionEstimate: ...
