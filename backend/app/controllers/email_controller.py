from fastapi import APIRouter, Depends, Query

from app.controllers.dependencies import get_email_service
from app.schemas.common import Page
from app.schemas.email import EmailIngestResult, EmailMessageRead, InboundEmail
from app.services.email_ingestion_service import EmailIngestionService

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("", response_model=Page[EmailMessageRead])
def list_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: EmailIngestionService = Depends(get_email_service),
):
    return service.list_emails(page, page_size)


@router.post("/inbound", response_model=EmailIngestResult)
def inbound_email(
    email: InboundEmail, service: EmailIngestionService = Depends(get_email_service)
):
    """Webhook for inbound-email providers (SendGrid/Mailgun/etc.) or manual testing."""
    return service.ingest(email)
