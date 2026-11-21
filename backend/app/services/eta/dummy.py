"""Placeholder resolution-time model: fixed targets by priority and escalation level.
Replace with a trained model later (same `estimate()` signature)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Ticket, TicketPriority
from app.services.eta.base import ResolutionEstimate

# priority -> (first response, resolution) for a level-2 escalation
_TARGETS: dict[TicketPriority, tuple[timedelta, timedelta]] = {
    TicketPriority.URGENT: (timedelta(minutes=30), timedelta(hours=4)),
    TicketPriority.HIGH: (timedelta(hours=1), timedelta(hours=8)),
    TicketPriority.MEDIUM: (timedelta(hours=2), timedelta(hours=24)),
    TicketPriority.LOW: (timedelta(hours=4), timedelta(hours=48)),
}


class DummyEtaModel:
    name = "dummy-v0"

    def estimate(self, ticket: Ticket, level: int, now: datetime) -> ResolutionEstimate:
        first, resolve = _TARGETS[ticket.priority]
        factors = [f"{ticket.priority.value.capitalize()} priority → {_fmt(first)} first response, {_fmt(resolve)} resolution"]
        if level >= 3:
            first, resolve = first / 2, resolve / 2
            factors.append("Level 3 escalation → targets halved")
        return ResolutionEstimate(
            first_response_due_at=now + first,
            resolution_due_at=now + resolve,
            model=self.name,
            confidence=0.5,
            factors=factors,
        )


def _fmt(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h"
