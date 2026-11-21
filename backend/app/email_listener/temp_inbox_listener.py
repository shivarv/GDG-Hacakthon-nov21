import json
import logging
import secrets
import threading
from pathlib import Path

from app.core.config import Settings
from app.core.database import SessionLocal
from app.email_listener.inbox_registry import set_inbox_address
from app.email_listener.mailtm_client import MailTmClient, MailTmError
from app.services.email_ingestion_service import EmailIngestionService
from app.services.email_parser import parse_raw_email

logger = logging.getLogger(__name__)


class TempInboxListener:
    """Receives real internet email with no domain or public server.

    On first start it creates a mail.tm address and saves the credentials to
    disk so the address stays the same across restarts. It then polls the
    inbox, turns each message into a case, and deletes it from mail.tm.
    Receive-only: nothing is ever sent.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = MailTmClient()
        self.address: str | None = None
        self._password: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="temp-inbox", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.address:
                    self._setup_account()
                self.poll_once()
            except MailTmError as exc:
                if str(exc) == "unauthorized":
                    self._login()
                elif "429" in str(exc):
                    logger.info("mail.tm rate limit hit; pausing 30s")
                    self._stop.wait(30)
                else:
                    logger.warning("Temp inbox error: %s", exc)
            except Exception:
                logger.exception("Temp inbox poll failed")
            self._stop.wait(self.settings.temp_inbox_poll_interval_seconds)

    def _setup_account(self) -> None:
        path = Path(self.settings.temp_inbox_state_file)
        if self.settings.temp_inbox_address and self.settings.temp_inbox_password:
            # Hosted: credentials come from the environment, so the address survives redeploys.
            self.address, self._password = self.settings.temp_inbox_address, self.settings.temp_inbox_password
            self._login()
        elif path.exists():
            saved = json.loads(path.read_text())
            self.address, self._password = saved["address"], saved["password"]
            try:
                self._login()
            except MailTmError:
                logger.warning("Saved temp inbox %s is gone; creating a new one", self.address)
                self.address = None
        if not self.address:
            domain = self.client.get_domain()
            address = f"helpdesk-{secrets.token_hex(4)}@{domain}"
            password = secrets.token_urlsafe(16)
            self.client.create_account(address, password)
            self.address, self._password = address, password
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"address": address, "password": password}))
            self._login()
        set_inbox_address(self.address)
        logger.info("=" * 60)
        logger.info("Temp support inbox ready: send email to  %s", self.address)
        logger.info("=" * 60)

    def _login(self) -> None:
        assert self.address and self._password
        self.client.token = None
        self.client.login(self.address, self._password)

    def poll_once(self) -> int:
        processed = 0
        for msg in self.client.list_messages():
            raw = self.client.get_raw_source(msg["id"])
            db = SessionLocal()
            try:
                inbound = parse_raw_email(raw)
                result = EmailIngestionService(db).ingest(inbound)
                logger.info("Temp inbox email from %s -> %s (%s)",
                            inbound.from_address, result.ticket_number, result.action.value)
            finally:
                db.close()
            self.client.delete_message(msg["id"])
            processed += 1
        return processed
