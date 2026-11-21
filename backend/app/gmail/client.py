"""Send email through the Gmail API with a stored OAuth token (send-only permission).

The token is created once by `python scripts/gmail_auth.py` (browser sign-in) and
refreshed automatically afterwards. Incoming mail is not read through Gmail: the
Gmail account forwards it to the helpdesk inbox the app already reads.
"""

from __future__ import annotations

import base64
import threading
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]  # send only, no access to the mailbox
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailNotConnected(Exception):
    pass


class GmailClient:
    def __init__(self, token_file: str):
        self.token_file = Path(token_file)
        self._lock = threading.Lock()
        self._session: AuthorizedSession | None = None

    def _get_session(self) -> AuthorizedSession:
        with self._lock:
            if self._session is None:
                if not self.token_file.exists():
                    raise GmailNotConnected("Gmail isn't connected yet: run python scripts/gmail_auth.py")
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
                if not creds.valid and creds.refresh_token:
                    creds.refresh(Request())
                    self.token_file.write_text(creds.to_json())
                self._session = AuthorizedSession(creds)
            return self._session

    def send(self, message: EmailMessage) -> str:
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        resp = self._get_session().post(SEND_URL, json={"raw": raw}, timeout=20)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error", {}).get("message", resp.text)
            except ValueError:
                detail = resp.text
            raise RuntimeError(f"Gmail API {resp.status_code}: {detail}")
        return resp.json()["id"]


_client: GmailClient | None = None


def get_gmail_client(token_file: str) -> GmailClient:
    """One shared client per process (token refresh is thread-safe)."""
    global _client
    if _client is None or str(_client.token_file) != str(Path(token_file)):
        _client = GmailClient(token_file)
    return _client
