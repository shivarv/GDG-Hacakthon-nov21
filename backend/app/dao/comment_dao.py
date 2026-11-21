from sqlalchemy import select

from app.dao.base_dao import BaseDAO
from app.models import Comment


class CommentDAO(BaseDAO[Comment]):
    model = Comment

    def list_for_ticket(self, ticket_id: int) -> list[Comment]:
        stmt = select(Comment).where(Comment.ticket_id == ticket_id).order_by(Comment.created_at)
        return list(self.db.scalars(stmt).all())
