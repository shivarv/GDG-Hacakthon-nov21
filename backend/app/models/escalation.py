from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, and_, exists, func
from sqlalchemy.orm import Mapped, backref, column_property, mapped_column, relationship

from app.core.database import Base
from app.core.types import UTCDateTime
from app.models.enums import EscalationSource, EscalationStatus
from app.models.ticket import Ticket, _enum
from app.models.user import User


class Escalation(Base):
    """One escalation event. A ticket counts as escalated while it has an ACTIVE row."""

    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    escalated_to_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    escalated_by: Mapped[str] = mapped_column(String(200))
    level: Mapped[int] = mapped_column(Integer, default=2)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[EscalationStatus] = mapped_column(
        _enum(EscalationStatus), default=EscalationStatus.ACTIVE, index=True
    )
    source: Mapped[EscalationSource] = mapped_column(_enum(EscalationSource), default=EscalationSource.MANUAL)
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_assigned: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    first_response_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolution_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    eta_model: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    escalated_to: Mapped[User] = relationship(lazy="joined")
    ticket: Mapped[Ticket] = relationship(
        backref=backref("escalations", order_by="Escalation.created_at", cascade="all, delete-orphan")
    )


# Computed in SQL, so it needs no column on `tickets` and works for filtering too.
Ticket.is_escalated = column_property(
    exists().where(
        and_(Escalation.ticket_id == Ticket.id, Escalation.status == EscalationStatus.ACTIVE)
    )
)
