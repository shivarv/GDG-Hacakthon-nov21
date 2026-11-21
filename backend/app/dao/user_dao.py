from __future__ import annotations

from sqlalchemy import func, select

from app.dao.base_dao import BaseDAO
from app.models import User


class UserDAO(BaseDAO[User]):
    model = User

    def list(self, escalation_contacts_only: bool = False) -> list[User]:
        stmt = select(User).where(User.is_active.is_(True))
        if escalation_contacts_only:
            stmt = stmt.where(User.is_escalation_contact.is_(True))
        return list(self.db.scalars(stmt.order_by(User.escalation_level, User.team, User.name)).all())

    def count(self) -> int:
        return self.db.scalar(select(func.count(User.id))) or 0
