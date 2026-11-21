from __future__ import annotations

from sqlalchemy.orm import Session

from app.dao.user_dao import UserDAO
from app.models import User


class UserService:
    def __init__(self, db: Session):
        self.users = UserDAO(db)

    def list(self, escalation_contacts_only: bool = False) -> list[User]:
        return self.users.list(escalation_contacts_only)
