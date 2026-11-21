import imaplib
import logging
import threading

from app.core.config import Settings
from app.core.database import SessionLocal
from app.services.email_ingestion_service import EmailIngestionService
from app.services.email_parser import parse_raw_email

logger = logging.getLogger(__name__)


class ImapEmailListener:
    """Background thread that polls an IMAP mailbox for UNSEEN messages and
    hands each one to the EmailIngestionService."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="imap-listener", daemon=True)
        self._thread.start()
        logger.info(
            "IMAP listener started for %s@%s:%s",
            self.settings.imap_username,
            self.settings.imap_host,
            self.settings.imap_port,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception("IMAP poll failed; retrying in %ss", self.settings.imap_poll_interval_seconds)
            self._stop.wait(self.settings.imap_poll_interval_seconds)

    def poll_once(self) -> int:
        s = self.settings
        client_cls = imaplib.IMAP4_SSL if s.imap_use_ssl else imaplib.IMAP4
        processed = 0
        with client_cls(s.imap_host, s.imap_port) as imap:
            imap.login(s.imap_username, s.imap_password)
            imap.select(s.imap_mailbox)
            _, data = imap.search(None, "UNSEEN")
            for num in data[0].split():
                _, msg_data = imap.fetch(num, "(RFC822)")
                raw = next((part[1] for part in msg_data if isinstance(part, tuple)), None)
                if raw:
                    self._process(raw)
                    processed += 1
                imap.store(num, "+FLAGS", "\\Seen")
            imap.logout()
        if processed:
            logger.info("Processed %d new email(s)", processed)
        return processed

    def _process(self, raw: bytes) -> None:
        db = SessionLocal()
        try:
            inbound = parse_raw_email(raw)
            result = EmailIngestionService(db).ingest(inbound)
            logger.info("Email %s -> %s (%s)", inbound.message_id, result.ticket_number, result.action.value)
        except Exception:
            logger.exception("Could not process email")
        finally:
            db.close()
