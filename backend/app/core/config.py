from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # backend/.env, wherever the process is started from. Real env vars still take precedence.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "HelpDesk Ticketing API"
    database_url: str = "postgresql+psycopg://helpdesk:helpdesk@localhost:5432/helpdesk"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Ticket number prefix, e.g. TCK-42. Used to thread email replies onto cases.
    ticket_prefix: str = "TCK"

    # IMAP listener
    email_listener_enabled: bool = False
    imap_host: str = "localhost"
    imap_port: int = 3143
    imap_use_ssl: bool = False
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_poll_interval_seconds: int = 10

    # Temporary public inbox via mail.tm (receive real email with no domain/server)
    temp_inbox_enabled: bool = False
    temp_inbox_poll_interval_seconds: int = 10
    temp_inbox_state_file: str = ".data/temp_inbox.json"

    # SMTP (acknowledgement emails)
    smtp_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 3025
    smtp_use_tls: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    support_from_address: str = "support@helpdesk.local"
    support_from_name: str = "HelpDesk Support"

    # Triage of new email tickets: escalate severe ones automatically
    auto_escalate: bool = True
    triage_model: str = "dummy"

    # Resolution-time model used for escalation due dates ("dummy" until a trained one is merged)
    eta_model: str = "dummy"
    # Timezone used when showing due times to customers
    support_timezone: str = "America/New_York"

    # Gmail API for sending (send-only token from scripts/gmail_auth.py).
    gmail_api_enabled: bool = False
    gmail_credentials_file: str = ".data/gmail_credentials.json"
    gmail_token_file: str = ".data/gmail_token.json"

    # Brevo transactional API. When set, it's used instead of SMTP.
    # Takes an API key (xkeysib-...), not an SMTP key.
    brevo_api_key: str = ""
    brevo_api_url: str = "https://api.brevo.com/v3/smtp/email"

    @property
    def smtp_missing_credentials(self) -> bool:
        """Remote relays (Brevo, Gmail) need a login; local test servers (GreenMail) don't."""
        local = self.smtp_host in {"localhost", "127.0.0.1", "mail"}
        return not local and not (self.smtp_username and self.smtp_password)

    @property
    def smtp_ready(self) -> bool:
        return self.smtp_enabled and not self.smtp_missing_credentials

    @property
    def email_transport(self) -> str | None:
        """'gmail_api', 'brevo_api', 'smtp', or None when outgoing email can't be sent."""
        if self.gmail_api_enabled:
            return "gmail_api" if Path(self.gmail_token_file).exists() else None
        if self.brevo_api_key:
            return "brevo_api" if not self.support_from_address.endswith("@helpdesk.local") else None
        return "smtp" if self.smtp_ready else None

    @property
    def sender_address(self) -> str:
        """Gmail rejects a From that differs from the login account, so default to it there.
        Relays like Brevo use a non-address login, so SUPPORT_FROM_ADDRESS must be set
        to a verified sender instead."""
        if "gmail" in self.smtp_host and self.smtp_username and self.support_from_address.endswith("@helpdesk.local"):
            return self.smtp_username
        return self.support_from_address

    @field_validator("database_url")
    @classmethod
    def _anchor_sqlite_path(cls, v: str) -> str:
        """Resolve relative SQLite paths against backend/, not the current directory."""
        prefix = "sqlite:///"
        if v.startswith(prefix) and not v.startswith(prefix + "/"):
            path = (BACKEND_DIR / v[len(prefix):]).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{path}"
        return v

    @field_validator("temp_inbox_state_file", "gmail_credentials_file", "gmail_token_file")
    @classmethod
    def _anchor_state_file(cls, v: str) -> str:
        return str(v if Path(v).is_absolute() else BACKEND_DIR / v)

    @field_validator("support_from_address", mode="before")
    @classmethod
    def _blank_from_means_default(cls, v: str) -> str:
        return v or "support@helpdesk.local"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
