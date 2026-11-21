from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseDAO(Generic[ModelT]):
    """Generic data-access object. DAOs flush but never commit;
    the service layer owns the transaction boundary."""

    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, entity_id: int) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.flush()
