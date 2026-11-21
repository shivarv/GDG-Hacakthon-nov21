from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.dao.comment_dao import CommentDAO
from app.dao.ticket_dao import TicketDAO
from app.models import Comment, TicketSource
from app.schemas.comment import CommentCreate
from app.services.notification_service import NotificationService


class CommentService:
    def __init__(self, db: Session):
        self.db = db
        self.comments = CommentDAO(db)
        self.tickets = TicketDAO(db)

    def list(self, ticket_id: int) -> list[Comment]:
        self._ensure_ticket(ticket_id)
        return self.comments.list_for_ticket(ticket_id)

    def add(self, ticket_id: int, data: CommentCreate) -> Comment:
        ticket = self._ensure_ticket(ticket_id)
        comment = self.comments.add(
            Comment(ticket_id=ticket.id, source=TicketSource.WEB, **data.model_dump(exclude={"notify_customer"}))
        )
        self.db.commit()

        # Public replies go to the customer by email (via Brevo/SMTP); internal notes never do.
        if not comment.is_internal and data.notify_customer:
            sent = NotificationService(self.db).send_agent_reply(ticket, comment.author, comment.body)
            if sent is not None:
                comment.email_status = sent.status.value  # transient, returned to the caller only
                comment.email_error = sent.error
        return comment

    def _ensure_ticket(self, ticket_id: int):
        ticket = self.tickets.get(ticket_id)
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket
