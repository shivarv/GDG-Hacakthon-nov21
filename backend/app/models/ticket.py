from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.database import Base
from app.core.types import UTCDateTime
from app.models.enums import TicketPriority, TicketSource, TicketStatus


def _enum(e):
    return Enum(e, values_callable=lambda x: [m.value for m in x], native_enum=False, length=32)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TicketStatus] = mapped_column(_enum(TicketStatus), default=TicketStatus.OPEN, index=True)
    priority: Mapped[TicketPriority] = mapped_column(
        _enum(TicketPriority), default=TicketPriority.MEDIUM, index=True
    )
    source: Mapped[TicketSource] = mapped_column(_enum(TicketSource), default=TicketSource.WEB)
    requester_email: Mapped[str] = mapped_column(String(320), index=True)
    requester_name: Mapped[str | None] = mapped_column(String(200))
    assignee: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    comments: Mapped[list["Comment"]] = relationship(  # noqa: F821
        back_populates="ticket", cascade="all, delete-orphan", order_by="Comment.created_at"
    )
    emails: Mapped[list["EmailMessage"]] = relationship(back_populates="ticket")  # noqa: F821

    @property
    def ticket_number(self) -> str:
        return f"{get_settings().ticket_prefix}-{self.id}"
