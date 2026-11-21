from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.dao.comment_dao import CommentDAO
from app.dao.escalation_dao import EscalationDAO
from app.dao.ticket_dao import TicketDAO
from app.dao.user_dao import UserDAO
from app.models import (
    Comment,
    Escalation,
    EscalationSource,
    EscalationStatus,
    OutboundEmailStatus,
    Ticket,
    TicketSource,
    TicketStatus,
)
from app.schemas.escalation import EmailPreview, EscalationCreate, EscalationResolve, EscalationSuggestionRead, UserRead
from app.services.escalation_routing_service import EscalationRoutingService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

ESCALATABLE_STATUSES = {TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING}
MAX_LEVEL = 3


class EscalationService:
    """Escalates open tickets to a named contact, keeps an audit trail as
    internal notes, and notifies the contact by email."""

    def __init__(self, db: Session, notifier: NotificationService | None = None):
        self.db = db
        self.escalations = EscalationDAO(db)
        self.tickets = TicketDAO(db)
        self.users = UserDAO(db)
        self.comments = CommentDAO(db)
        self.notifier = notifier or NotificationService(db)
        self.router = EscalationRoutingService(db)

    def escalate(
        self, ticket_id: int, data: EscalationCreate, source: EscalationSource = EscalationSource.MANUAL
    ) -> Escalation:
        ticket = self._get_ticket(ticket_id)
        if ticket.status not in ESCALATABLE_STATUSES:
            raise ValidationError(f"Only open tickets can be escalated (ticket is {ticket.status.value})")

        auto = data.escalated_to_id is None
        if auto:
            suggestion = self.router.suggest(ticket)
            if not suggestion:
                raise ValidationError("No escalation contact is available to auto-assign")
            contact = suggestion.contact
        else:
            contact = self.users.get(data.escalated_to_id)
            if not contact or not contact.is_active or not contact.is_escalation_contact:
                raise ValidationError("Choose an active escalation contact")

        # Re-escalating supersedes the current escalation and moves one level up.
        previous = self.escalations.get_active_for_ticket(ticket_id)
        level = suggestion.level if auto else max(contact.escalation_level, 2)
        if previous:
            if previous.escalated_to_id == contact.id:
                raise ValidationError(f"Ticket is already escalated to {contact.name}")
            level = min(max(level, previous.level + 1), MAX_LEVEL)
            self._close(previous, f"Superseded by escalation to {contact.name}")

        escalation = self.escalations.add(
            Escalation(
                ticket_id=ticket.id,
                escalated_to_id=contact.id,
                escalated_by=data.escalated_by,
                level=level,
                reason=data.reason.strip(),
                source=source,
                auto_assigned=auto,
            )
        )
        if data.reassign:
            ticket.assignee = contact.name
        self._note(
            ticket,
            data.escalated_by,
            f"{'Auto-assigned' if auto else 'Escalated'} to {contact.name} ({contact.team}, L{level}).\n"
            f"Reason: {escalation.reason}",
        )
        self.db.commit()

        escalation.notification_sent = self.notifier.send_escalation(ticket, contact, escalation)
        if data.notify_customer:
            sent = self.notifier.send_customer_handoff(ticket, contact)
            escalation.customer_notified = sent is not None and sent.status == OutboundEmailStatus.SENT
            if escalation.customer_notified:
                # Show what the customer received in the public conversation.
                self.comments.add(Comment(ticket_id=ticket.id, author=self.notifier.settings.support_from_name,
                                          body=sent.body, is_internal=False, source=TicketSource.EMAIL))
        self.db.commit()
        self.db.refresh(escalation)
        return escalation

    def resolve(self, ticket_id: int, data: EscalationResolve, resolved_by: str = "Support Agent") -> Escalation:
        ticket = self._get_ticket(ticket_id)
        active = self.escalations.get_active_for_ticket(ticket_id)
        if not active:
            raise ValidationError("Ticket is not escalated")
        self._close(active, data.note)
        self._note(ticket, resolved_by, "De-escalated." + (f"\nNote: {data.note}" if data.note else ""))
        self.db.commit()
        self.db.refresh(active)
        return active

    def resolve_for_closed_ticket(self, ticket: Ticket) -> None:
        """Called when a ticket is resolved/closed. Does not commit."""
        active = self.escalations.get_active_for_ticket(ticket.id)
        if active:
            self._close(active, f"Ticket marked {ticket.status.value}")

    def suggest(self, ticket_id: int, preview_contact_id: int | None = None) -> EscalationSuggestionRead:
        """Auto-assignment pick plus the customer email preview — for the pick,
        or for `preview_contact_id` when the agent chooses someone manually."""
        ticket = self._get_ticket(ticket_id)
        suggestion = self.router.suggest(ticket)
        if not suggestion:
            raise ValidationError("No escalation contact is available")
        preview_contact = suggestion.contact
        if preview_contact_id is not None:
            preview_contact = self.users.get(preview_contact_id) or suggestion.contact
        subject, body = self.notifier.customer_handoff_message(ticket, preview_contact)
        return EscalationSuggestionRead(
            contact=UserRead.model_validate(suggestion.contact),
            level=suggestion.level,
            team=suggestion.team,
            reasons=suggestion.reasons,
            customer_email=EmailPreview(to=ticket.requester_email, subject=subject, body=body),
        )

    def list(self, status: EscalationStatus | None) -> list[Escalation]:
        return self.escalations.list(status)

    def list_for_ticket(self, ticket_id: int) -> list[Escalation]:
        self._get_ticket(ticket_id)
        return self.escalations.list_for_ticket(ticket_id)

    # ---- internals -------------------------------------------------------

    def _get_ticket(self, ticket_id: int) -> Ticket:
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    @staticmethod
    def _close(escalation: Escalation, note: str | None) -> None:
        escalation.status = EscalationStatus.RESOLVED
        escalation.resolved_at = datetime.now(timezone.utc)
        escalation.resolution_note = note

    def _note(self, ticket: Ticket, author: str, body: str) -> None:
        self.comments.add(Comment(ticket_id=ticket.id, author=author, body=body, is_internal=True))
