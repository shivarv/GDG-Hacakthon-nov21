from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dao.outbound_email_dao import OutboundEmailDAO
from app.services.notification_service import NotificationService

from app.controllers.dependencies import get_email_service
from app.schemas.common import Page
from app.schemas.email import (
    EmailIngestResult,
    EmailMessageRead,
    InboundEmail,
    InboxInfo,
    OutboundEmailRead,
    SmtpStatus,
    TestEmailRequest,
)
from app.services.email_ingestion_service import EmailIngestionService

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("", response_model=Page[EmailMessageRead])
def list_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: EmailIngestionService = Depends(get_email_service),
):
    return service.list_emails(page, page_size)


@router.get("/inbox", response_model=InboxInfo)
def inbox_info(request: Request):
    """The public address customers can email, when the temp inbox is enabled."""
    listener = getattr(request.app.state, "temp_inbox", None)
    return InboxInfo(enabled=listener is not None, address=listener.address if listener else None)


@router.post("/inbound", response_model=EmailIngestResult)
def inbound_email(
    email: InboundEmail, service: EmailIngestionService = Depends(get_email_service)
):
    """Webhook for inbound-email providers (SendGrid/Mailgun/etc.) or manual testing."""
    return service.ingest(email)


@router.get("/outbound", response_model=Page[OutboundEmailRead])
def list_outbound(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    items, total = OutboundEmailDAO(db).list_recent((page - 1) * page_size, page_size)
    return Page[OutboundEmailRead](
        items=[OutboundEmailRead.model_validate(e) for e in items], total=total, page=page, page_size=page_size
    )


@router.get("/smtp-status", response_model=SmtpStatus)
def smtp_status():
    return NotificationService().status()


@router.post("/test", response_model=OutboundEmailRead)
def send_test_email(data: TestEmailRequest, db: Session = Depends(get_db)):
    """Sends a test email so you can confirm SMTP delivery (e.g. to your Gmail)."""
    return NotificationService(db).send_test(str(data.to))
