from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EscalationSource, EscalationStatus, TicketPriority, TicketStatus
from app.schemas.user import UserRead


class EscalationCreate(BaseModel):
    escalated_to_id: int
    reason: str = Field(min_length=3)
    escalated_by: str = "Support Agent"
    reassign: bool = True  # make the escalation contact the ticket assignee


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
