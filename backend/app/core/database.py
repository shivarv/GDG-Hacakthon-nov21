from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()

    from app.core.seed import seed_users

    with SessionLocal() as db:
        seed_users(db)


# create_all() creates new tables but never adds columns to existing ones.
# Until Alembic is introduced, additive columns are listed here and applied on startup.
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("users", "phone", "VARCHAR(40)"),
    ("escalations", "customer_notified", "BOOLEAN DEFAULT FALSE"),
    ("escalations", "auto_assigned", "BOOLEAN DEFAULT FALSE"),
    ("escalations", "first_response_due_at", "TIMESTAMP"),
    ("escalations", "resolution_due_at", "TIMESTAMP"),
    ("escalations", "eta_model", "VARCHAR(64)"),
]


def _add_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, column, ddl in _ADDITIVE_COLUMNS:
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
