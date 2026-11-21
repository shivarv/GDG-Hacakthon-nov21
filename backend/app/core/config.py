from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    @property
    def sender_address(self) -> str:
        """Gmail and most providers reject a From that differs from the login account."""
        if self.smtp_username and self.support_from_address.endswith("@helpdesk.local"):
            return self.smtp_username
        return self.support_from_address

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
