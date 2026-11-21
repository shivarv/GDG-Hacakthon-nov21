from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dao.base_dao import BaseDAO
from app.models import Escalation, EscalationStatus


class EscalationDAO(BaseDAO[Escalation]):
    model = Escalation

    def get_active_for_ticket(self, ticket_id: int) -> Escalation | None:
        stmt = select(Escalation).where(
            Escalation.ticket_id == ticket_id, Escalation.status == EscalationStatus.ACTIVE
        )
        return self.db.scalars(stmt).first()

    def list_for_ticket(self, ticket_id: int) -> list[Escalation]:
        stmt = select(Escalation).where(Escalation.ticket_id == ticket_id).order_by(Escalation.created_at)
        return list(self.db.scalars(stmt).unique().all())

    def list(self, status: EscalationStatus | None = None) -> list[Escalation]:
        stmt = select(Escalation).options(selectinload(Escalation.ticket))
        if status:
            stmt = stmt.where(Escalation.status == status)
        return list(self.db.scalars(stmt.order_by(Escalation.created_at.desc())).unique().all())
