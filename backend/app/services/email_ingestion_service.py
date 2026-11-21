import logging

from sqlalchemy.orm import Session

from app.dao.comment_dao import CommentDAO
from app.dao.email_dao import EmailDAO
from app.dao.ticket_dao import TicketDAO
from app.models import (
    Comment,
    EmailMessage,
    EmailProcessingStatus,
    Ticket,
    TicketSource,
    TicketStatus,
)
from app.schemas.common import Page
from app.schemas.email import EmailIngestResult, EmailMessageRead, InboundEmail
from app.services import email_parser
from app.services.notification_service import NotificationService
from app.services.triage import get_triage_model

logger = logging.getLogger(__name__)


class EmailIngestionService:
    """Converts inbound emails into cases.

    - New conversation         -> new Ticket (source=email, priority auto-detected)
    - Reply to existing case   -> Comment on that Ticket (matched by [TCK-n] subject
                                  tag or In-Reply-To header); resolved/closed cases reopen
    - Duplicate Message-ID     -> ignored (idempotent), returns the original result
    """

    def __init__(self, db: Session, notifier: NotificationService | None = None):
        self.db = db
        self.emails = EmailDAO(db)
        self.tickets = TicketDAO(db)
        self.comments = CommentDAO(db)
        self.notifier = notifier or NotificationService(db)

    def ingest(self, inbound: InboundEmail) -> EmailIngestResult:
        message_id = inbound.message_id or email_parser.generate_message_id()

        existing = self.emails.get_by_message_id(message_id)
        if existing:
            logger.info("Skipping duplicate email %s", message_id)
            return self._result(existing)

        if inbound.sent_by_us or email_parser.is_bounce_address(str(inbound.from_address)):
            # Our own email came back (e.g. via Gmail forwarding) or a bounce notice: record it, do nothing.
            logger.info("Ignoring looped-back email or bounce: %s", inbound.subject)
            record = self.emails.add(self._record(inbound, message_id, EmailProcessingStatus.IGNORED))
            self.db.commit()
            return self._result(record)

        try:
            ticket = self._find_existing_ticket(inbound)
            if ticket:
                self._append_reply(ticket, inbound)
                status = EmailProcessingStatus.APPENDED_COMMENT
                created = False
            else:
                ticket = self._create_ticket(inbound)
                status = EmailProcessingStatus.CREATED_TICKET
                created = True

            record = self.emails.add(self._record(inbound, message_id, status, ticket_id=ticket.id))
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.exception("Failed to ingest email %s", message_id)
            record = self.emails.add(
                self._record(inbound, message_id, EmailProcessingStatus.FAILED, error=str(exc))
            )
            self.db.commit()
            return self._result(record)

        if created:
            self._triage_note(ticket)
            self._add_rag_note(ticket)
            self.db.commit()
        is_automatic = inbound.auto_generated or email_parser.is_no_reply_address(str(inbound.from_address))
        if created and not is_automatic:
            # Severe tickets are escalated straight away; the escalation email replaces the plain acknowledgement.
            if not self._auto_escalate(ticket):
                self.notifier.send_ticket_created(ticket)
        return self._result(record)

    def list_emails(self, page: int, page_size: int) -> Page[EmailMessageRead]:
        items, total = self.emails.list_recent((page - 1) * page_size, page_size)
        return Page[EmailMessageRead](
            items=[EmailMessageRead.model_validate(e) for e in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_for_ticket(self, ticket_id: int) -> list[EmailMessage]:
        return self.emails.list_for_ticket(ticket_id)

    # ---- internals -------------------------------------------------------

    def _triage(self, subject: str, body: str):
        """Run the configured triage model once per email. If it fails, fall back to keyword rules
        for this one ticket so the email is never lost."""
        if not hasattr(self, "_decision"):
            name = self.notifier.settings.triage_model
            try:
                self._decision = get_triage_model(name).assess(subject, body)
            except Exception as exc:
                logger.exception("Triage model %s failed; using keyword rules for this ticket", name)
                self._decision = get_triage_model("dummy").assess(subject, body)
                self._decision.reasons.insert(0, f"Triage model {name} unavailable ({exc}); keyword rules used")
        return self._decision

    def _triage_note(self, ticket: Ticket) -> None:
        d = self._triage(ticket.subject, ticket.description)
        lines = [f"Triage ({d.model}): priority {d.priority.value}, "
                 + ("escalation recommended" if d.should_escalate else "no escalation")]
        lines += [f"• {r}" for r in d.reasons]
        self.comments.add(Comment(ticket_id=ticket.id, author="Triage", body="\n".join(lines), is_internal=True))
        self.db.commit()

    def _add_rag_note(self, ticket: Ticket) -> None:
        """Attach the grounded suggested reply + cited precedents as an internal note (best effort)."""
        try:
            rag = getattr(self._triage(ticket.subject, ticket.description), "rag", None)
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

    def _auto_escalate(self, ticket: Ticket) -> bool:
        """Escalate a new ticket when the triage model says it's severe. Returns True if escalated."""
        decision = self._triage(ticket.subject, ticket.description)
        if not (self.notifier.settings.auto_escalate and decision.should_escalate):
            return False
        # Local import avoids a cycle (escalation service -> notification -> ...).
        from app.models import EscalationSource
        from app.schemas.escalation import EscalationCreate
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
            logger.exception("Auto-escalation failed for %s; sending a normal acknowledgement", ticket.ticket_number)
            return False

    def _find_existing_ticket(self, inbound: InboundEmail) -> Ticket | None:
        ticket_id = email_parser.extract_ticket_id(inbound.subject)
        if ticket_id:
            ticket = self.tickets.get(ticket_id)
            if ticket:
                return ticket
        if inbound.in_reply_to:
            parent = self.emails.get_by_message_id(inbound.in_reply_to)
            if parent and parent.ticket_id:
                return self.tickets.get(parent.ticket_id)
        return None

    def _create_ticket(self, inbound: InboundEmail) -> Ticket:
        subject = email_parser.clean_subject(inbound.subject, inbound.body_text)
        return self.tickets.add(
            Ticket(
                subject=subject[:500],
                description=inbound.body_text,
                priority=self._triage(subject, inbound.body_text).priority,
                predicted_type=self._triage(subject, inbound.body_text).ticket_type,
                predicted_queue=self._triage(subject, inbound.body_text).queue,
                queue_confidence=self._triage(subject, inbound.body_text).queue_confidence,
                triage_model=self._triage(subject, inbound.body_text).model,
                source=TicketSource.EMAIL,
                requester_email=str(inbound.from_address),
                requester_name=inbound.from_name,
            )
        )

    def _append_reply(self, ticket: Ticket, inbound: InboundEmail) -> None:
        self.comments.add(
            Comment(
                ticket_id=ticket.id,
                author=str(inbound.from_address),
                body=email_parser.strip_quoted_reply(inbound.body_text),
                source=TicketSource.EMAIL,
            )
        )
        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED, TicketStatus.PENDING):
            ticket.status = TicketStatus.OPEN
        self.db.flush()

    @staticmethod
    def _record(
        inbound: InboundEmail,
        message_id: str,
        status: EmailProcessingStatus,
        ticket_id: int | None = None,
        error: str | None = None,
    ) -> EmailMessage:
        return EmailMessage(
            message_id=message_id,
            in_reply_to=inbound.in_reply_to,
            from_address=str(inbound.from_address),
            from_name=inbound.from_name,
            to_address=inbound.to_address,
            subject=inbound.subject[:1000],
            body_text=inbound.body_text,
            processing_status=status,
            ticket_id=ticket_id,
            error=error,
        )

    def _result(self, record: EmailMessage) -> EmailIngestResult:
        ticket = self.tickets.get(record.ticket_id) if record.ticket_id else None
        return EmailIngestResult(
            email_id=record.id,
            ticket_id=record.ticket_id,
            ticket_number=ticket.ticket_number if ticket else None,
            action=record.processing_status,
        )
