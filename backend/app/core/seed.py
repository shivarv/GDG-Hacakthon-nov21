"""Dummy support staff, loaded once when the users table is empty.
All addresses use the non-routable helpdesk.local domain."""

import logging

from sqlalchemy.orm import Session

from app.dao.user_dao import UserDAO
from app.models import User, UserRole

logger = logging.getLogger(__name__)

# (name, role, team, escalation level, is escalation contact)
DUMMY_USERS: list[tuple[str, UserRole, str, int, bool]] = [
    # Level 2: team leads, one per queue
    ("Priya Sharma", UserRole.TEAM_LEAD, "Technical Support", 2, True),
    ("Marcus Weber", UserRole.TEAM_LEAD, "IT Support", 2, True),
    ("Elena Rossi", UserRole.TEAM_LEAD, "Billing and Payments", 2, True),
    ("David Okafor", UserRole.TEAM_LEAD, "Customer Service", 2, True),
    ("Lena Fischer", UserRole.TEAM_LEAD, "Product Support", 2, True),
    # Level 3: managers, on-call and security
    ("Hannah Schmidt", UserRole.MANAGER, "Customer Service", 3, True),
    ("Thomas Becker", UserRole.MANAGER, "Head of Support", 3, True),
    ("Raj Patel", UserRole.ON_CALL, "Service Outages and Maintenance", 3, True),
    ("Sofia Martinez", UserRole.SECURITY, "Information Security", 3, True),
    # Level 1: frontline agents (not escalation targets)
    ("Alex Kim", UserRole.AGENT, "Technical Support", 1, False),
    ("Jordan Lee", UserRole.AGENT, "Customer Service", 1, False),
]


def _email(name: str) -> str:
    return name.lower().replace(" ", ".") + "@helpdesk.local"


def seed_users(db: Session) -> None:
    dao = UserDAO(db)
    if dao.count():
        return
    for name, role, team, level, contact in DUMMY_USERS:
        db.add(User(name=name, email=_email(name), role=role, team=team,
                    escalation_level=level, is_escalation_contact=contact))
    db.commit()
    logger.info("Seeded %d dummy users", len(DUMMY_USERS))
