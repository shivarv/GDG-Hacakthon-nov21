import enum


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketSource(str, enum.Enum):
    WEB = "web"
    EMAIL = "email"


class EmailProcessingStatus(str, enum.Enum):
    CREATED_TICKET = "created_ticket"
    APPENDED_COMMENT = "appended_comment"
    IGNORED = "ignored"  # our own outgoing email looping back (e.g. via Gmail forwarding)
    FAILED = "failed"


class UserRole(str, enum.Enum):
    AGENT = "agent"
    TEAM_LEAD = "team_lead"
    MANAGER = "manager"
    ON_CALL = "on_call"
    SECURITY = "security"


class EscalationStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class EscalationSource(str, enum.Enum):
    MANUAL = "manual"
    AUTO = "auto"  # reserved for the SentinelDesk escalation gate


class OutboundEmailStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"  # SMTP not configured


class OutboundEmailKind(str, enum.Enum):
    ACKNOWLEDGEMENT = "acknowledgement"
    ESCALATION_INTERNAL = "escalation_internal"  # to the escalation contact
    CUSTOMER_HANDOFF = "customer_handoff"  # tells the customer who is handling the ticket
    AGENT_REPLY = "agent_reply"  # a public reply written by an agent in the app
    TEST = "test"
