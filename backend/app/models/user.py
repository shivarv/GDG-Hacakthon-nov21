from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import UserRole
from app.models.ticket import _enum


class User(Base):
    """Support staff. Escalation contacts receive escalated tickets."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole))
    team: Mapped[str] = mapped_column(String(200))
    # 1 = frontline agent, 2 = team lead, 3 = manager / on-call / security
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    is_escalation_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
