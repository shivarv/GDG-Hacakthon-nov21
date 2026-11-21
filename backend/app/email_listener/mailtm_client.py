"""Minimal client for the mail.tm temporary-inbox API (https://docs.mail.tm)."""

import json
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://api.mail.tm"


class MailTmError(Exception):
    pass


def _members(resp: Any) -> list[dict[str, Any]]:
    """Collections come back as a plain list or a hydra-wrapped object."""
    return resp if isinstance(resp, list) else resp.get("hydra:member", [])


class MailTmClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = 15):
        self.base_url = base_url
        self.timeout = timeout
        self.token: str | None = None

    def get_domain(self) -> str:
        domains = _members(self._request("GET", "/domains"))
        active = [d["domain"] for d in domains if d.get("isActive")]
        if not active:
            raise MailTmError("mail.tm has no active domains right now")
        return active[0]

    def create_account(self, address: str, password: str) -> None:
        self._request("POST", "/accounts", {"address": address, "password": password})

    def login(self, address: str, password: str) -> None:
        self.token = self._request("POST", "/token", {"address": address, "password": password})["token"]

    def list_messages(self) -> list[dict[str, Any]]:
        return _members(self._request("GET", "/messages"))

    def get_raw_source(self, message_id: str) -> bytes:
        return self._request("GET", f"/sources/{message_id}")["data"].encode()

    def delete_message(self, message_id: str) -> None:
        self._request("DELETE", f"/messages/{message_id}")

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        headers = {"Accept": "application/json", "User-Agent": "helpdesk-ticketing/0.1"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and self.token:
                raise MailTmError("unauthorized") from exc
            raise MailTmError(f"{method} {path} -> {exc.code}: {exc.read()[:300]!r}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:  # network hiccup: retry next poll
            raise MailTmError(f"{method} {path} -> network error: {exc}") from exc
