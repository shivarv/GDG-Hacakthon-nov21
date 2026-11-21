"""Triage for new tickets, shared by email intake and the "New ticket" form.

  assess()        run the configured triage model (keyword rules if it fails)
  apply()         copy the prediction onto the ticket (type/queue/confidence/model, optionally priority)
  add_notes()     internal "Triage" note with the reasoning, plus the RAG note when available
  auto_escalate() escalate right away when the model says it's severe
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.dao.comment_dao import CommentDAO
from app.models import Comment, EscalationSource, Ticket, TicketPriority
from app.services.notification_service import NotificationService
from app.services.triage import TriageDecision, get_triage_model

logger = logging.getLogger(__name__)


class TicketTriageService:
    def __init__(self, db: Session, notifier: NotificationService | None = None):
        self.db = db
        self.notifier = notifier or NotificationService(db)
        self.comments = CommentDAO(db)

    def assess(self, subject: str, body: str) -> TriageDecision:
        name = self.notifier.settings.triage_model
        try:
            return get_triage_model(name).assess(subject, body)
        except Exception as exc:
            logger.exception("Triage model %s failed; using keyword rules for this ticket", name)
            decision = get_triage_model("dummy").assess(subject, body)
            decision.reasons.insert(0, f"Triage model {name} unavailable ({exc}); keyword rules used")
            return decision

    @staticmethod
    def apply(ticket: Ticket, decision: TriageDecision, set_priority: bool = True) -> None:
        if set_priority:
            ticket.priority = decision.priority
        ticket.predicted_type = decision.ticket_type
        ticket.predicted_queue = decision.queue
        ticket.queue_confidence = decision.queue_confidence
        ticket.triage_model = decision.model

    def add_notes(self, ticket: Ticket, decision: TriageDecision, chosen_priority: TicketPriority | None = None) -> None:
        lines = [f"Triage ({decision.model}): priority {decision.priority.value}, "
                 + ("escalation recommended" if decision.should_escalate else "no escalation")]
        if chosen_priority and chosen_priority != decision.priority:
            lines.append(f"• Agent set priority {chosen_priority.value} (model suggested {decision.priority.value})")
        lines += [f"• {r}" for r in decision.reasons]
        self.comments.add(Comment(ticket_id=ticket.id, author="Triage", body="\n".join(lines), is_internal=True))
        self._add_rag_note(ticket, decision)
        self.db.commit()

    def auto_escalate(self, ticket: Ticket, decision: TriageDecision) -> bool:
        """Escalate a new ticket when the triage model says it's severe. Returns True if escalated."""
        if not (self.notifier.settings.auto_escalate and decision.should_escalate):
            return False
        from app.schemas.escalation import EscalationCreate  # local imports avoid a cycle
        from app.services.escalation_service import EscalationService

        try:
            EscalationService(self.db, notifier=self.notifier).escalate(
                ticket.id,
                EscalationCreate(reason="Auto-escalated by triage: " + "; ".join(decision.reasons),
                                 escalated_by=f"Triage ({decision.model})"),
                source=EscalationSource.AUTO,
            )
            logger.info("Auto-escalated %s (%s)", ticket.ticket_number, "; ".join(decision.reasons))
            return True
        except Exception:
            self.db.rollback()
            logger.exception("Auto-escalation failed for %s", ticket.ticket_number)
            return False

    def _add_rag_note(self, ticket: Ticket, decision: TriageDecision) -> None:
        """Attach the grounded suggested reply + cited precedents as an internal note (best effort)."""
        try:
            rag = getattr(decision, "rag", None)
            if not rag:
                return
            reply = rag.get("reply") or {}
            cited = [str(c) for c in (reply.get("cited_ticket_ids") or [])]
            lines = []
            text = (reply.get("text") or "").strip()
            if text and not reply.get("needs_human"):
                lines.append(f"Suggested reply (grounded in {', '.join(cited) or 'precedents'}):\n{text}")
            elif reply.get("needs_human"):
                lines.append("Needs a human: " + (reply.get("reason") or "no grounded reply available"))
            precs = []
            for p in (rag.get("precedents") or [])[:5]:
                bits = [f"sim {float(p.get('similarity', 0)):.2f}"]
                if p.get("queue"):
                    bits.append(f"queue {p['queue']}")
                if p.get("priority"):
                    bits.append(f"priority {p['priority']}")
                precs.append(f"{p.get('ticket_id')} ({', '.join(bits)})")
            if precs:
                lines.append("Precedents: " + ", ".join(precs))
            if lines:
                self.comments.add(Comment(ticket_id=ticket.id, author="Triage (RAG)",
                                          body="\n\n".join(lines), is_internal=True))
        except Exception:
            logger.exception("Could not attach RAG note")
