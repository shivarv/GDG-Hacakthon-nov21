from __future__ import annotations

import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dao.outbound_email_dao import OutboundEmailDAO
from app.email_listener.inbox_registry import get_inbox_address
from app.gmail.client import get_gmail_client
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
# Brevo sits behind Cloudflare, which rejects Python's default "Python-urllib" User-Agent with 403.
USER_AGENT = "HelpDesk/1.0"
# Marks our emails so they're ignored if they loop back in, and tells other systems not to auto-reply.
LOOP_HEADERS = {"X-HelpDesk-Generated": "true", "Auto-Submitted": "auto-generated"}

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

    def customer_handoff_message(self, ticket: Ticket, contact: User, level: int, eta) -> tuple[str, str]:
        """The escalation notice sent to the customer: who owns the ticket now and when to expect progress."""
        first = self._first_name(contact.name)
        role = f"{ROLE_LABELS.get(contact.role, 'Support')}, {contact.team}"
        lines = [
            f"Hi {self._first_name(ticket.requester_name) or 'there'},",
            "",
            "Thank you for your patience. We've escalated your request to our senior support team "
            "so it gets the priority attention it needs.",
            "",
            f"  Ticket:    {ticket.ticket_number} – {ticket.subject}",
            f"  Priority:  {ticket.priority.value.capitalize()}",
            f"  Status:    Escalated (Level {level})",
            "",
            "Your assigned specialist",
            f"  {contact.name} — {role}",
            f"  Email: {contact.email}",
        ]
        if contact.phone:
            lines.append(f"  Phone: {contact.phone}")
        lines += [
            "",
            "What to expect",
            f"  • First response by:      {self._fmt_time(eta.first_response_due_at)}",
            f"  • Target resolution by:   {self._fmt_time(eta.resolution_due_at)}",
            "",
            f"{first} is now reviewing your ticket and will keep you updated on progress. "
            f"If you have more details to share, simply reply to this email (please keep "
            f'"[{ticket.ticket_number}]" in the subject) or contact {first} directly.',
            "",
            "Kind regards,",
            self.settings.support_from_name,
            "",
            "Times are estimates and may change as we learn more about the issue.",
        ]
        subject = f"[{ticket.ticket_number}] Your ticket has been escalated – {contact.name} is on it"
        return subject, "\n".join(lines)

    def _fmt_time(self, when) -> str:
        from datetime import timezone
        from zoneinfo import ZoneInfo

        if when.tzinfo is None:  # SQLite returns naive UTC timestamps
            when = when.replace(tzinfo=timezone.utc)
        local = when.astimezone(ZoneInfo(self.settings.support_timezone))
        return local.strftime("%a, %d %b %Y, %-I:%M %p %Z")

    def send_customer_handoff(self, ticket: Ticket, contact: User, level: int, eta) -> OutboundEmail | None:
        subject, body = self.customer_handoff_message(ticket, contact, level, eta)
        return self._send(ticket.requester_email, subject, body, OutboundEmailKind.CUSTOMER_HANDOFF, ticket)

    def send_agent_reply(self, ticket: Ticket, author: str, body: str) -> OutboundEmail | None:
        """Email an agent's public reply to the requester, threaded on the ticket."""
        signature = f"\n\n— {author}\n{self.settings.support_from_name}" if author else f"\n\n— {self.settings.support_from_name}"
        footer = f'\n\nTo respond, just reply to this email (keep "[{ticket.ticket_number}]" in the subject).'
        subject = f"Re: [{ticket.ticket_number}] {ticket.subject}"
        return self._send(ticket.requester_email, subject, body.strip() + signature + footer,
                          OutboundEmailKind.AGENT_REPLY, ticket)

    def send_test(self, to: str) -> OutboundEmail | None:
        body = (
            "This is a test email from your HelpDesk support console.\n\n"
            "If you can read this, outbound email is configured correctly.\n\n"
            f"— {self.settings.support_from_name}"
        )
        return self._send(to, "HelpDesk test email", body, OutboundEmailKind.TEST, None)

    def status(self) -> dict:
        s = self.settings
        transport = s.email_transport
        host = {"gmail_api": "Gmail API", "brevo_api": "Brevo API (api.brevo.com)", "smtp": s.smtp_host}.get(transport or "")
        return {
            "enabled": transport is not None,
            "host": host,
            "from_address": self._sender(),
            "reply_to": self._reply_to(),
            "problem": self._not_ready_reason(),
        }

    def _not_ready_reason(self) -> str | None:
        s = self.settings
        if s.email_transport:
            return None
        if s.gmail_api_enabled:
            return "Gmail isn't connected yet: run python scripts/gmail_auth.py in the backend folder"
        if s.brevo_api_key:
            return "Set SUPPORT_FROM_ADDRESS in backend/.env to a sender verified in your Brevo account"
        if not s.smtp_enabled:
            return "Outgoing email is off: set BREVO_API_KEY (or the SMTP settings) in backend/.env"
        if s.smtp_missing_credentials:
            return "Credentials missing: set BREVO_API_KEY, or SMTP_USERNAME and SMTP_PASSWORD, in backend/.env"
        return None

    # ---- internals -------------------------------------------------------

    def _sender(self) -> str:
        return self.settings.sender_address

    def _reply_to(self) -> str:
        return get_inbox_address() or self._sender()

    @staticmethod
    def _first_name(name: str | None) -> str:
        return name.split()[0] if name and name.strip() else ""

    def _send(self, to: str, subject: str, body: str, kind: OutboundEmailKind, ticket: Ticket | None) -> OutboundEmail | None:
        s = self.settings
        sender = self._sender()
        reply_to = self._reply_to()
        status, error = OutboundEmailStatus.SKIPPED, self._not_ready_reason()
        transport = s.email_transport
        if to.lower().endswith(".local"):
            # Dummy contacts (@helpdesk.local) can't receive mail; sending would only produce a bounce.
            transport, error = None, "Not sent: demo address on a non-routable .local domain"

        if transport == "gmail_api":
            msg = EmailMessage()
            msg["From"] = formataddr((s.support_from_name, sender))
            msg["To"] = to
            msg["Subject"] = subject
            if reply_to != sender:
                msg["Reply-To"] = reply_to
            for name, value in LOOP_HEADERS.items():
                msg[name] = value
            msg.set_content(body)
            try:
                get_gmail_client(s.gmail_token_file).send(msg)
                status, error = OutboundEmailStatus.SENT, None
                logger.info("Email sent via Gmail API (%s) -> %s: %s", kind.value, to, subject)
            except Exception as exc:  # delivery failure must never break the main flow
                status, error = OutboundEmailStatus.FAILED, str(exc)
                logger.warning("Email to %s failed: %s", to, error)
        elif transport == "brevo_api":
            try:
                self._deliver_brevo_api(to, subject, body, sender, reply_to)
                status, error = OutboundEmailStatus.SENT, None
                logger.info("Email sent via Brevo API (%s) -> %s: %s", kind.value, to, subject)
            except Exception as exc:  # delivery failure must never break the main flow
                status, error = OutboundEmailStatus.FAILED, str(exc)
                logger.warning("Email to %s failed: %s", to, error)
        elif transport == "smtp":
            msg = EmailMessage()
            msg["From"] = formataddr((s.support_from_name, sender))
            msg["To"] = to
            msg["Subject"] = subject
            msg["Reply-To"] = reply_to
            msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
            for name, value in LOOP_HEADERS.items():
                msg[name] = value
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
            logger.info("Email skipped (%s) (%s) -> %s: %s", error, kind.value, to, subject)

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

    def _deliver_brevo_api(self, to: str, subject: str, body: str, sender: str, reply_to: str) -> None:
        """POST to Brevo's transactional email API. Raises with Brevo's message on failure."""
        s = self.settings
        payload = {
            "sender": {"name": s.support_from_name, "email": sender},
            "to": [{"email": to}],
            "replyTo": {"email": reply_to},
            "subject": subject,
            "textContent": body,
            "headers": LOOP_HEADERS,
        }
        req = urllib.request.Request(
            s.brevo_api_url,
            data=json.dumps(payload).encode(),
            headers={
                "api-key": s.brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("message", detail)
            except ValueError:
                pass
            hint = {
                401: " (check BREVO_API_KEY; an SMTP key won't work here)",
                429: " (rate limited; try again shortly)",
            }.get(exc.code, " (Brevo is having trouble; try again later)" if exc.code >= 500 else "")
            raise RuntimeError(f"Brevo API {exc.code}: {detail}{hint}") from exc
