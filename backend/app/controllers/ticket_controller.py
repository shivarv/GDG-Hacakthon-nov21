from fastapi import APIRouter, Depends, Query, status

from app.controllers.dependencies import (
    get_comment_service,
    get_email_service,
    get_escalation_service,
    get_ticket_service,
)
from app.models import TicketPriority, TicketSource, TicketStatus
from app.schemas.comment import CommentCreate, CommentRead
from app.schemas.common import Page
from app.schemas.email import EmailMessageRead
from app.schemas.escalation import EscalationCreate, EscalationRead, EscalationResolve, EscalationSuggestionRead
from app.schemas.ticket import TicketCreate, TicketDetail, TicketRead, TicketStats, TicketUpdate
from app.services.comment_service import CommentService
from app.services.email_ingestion_service import EmailIngestionService
from app.services.escalation_service import EscalationService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=Page[TicketRead])
def list_tickets(
    status_: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    source: TicketSource | None = None,
    q: str | None = None,
    escalated: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: TicketService = Depends(get_ticket_service),
):
    return service.list(
        status=status_,
        priority=priority,
        source=source,
        query=q,
        escalated=escalated,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=TicketStats)
def ticket_stats(service: TicketService = Depends(get_ticket_service)):
    return service.stats()


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, service: TicketService = Depends(get_ticket_service)):
    return service.create(data)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, service: TicketService = Depends(get_ticket_service)):
    return service.get(ticket_id)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int, data: TicketUpdate, service: TicketService = Depends(get_ticket_service)
):
    return service.update(ticket_id, data)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: int, service: TicketService = Depends(get_ticket_service)):
    service.delete(ticket_id)


@router.get("/{ticket_id}/comments", response_model=list[CommentRead])
def list_comments(ticket_id: int, service: CommentService = Depends(get_comment_service)):
    return service.list(ticket_id)


@router.post(
    "/{ticket_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED
)
def add_comment(
    ticket_id: int, data: CommentCreate, service: CommentService = Depends(get_comment_service)
):
    return service.add(ticket_id, data)


@router.get("/{ticket_id}/emails", response_model=list[EmailMessageRead])
def ticket_emails(ticket_id: int, service: EmailIngestionService = Depends(get_email_service)):
    return service.list_for_ticket(ticket_id)


@router.get("/{ticket_id}/escalations", response_model=list[EscalationRead])
def ticket_escalations(ticket_id: int, service: EscalationService = Depends(get_escalation_service)):
    return service.list_for_ticket(ticket_id)


@router.post("/{ticket_id}/escalate", response_model=EscalationRead, status_code=status.HTTP_201_CREATED)
def escalate_ticket(
    ticket_id: int, data: EscalationCreate, service: EscalationService = Depends(get_escalation_service)
):
    return service.escalate(ticket_id, data)


@router.post("/{ticket_id}/de-escalate", response_model=EscalationRead)
def de_escalate_ticket(
    ticket_id: int, data: EscalationResolve, service: EscalationService = Depends(get_escalation_service)
):
    return service.resolve(ticket_id, data)


@router.get("/{ticket_id}/escalation-suggestion", response_model=EscalationSuggestionRead)
def escalation_suggestion(
    ticket_id: int, contact_id: int | None = None, service: EscalationService = Depends(get_escalation_service)
):
    """Who auto-assignment would pick, why, and the email the customer would receive
    (for `contact_id` if given, otherwise for the pick)."""
    return service.suggest(ticket_id, contact_id)
