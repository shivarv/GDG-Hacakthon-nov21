from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import EmailProcessingStatus, OutboundEmailKind, OutboundEmailStatus


class InboundEmail(BaseModel):
    """Normalized email, produced by the IMAP parser or posted to the webhook."""

    from_address: EmailStr
    from_name: str | None = None
    to_address: str | None = None
    subject: str = ""
    body_text: str = ""
    message_id: str | None = None
    in_reply_to: str | None = None


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: str
    in_reply_to: str | None
    from_address: str
    from_name: str | None
    to_address: str | None
    subject: str
    body_text: str
    processing_status: EmailProcessingStatus
    error: str | None
    ticket_id: int | None
    received_at: datetime


class EmailIngestResult(BaseModel):
    email_id: int
    ticket_id: int | None
    ticket_number: str | None
    action: EmailProcessingStatus


class InboxInfo(BaseModel):
    enabled: bool
    address: str | None


class OutboundEmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int | None
    kind: OutboundEmailKind
    to_address: str
    from_address: str
    reply_to: str | None
    subject: str
    body: str
    status: OutboundEmailStatus
    error: str | None
    created_at: datetime


class SmtpStatus(BaseModel):
    enabled: bool
    host: str | None
    from_address: str
    reply_to: str


class TestEmailRequest(BaseModel):
    to: EmailStr
