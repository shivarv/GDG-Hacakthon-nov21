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
    FAILED = "failed"
