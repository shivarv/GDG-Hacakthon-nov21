from sqlalchemy import func, select

from app.dao.base_dao import BaseDAO
from app.models import EmailMessage


class EmailDAO(BaseDAO[EmailMessage]):
    model = EmailMessage

    def get_by_message_id(self, message_id: str) -> EmailMessage | None:
        return self.db.scalars(
            select(EmailMessage).where(EmailMessage.message_id == message_id)
        ).first()

    def list_recent(self, offset: int = 0, limit: int = 20) -> tuple[list[EmailMessage], int]:
        total = self.db.scalar(select(func.count(EmailMessage.id))) or 0
        items = self.db.scalars(
            select(EmailMessage).order_by(EmailMessage.received_at.desc()).offset(offset).limit(limit)
        ).all()
        return list(items), total

    def list_for_ticket(self, ticket_id: int) -> list[EmailMessage]:
        stmt = (
            select(EmailMessage)
            .where(EmailMessage.ticket_id == ticket_id)
            .order_by(EmailMessage.received_at)
        )
        return list(self.db.scalars(stmt).all())
