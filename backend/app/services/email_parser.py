"""Pure helpers for turning raw RFC 822 messages into InboundEmail objects."""

import re
import uuid
from email import policy
from email.message import EmailMessage as StdEmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from html import unescape

from app.core.config import get_settings
from app.models import TicketPriority
from app.schemas.email import InboundEmail

_REPLY_MARKERS = [
    re.compile(r"^On .+wrote:\s*$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^From:\s.+", re.IGNORECASE),
    re.compile(r"^_{5,}"),
]
_SUBJECT_PREFIX = re.compile(r"^\s*((re|fw|fwd|aw)\s*:\s*)+", re.IGNORECASE)
_URGENT_WORDS = ("urgent", "asap", "emergency", "critical", "outage", "down")
_HIGH_WORDS = ("important", "high priority", "blocked", "cannot", "can't", "unable")


def parse_raw_email(raw: bytes) -> InboundEmail:
    msg: StdEmailMessage = BytesParser(policy=policy.default).parsebytes(raw)  # type: ignore[assignment]
    from_name, from_address = parseaddr(str(msg.get("From", "")))
    return InboundEmail(
        from_address=from_address,
        from_name=from_name or None,
        to_address=str(msg.get("To", "")) or None,
        subject=str(msg.get("Subject", "")).strip(),
        body_text=_extract_body(msg),
        message_id=_clean_id(msg.get("Message-ID")),
        in_reply_to=_clean_id(msg.get("In-Reply-To")),
    )


def _extract_body(msg: StdEmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_type() == "text/html":
        content = _html_to_text(content)
    return content.strip()


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", "", html))


def _clean_id(value) -> str | None:
    if not value:
        return None
    return str(value).strip().strip("<>") or None


def generate_message_id() -> str:
    return f"{uuid.uuid4()}@helpdesk.local"


def strip_quoted_reply(body: str) -> str:
    """Keep only the new text a customer typed above the quoted thread."""
    kept: list[str] = []
    for line in body.splitlines():
        if line.lstrip().startswith(">") or any(p.match(line.strip()) for p in _REPLY_MARKERS):
            break
        kept.append(line)
    text = "\n".join(kept).strip()
    return text or body.strip()


def clean_subject(subject: str) -> str:
    """Remove Re:/Fwd: prefixes and any [TCK-123] tag."""
    subject = _SUBJECT_PREFIX.sub("", subject)
    subject = _ticket_tag_pattern().sub("", subject)
    return subject.strip() or "(no subject)"


def extract_ticket_id(subject: str) -> int | None:
    match = _ticket_tag_pattern().search(subject)
    return int(match.group(1)) if match else None


def detect_priority(subject: str, body: str) -> TicketPriority:
    text = f"{subject} {body}".lower()
    if any(w in text for w in _URGENT_WORDS):
        return TicketPriority.URGENT
    if any(w in text for w in _HIGH_WORDS):
        return TicketPriority.HIGH
    return TicketPriority.MEDIUM


def _ticket_tag_pattern() -> re.Pattern[str]:
    prefix = re.escape(get_settings().ticket_prefix)
    return re.compile(rf"\[\s*{prefix}-(\d+)\s*\]", re.IGNORECASE)
