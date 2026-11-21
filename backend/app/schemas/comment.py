from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketSource


class CommentCreate(BaseModel):
    author: str = Field(min_length=1, max_length=320)
    body: str = Field(min_length=1)
    is_internal: bool = False
    notify_customer: bool = True  # email public replies to the requester


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author: str
    body: str
    is_internal: bool
    source: TicketSource
    created_at: datetime
    # Only set on the response to creating a public reply: what happened to the email.
    email_status: str | None = None
    email_error: str | None = None
