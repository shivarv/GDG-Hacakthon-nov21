from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dao.outbound_email_dao import OutboundEmailDAO
from app.email_listener.inbox_registry import get_inbox_address
from app.models import (
    Escalation,
    OutboundEmail,
    OutboundEmailKind,
    OutboundEmailStatus,
    Ticket,
    User,
)
from app.models.enums import UserRole

logger = logging.getLogger(__name__)

ROLE_LABELS = {
    UserRole.AGENT: "Support Agent",
    UserRole.TEAM_LEAD: "Team Lead",
    UserRole.MANAGER: "Manager",
    UserRole.ON_CALL: "On-call Engineer",
    UserRole.SECURITY: "Security Officer",
}


class NotificationService:
    """Builds and sends every outbound email.

    - Sends through the configured SMTP server (e.g. Gmail with an App Password).
    - Subjects carry the [TCK-n] tag and Reply-To points at the inbox the system
      reads, so customer replies thread back onto the ticket.
    - When a DB session is given, every attempt is logged to `outbound_emails`.
    """

    def __init__(self, db: Session | None = None):
        self.settings = get_settings()
        self.log = OutboundEmailDAO(db) if db is not None else None

    # ---- public API ------------------------------------------------------

    def send_ticket_created(self, ticket: Ticket) -> OutboundEmail | None:
        body = (
            f"Hi {self._first_name(ticket.requester_name) or 'there'},\n\n"
            f"Thanks for contacting support. We've opened case {ticket.ticket_number} "
            f"for your request and will get back to you shortly.\n\n"
            f"Reply to this email to add more information to your case.\n\n"
            f"— {self.settings.support_from_name}"
        )
        return self._send(ticket.requester_email, f"[{ticket.ticket_number}] {ticket.subject}", body,
                          OutboundEmailKind.ACKNOWLEDGEMENT, ticket)

    def send_escalation(self, ticket: Ticket, contact: User, escalation: Escalation) -> bool:
        body = (
            f"Hi {self._first_name(contact.name)},\n\n"
            f"Case {ticket.ticket_number} has been escalated to you (level L{escalation.level}).\n\n"
            f"Subject:   {ticket.subject}\n"
            f"Priority:  {ticket.priority.value}\n"
            f"Requester: {ticket.requester_name or ''} <{ticket.requester_email}>\n"
            f"Escalated by: {escalation.escalated_by}\n\n"
            f"Reason:\n{escalation.reason}\n\n"
            f"— {self.settings.support_from_name}"
        )
        subject = f"[Escalation L{escalation.level}] [{ticket.ticket_number}] {ticket.subject}"
        record = self._send(contact.email, subject, body, OutboundEmailKind.ESCALATION_INTERNAL, ticket)
        return record is not None and record.status == OutboundEmailStatus.SENT

    def customer_handoff_message(self, ticket: Ticket, contact: User) -> tuple[str, str]:
        """Subject and body telling the customer who now owns their ticket."""
        first = self._first_name(contact.name)
        lines = [
            f"Hi {self._first_name(ticket.requester_name) or 'there'},",
            "",
            f'Your request "{ticket.subject}" (case {ticket.ticket_number}) has been escalated '
            f"to a senior member of our team for priority handling.",
            "",
            "Your dedicated contact:",
            f"  {contact.name} — {ROLE_LABELS.get(contact.role, 'Support')}, {contact.team}",
            f"  Email: {contact.email}",
        ]
        if contact.phone:
            lines.append(f"  Phone: {contact.phone}")
        lines += [
            "",
            f"{first} is now looking at your ticket. You can reach {first} directly by email"
            + (" or phone" if contact.phone else "")
            + f', or simply reply to this email — please keep "[{ticket.ticket_number}]" in the subject '
            "so your message is added to your case.",
            "",
            "Kind regards,",
            self.settings.support_from_name,
        ]
        subject = f"[{ticket.ticket_number}] Your request is now being handled by {contact.name}"
        return subject, "\n".join(lines)

    def send_customer_handoff(self, ticket: Ticket, contact: User) -> OutboundEmail | None:
        subject, body = self.customer_handoff_message(ticket, contact)
        return self._send(ticket.requester_email, subject, body, OutboundEmailKind.CUSTOMER_HANDOFF, ticket)

    def send_test(self, to: str) -> OutboundEmail | None:
        body = (
            "This is a test email from your HelpDesk support console.\n\n"
            "If you can read this, outbound email is configured correctly.\n\n"
            f"— {self.settings.support_from_name}"
        )
        return self._send(to, "HelpDesk test email", body, OutboundEmailKind.TEST, None)

    def status(self) -> dict:
        s = self.settings
        return {
            "enabled": s.smtp_enabled,
            "host": s.smtp_host if s.smtp_enabled else None,
            "from_address": s.sender_address,
            "reply_to": self._reply_to(),
        }

    # ---- internals -------------------------------------------------------

    def _reply_to(self) -> str:
        return get_inbox_address() or self.settings.sender_address

    @staticmethod
    def _first_name(name: str | None) -> str:
        return name.split()[0] if name and name.strip() else ""

    def _send(self, to: str, subject: str, body: str, kind: OutboundEmailKind, ticket: Ticket | None) -> OutboundEmail | None:
        s = self.settings
        sender = s.sender_address
        reply_to = self._reply_to()
        status, error = OutboundEmailStatus.SKIPPED, "SMTP is disabled (set SMTP_ENABLED=true)"

        if s.smtp_enabled:
            msg = EmailMessage()
            msg["From"] = formataddr((s.support_from_name, sender))
            msg["To"] = to
            msg["Subject"] = subject
            msg["Reply-To"] = reply_to
            msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
            msg.set_content(body)
            try:
                with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                    if s.smtp_use_tls:
                        smtp.starttls()
                    if s.smtp_username:
                        smtp.login(s.smtp_username, s.smtp_password)
                    smtp.send_message(msg)
                status, error = OutboundEmailStatus.SENT, None
                logger.info("Email sent (%s) -> %s: %s", kind.value, to, subject)
            except Exception as exc:  # delivery failure must never break the main flow
                status, error = OutboundEmailStatus.FAILED, f"{type(exc).__name__}: {exc}"
                logger.warning("Email to %s failed: %s", to, error)
        else:
            logger.info("Email skipped (SMTP off) (%s) -> %s: %s", kind.value, to, subject)

        if self.log is None:
            return None
        record = self.log.add(
            OutboundEmail(
                ticket_id=ticket.id if ticket else None,
                kind=kind,
                to_address=to,
                from_address=sender,
                reply_to=reply_to,
                subject=subject,
                body=body,
                status=status,
                error=error,
            )
        )
        self.log.db.commit()
        return record
