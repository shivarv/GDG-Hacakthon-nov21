"""German customer handling: language detection, priority keywords, customer-facing emails."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import TicketPriority  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.services.email_parser import detect_priority  # noqa: E402
from app.services.language import detect_language  # noqa: E402
from app.services.notification_service import NotificationService  # noqa: E402


def _ticket(subject, description, name="Max Mustermann"):
    return SimpleNamespace(id=1, ticket_number="TCK-7", subject=subject, description=description,
                           requester_name=name, requester_email="max@example.de",
                           priority=TicketPriority.URGENT)


CONTACT = SimpleNamespace(name="Raj Patel", email="raj@helpdesk.local", phone="+1 555-0113",
                          role=UserRole.ON_CALL, team="Service Outages and Maintenance")
ETA = SimpleNamespace(first_response_due_at=datetime(2026, 11, 21, 15, 30, tzinfo=timezone.utc),
                      resolution_due_at=datetime(2026, 11, 21, 19, 5, tzinfo=timezone.utc))


def test_detect_language():
    assert detect_language("VPN Ausfall", "Unser VPN ist komplett ausgefallen, bitte helfen Sie uns.") == "de"
    assert detect_language("Passwort vergessen", "Ich kann mich nicht anmelden.") == "de"
    assert detect_language("VPN down", "Our VPN is down, please help us.") == "en"
    assert detect_language(None, "") == "en"


def test_german_priority_keywords():
    assert detect_priority("VPN Ausfall", "Das VPN ist ausgefallen.") == TicketPriority.URGENT
    assert detect_priority("Dringend", "Bitte sofort prüfen.") == TicketPriority.URGENT
    assert detect_priority("Drucker", "Der Drucker funktioniert nicht.") == TicketPriority.HIGH
    assert detect_priority("Frage", "Wie ändere ich mein Profilbild?") == TicketPriority.MEDIUM


def test_german_handoff_email_is_german_and_portable():
    subject, body = NotificationService().customer_handoff_message(
        _ticket("VPN Ausfall", "Unser VPN ist komplett ausgefallen."), CONTACT, 3, ETA)
    assert "Ihr Ticket wurde eskaliert" in subject
    assert body.startswith("Hallo Max,")
    assert "Priorität:  Dringend" in body and "Stufe 3" in body
    assert "Bereitschaftstechniker" in body
    assert "Mit freundlichen Grüßen" in body
    assert "Thank you" not in body
    assert "21.11.2026" in body  # German date format, no OS-locale dependency


def test_english_handoff_email_still_english():
    subject, body = NotificationService().customer_handoff_message(
        _ticket("VPN down", "Our VPN is down for everyone."), CONTACT, 3, ETA)
    assert "Your ticket has been escalated" in subject
    assert body.startswith("Hi Max,") and "Kind regards," in body
