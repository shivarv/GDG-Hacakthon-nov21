import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.models import Escalation, Ticket, User

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends acknowledgement emails. The [TCK-n] tag in the subject lets
    customer replies thread back onto the same case."""

    def __init__(self):
        self.settings = get_settings()

    def send_ticket_created(self, ticket: Ticket) -> None:
        body = (
            f"Hi {ticket.requester_name or 'there'},\n\n"
            f"Thanks for contacting support. We've opened case {ticket.ticket_number} "
            f"for your request and will get back to you shortly.\n\n"
            f"Reply to this email to add more information to your case.\n\n"
            f"— Support Team"
        )
        self._send(ticket.requester_email, f"[{ticket.ticket_number}] {ticket.subject}", body)

    def send_escalation(self, ticket: Ticket, contact: User, escalation: Escalation) -> bool:
        body = (
            f"Hi {contact.name.split()[0]},\n\n"
            f"Case {ticket.ticket_number} has been escalated to you (level L{escalation.level}).\n\n"
            f"Subject:   {ticket.subject}\n"
            f"Priority:  {ticket.priority.value}\n"
            f"Requester: {ticket.requester_name or ''} <{ticket.requester_email}>\n"
            f"Escalated by: {escalation.escalated_by}\n\n"
            f"Reason:\n{escalation.reason}\n\n"
            f"— HelpDesk"
        )
        subject = f"[Escalation L{escalation.level}] [{ticket.ticket_number}] {ticket.subject}"
        logger.info("Escalation email -> %s: %s", contact.email, subject)
        return self._send(contact.email, subject, body)

    def _send(self, to: str, subject: str, body: str) -> bool:
        s = self.settings
        if not s.smtp_enabled:
            return False
        msg = EmailMessage()
        msg["From"] = s.support_from_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
                if s.smtp_use_tls:
                    smtp.starttls()
                if s.smtp_username:
                    smtp.login(s.smtp_username, s.smtp_password)
                smtp.send_message(msg)
            return True
        except Exception:  # notification failure must never break the main flow
            logger.exception("Failed to send notification to %s", to)
            return False
