from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EscalationSource, EscalationStatus, TicketPriority, TicketStatus
from app.schemas.user import UserRead


class EscalationCreate(BaseModel):
    # Omit to let the router auto-assign the best contact.
    escalated_to_id: int | None = None
    reason: str = Field(min_length=3)
    escalated_by: str = "Support Agent"
    reassign: bool = True  # make the escalation contact the ticket assignee
    notify_customer: bool = True  # email the requester who is now handling the ticket


class EscalationResolve(BaseModel):
    note: str | None = None


class EscalationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    escalated_to: UserRead
    escalated_by: str
    level: int
    reason: str
    status: EscalationStatus
    source: EscalationSource
    notification_sent: bool
    customer_notified: bool = False
    auto_assigned: bool = False
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None


class EscalatedTicketSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    subject: str
    status: TicketStatus
    priority: TicketPriority
    requester_email: str
    requester_name: str | None


class EscalationWithTicket(EscalationRead):
    ticket: EscalatedTicketSummary


class EmailPreview(BaseModel):
    to: str
    subject: str
    body: str


class EscalationSuggestionRead(BaseModel):
    contact: UserRead
    level: int
    team: str
    reasons: list[str]
    customer_email: EmailPreview
