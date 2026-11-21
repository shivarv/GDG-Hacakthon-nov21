from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import TicketPriority, TicketSource, TicketStatus
from app.schemas.comment import CommentRead


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    description: str = ""
    priority: TicketPriority = TicketPriority.MEDIUM
    requester_email: EmailStr
    requester_name: str | None = None
    assignee: str | None = None


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee: str | None = None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    source: TicketSource
    requester_email: str
    requester_name: str | None
    assignee: str | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketRead):
    comments: list[CommentRead] = []


class TicketStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_source: dict[str, int]
