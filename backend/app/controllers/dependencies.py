from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.comment_service import CommentService
from app.services.email_ingestion_service import EmailIngestionService
from app.services.ticket_service import TicketService


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)


def get_comment_service(db: Session = Depends(get_db)) -> CommentService:
    return CommentService(db)


def get_email_service(db: Session = Depends(get_db)) -> EmailIngestionService:
    return EmailIngestionService(db)
