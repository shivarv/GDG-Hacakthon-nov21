"""Dummy support staff, loaded once when the users table is empty.
All addresses use the non-routable helpdesk.local domain, and phone numbers
use the +1 555-01xx range reserved for fictional use."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.user_dao import UserDAO
from app.models import User, UserRole

logger = logging.getLogger(__name__)

# (name, role, team, escalation level, is escalation contact, phone)
DUMMY_USERS: list[tuple[str, UserRole, str, int, bool, str]] = [
    # Level 2: team leads, one per queue
    ("Priya Sharma", UserRole.TEAM_LEAD, "Technical Support", 2, True, "+1 555-0101"),
    ("Marcus Weber", UserRole.TEAM_LEAD, "IT Support", 2, True, "+1 555-0102"),
    ("Elena Rossi", UserRole.TEAM_LEAD, "Billing and Payments", 2, True, "+1 555-0103"),
    ("David Okafor", UserRole.TEAM_LEAD, "Customer Service", 2, True, "+1 555-0104"),
    ("Lena Fischer", UserRole.TEAM_LEAD, "Product Support", 2, True, "+1 555-0105"),
    # Level 3: managers, on-call and security
    ("Hannah Schmidt", UserRole.MANAGER, "Customer Service", 3, True, "+1 555-0111"),
    ("Thomas Becker", UserRole.MANAGER, "Head of Support", 3, True, "+1 555-0112"),
    ("Raj Patel", UserRole.ON_CALL, "Service Outages and Maintenance", 3, True, "+1 555-0113"),
    ("Sofia Martinez", UserRole.SECURITY, "Information Security", 3, True, "+1 555-0114"),
    # Level 1: frontline agents (not escalation targets)
    ("Alex Kim", UserRole.AGENT, "Technical Support", 1, False, "+1 555-0121"),
    ("Jordan Lee", UserRole.AGENT, "Customer Service", 1, False, "+1 555-0122"),
]


def _email(name: str) -> str:
    return name.lower().replace(" ", ".") + "@helpdesk.local"


def seed_users(db: Session) -> None:
    dao = UserDAO(db)
    if not dao.count():
        for name, role, team, level, contact, phone in DUMMY_USERS:
            db.add(User(name=name, email=_email(name), phone=phone, role=role, team=team,
                        escalation_level=level, is_escalation_contact=contact))
        db.commit()
        logger.info("Seeded %d dummy users", len(DUMMY_USERS))
        return

    # Databases seeded before phone numbers existed: fill them in.
    phones = {_email(name): phone for name, *_, phone in DUMMY_USERS}
    updated = 0
    for user in db.scalars(select(User).where(User.phone.is_(None))):
        if user.email in phones:
            user.phone = phones[user.email]
            updated += 1
    if updated:
        db.commit()
        logger.info("Backfilled phone numbers for %d users", updated)
