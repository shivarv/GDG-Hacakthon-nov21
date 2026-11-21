"""Chooses who a ticket should be escalated to.

Rules, in order:
1. Topic -> team, from keywords in the subject and description (EN + DE).
2. Level: L2 team lead by default; L3 when the ticket is urgent, already
   escalated, or the topic is owned by an L3 specialist (outages, security).
3. Within the candidates, pick the contact with the fewest active escalations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.escalation_dao import EscalationDAO
from app.dao.user_dao import UserDAO
from app.models import Escalation, EscalationStatus, Ticket, TicketPriority, User

# team -> keywords. The first team with a keyword hit wins; order matters.
TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Information Security", ("security", "breach", "hacked", "phishing", "malware", "virus", "suspicious",
                              "gdpr", "data leak", "compromised", "sicherheit", "datenschutz")),
    ("Service Outages and Maintenance", ("outage", "is down", "are down", "service down", "site down", "not loading",
                                         "unavailable", "all users", "everyone", "production", "ausfall", "störung")),
    ("Billing and Payments", ("invoice", "refund", "charged", "charge", "billing", "payment", "subscription",
                              "credit card", "rechnung", "zahlung", "erstattung")),
    ("IT Support", ("laptop", "printer", "vpn", "network", "wifi", "wi-fi", "hardware", "monitor", "keyboard",
                    "access request", "drucker", "netzwerk")),
    ("Technical Support", ("login", "log in", "password", "error", "bug", "crash", "not working", "api",
                           "integration", "reset", "anmeld", "passwort", "fehler")),
    ("Product Support", ("feature", "how do i", "how to", "dashboard", "report", "product", "funktion")),
]
DEFAULT_TEAM = "Customer Service"
# Use the triage model's predicted queue when no keyword matched and it's reasonably sure,
# or whenever it's very sure (keywords then only break ties).
MODEL_QUEUE_MIN_CONF = 0.4
MODEL_QUEUE_STRONG_CONF = 0.75
L3_SPECIALIST_TEAMS = {"Information Security", "Service Outages and Maintenance"}
FALLBACK_L3_TEAM = "Head of Support"


@dataclass
class Suggestion:
    contact: User
    level: int
    team: str
    reasons: list[str] = field(default_factory=list)


class EscalationRoutingService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserDAO(db)
        self.escalations = EscalationDAO(db)

    def suggest(self, ticket: Ticket) -> Suggestion | None:
        contacts = self.users.list(escalation_contacts_only=True)
        if not contacts:
            return None

        current = self.escalations.get_active_for_ticket(ticket.id)
        team, keyword = self._detect_team(ticket)
        reasons = [f'Matched "{keyword}" → {team}' if keyword else f"No topic keywords → {team}"]
        staffed = {c.team for c in contacts}
        conf = ticket.queue_confidence or 0.0
        model_team_ok = ticket.predicted_queue in staffed
        if model_team_ok and (conf >= MODEL_QUEUE_STRONG_CONF or (keyword is None and conf >= MODEL_QUEUE_MIN_CONF)):
            team = ticket.predicted_queue
            reasons = [f"Model predicted queue {team} ({ticket.queue_confidence:.2f})"]

        level = 2
        if team in L3_SPECIALIST_TEAMS:
            level = 3
            reasons.append(f"{team} is handled by an L3 specialist")
        if ticket.priority == TicketPriority.URGENT:
            level = 3
            reasons.append("Urgent priority → L3")
        if current:
            level = max(level, min(current.level + 1, 3))
            reasons.append(f"Already escalated to L{current.level} → L{level}")

        candidates = [c for c in contacts if c.escalation_level == level and (not current or c.id != current.escalated_to_id)]
        same_team = [c for c in candidates if c.team == team]
        if same_team:
            pool = same_team
        else:
            fallback = FALLBACK_L3_TEAM if level == 3 else DEFAULT_TEAM
            pool = [c for c in candidates if c.team == fallback] or candidates
            if pool:
                reasons.append(f"No L{level} contact in {team} → {pool[0].team}")
        if not pool:
            return None

        load = self._active_load([c.id for c in pool])
        pool.sort(key=lambda c: (load.get(c.id, 0), c.name))
        chosen = pool[0]
        n = load.get(chosen.id, 0)
        reasons.append(f"{chosen.name} has {n} active escalation{'s' if n != 1 else ''}" + (" (least loaded)" if len(pool) > 1 else ""))
        return Suggestion(contact=chosen, level=level, team=team, reasons=reasons)

    @staticmethod
    def _detect_team(ticket: Ticket) -> tuple[str, str | None]:
        text = f"{ticket.subject}\n{ticket.description}".lower()
        for team, keywords in TOPIC_RULES:
            for kw in keywords:
                if re.search(rf"(?<!\w){re.escape(kw)}", text):
                    return team, kw
        return DEFAULT_TEAM, None

    def _active_load(self, user_ids: list[int]) -> dict[int, int]:
        rows = self.db.execute(
            select(Escalation.escalated_to_id, func.count())
            .where(Escalation.status == EscalationStatus.ACTIVE, Escalation.escalated_to_id.in_(user_ids))
            .group_by(Escalation.escalated_to_id)
        ).all()
        return dict(rows)
