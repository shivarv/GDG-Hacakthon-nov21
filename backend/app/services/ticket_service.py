from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.dao.ticket_dao import TicketDAO
from app.models import Ticket, TicketPriority, TicketSource, TicketStatus
from app.schemas.common import Page
from app.schemas.ticket import TicketCreate, TicketRead, TicketStats, TicketUpdate


class TicketService:
    def __init__(self, db: Session):
        self.db = db
        self.tickets = TicketDAO(db)

    def create(self, data: TicketCreate, source: TicketSource = TicketSource.WEB) -> Ticket:
        ticket = self.tickets.add(Ticket(**data.model_dump(), source=source))
        self.db.commit()
        return ticket

    def get(self, ticket_id: int) -> Ticket:
        ticket = self.tickets.get_with_comments(ticket_id)
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    def list(
        self,
        *,
        status: TicketStatus | None,
        priority: TicketPriority | None,
        source: TicketSource | None,
        query: str | None,
        page: int,
        escalated: bool | None = None,
        page_size: int,
    ) -> Page[TicketRead]:
        items, total = self.tickets.search(
            status=status,
            priority=priority,
            source=source,
            query=query,
            escalated=escalated,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return Page[TicketRead](
            items=[TicketRead.model_validate(t) for t in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def update(self, ticket_id: int, data: TicketUpdate) -> Ticket:
        ticket = self.get(ticket_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(ticket, field, value)
        if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            # Local import: EscalationService depends on this module's siblings.
            from app.services.escalation_service import EscalationService

            EscalationService(self.db).resolve_for_closed_ticket(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def delete(self, ticket_id: int) -> None:
        ticket = self.get(ticket_id)
        self.tickets.delete(ticket)
        self.db.commit()

    def stats(self) -> TicketStats:
        return TicketStats(
            total=self.tickets.count_all(),
            escalated=self.tickets.count_escalated(),
            by_status=self.tickets.count_by(Ticket.status),
            by_priority=self.tickets.count_by(Ticket.priority),
            by_source=self.tickets.count_by(Ticket.source),
        )
