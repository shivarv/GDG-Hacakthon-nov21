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
                priority=email_parser.detect_priority(subject, inbound.body_text),
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
