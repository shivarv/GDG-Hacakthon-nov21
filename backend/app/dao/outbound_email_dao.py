from __future__ import annotations

from sqlalchemy import func, select

from app.dao.base_dao import BaseDAO
from app.models import OutboundEmail


class OutboundEmailDAO(BaseDAO[OutboundEmail]):
    model = OutboundEmail

    def list_recent(self, offset: int = 0, limit: int = 20) -> tuple[list[OutboundEmail], int]:
        total = self.db.scalar(select(func.count(OutboundEmail.id))) or 0
        items = self.db.scalars(
            select(OutboundEmail).order_by(OutboundEmail.created_at.desc(), OutboundEmail.id.desc()).offset(offset).limit(limit)
        ).all()
        return list(items), total
