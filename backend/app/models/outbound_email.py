from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime
from app.models.enums import OutboundEmailKind, OutboundEmailStatus
from app.models.ticket import _enum


class OutboundEmail(Base):
    """Every email the system tries to send, whether or not delivery succeeded."""

    __tablename__ = "outbound_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
    kind: Mapped[OutboundEmailKind] = mapped_column(_enum(OutboundEmailKind))
    to_address: Mapped[str] = mapped_column(String(320))
    from_address: Mapped[str] = mapped_column(String(320))
    reply_to: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(1000))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[OutboundEmailStatus] = mapped_column(_enum(OutboundEmailStatus))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
