from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.dao.base_dao import BaseDAO
from app.models import Ticket, TicketPriority, TicketSource, TicketStatus


class TicketDAO(BaseDAO[Ticket]):
    model = Ticket

    def get_with_comments(self, ticket_id: int) -> Ticket | None:
        stmt = select(Ticket).options(selectinload(Ticket.comments)).where(Ticket.id == ticket_id)
        return self.db.scalars(stmt).first()

    def search(
        self,
        *,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        source: TicketSource | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Ticket], int]:
        stmt = select(Ticket)
        if status:
            stmt = stmt.where(Ticket.status == status)
        if priority:
            stmt = stmt.where(Ticket.priority == priority)
        if source:
            stmt = stmt.where(Ticket.source == source)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Ticket.subject.ilike(like),
                    Ticket.description.ilike(like),
                    Ticket.requester_email.ilike(like),
                )
            )

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(
            stmt.order_by(Ticket.updated_at.desc()).offset(offset).limit(limit)
        ).all()
        return list(items), total

    def count_by(self, column) -> dict[str, int]:
        rows = self.db.execute(select(column, func.count()).group_by(column)).all()
        return {(k.value if hasattr(k, "value") else str(k)): v for k, v in rows}

    def count_all(self) -> int:
        return self.db.scalar(select(func.count(Ticket.id))) or 0
