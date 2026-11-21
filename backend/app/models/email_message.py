from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import UTCDateTime
from app.models.enums import EmailProcessingStatus
from app.models.ticket import _enum


class EmailMessage(Base):
    """Raw record of every inbound email, kept for audit and reply threading."""

    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(998), unique=True, index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(998))
    from_address: Mapped[str] = mapped_column(String(320))
    from_name: Mapped[str | None] = mapped_column(String(200))
    to_address: Mapped[str | None] = mapped_column(String(1000))
    subject: Mapped[str] = mapped_column(String(1000), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    processing_status: Mapped[EmailProcessingStatus] = mapped_column(_enum(EmailProcessingStatus))
    error: Mapped[str | None] = mapped_column(Text)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    ticket: Mapped["Ticket | None"] = relationship(back_populates="emails")  # noqa: F821
