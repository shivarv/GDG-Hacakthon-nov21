"""SentinelDesk triage model (Nathan's `triage/` package), used two ways:

- SentinelRemoteModel: POST {subject, body} to the deployed Cloud Run service (`/triage`).
- SentinelLocalModel:  load the same `triage.joblib` in-process (for local testing).

Both turn the model's JSON contract into a TriageDecision:
  priority  = "urgent" when the urgency rule fires, else the model's priority (high/medium/low)
  escalate  = the model's own tuned gate (`gate_hints.escalate`), with its reasons
  queue     = predicted department, used by auto-assign to pick the escalation team
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from app.core.config import get_settings
from app.models import TicketPriority
from app.services.triage.base import TriageDecision

logger = logging.getLogger(__name__)

_PRIORITY = {"high": TicketPriority.HIGH, "medium": TicketPriority.MEDIUM, "low": TicketPriority.LOW}


def decision_from_contract(result: dict, model_name: str) -> TriageDecision:
    """Map the SentinelDesk JSON contract onto our TriageDecision."""
    urgent = bool(result.get("urgency", {}).get("urgent"))
    priority = TicketPriority.URGENT if urgent else _PRIORITY.get(result["priority"]["label"], TicketPriority.MEDIUM)
    gate = result.get("gate_hints", {})
    reasons = [
        f"Model: {result['type']['label']} · {result['queue']['label']} ({result['queue']['conf']:.2f}) · "
        f"{result['priority']['label']} priority ({result['priority']['conf']:.2f})"
    ] + list(gate.get("reasons", []))
    if not gate.get("escalate"):
        reasons.append("Model gate: no escalation needed")
    return TriageDecision(
        priority=priority,
        should_escalate=bool(gate.get("escalate")),
        confidence=float(result["priority"]["conf"]),
        model=model_name,
        reasons=reasons,
        ticket_type=result["type"]["label"],
        queue=result["queue"]["label"],
        queue_confidence=float(result["queue"]["conf"]),
    )


class SentinelRemoteModel:
    name = "sentinel-remote"

    def __init__(self):
        self.url = get_settings().sentinel_triage_url.rstrip("/")
        if not self.url:
            raise ValueError("TRIAGE_MODEL=sentinel_remote needs SENTINEL_TRIAGE_URL in backend/.env")

    def assess(self, subject: str, body: str) -> TriageDecision:
        req = urllib.request.Request(
            f"{self.url}/triage",
            data=json.dumps({"subject": subject, "body": body}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "HelpDesk/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return decision_from_contract(json.load(resp), self.name)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Sentinel triage service {exc.code}: {exc.read()[:200]!r}") from exc

    def health(self) -> dict:
        with urllib.request.urlopen(f"{self.url}/health", timeout=10) as resp:
            return json.load(resp)


class SentinelLocalModel:
    name = "sentinel-local"
    _lock = threading.Lock()
    _model = None

    def __init__(self):
        self.path = Path(get_settings().sentinel_model_path)

    def _load(self):
        with self._lock:
            if SentinelLocalModel._model is None:
                repo_root = self.path.resolve().parents[2]  # .../triage/models/triage.joblib -> repo root
                if str(repo_root) not in sys.path:
                    sys.path.insert(0, str(repo_root))
                from triage.model import TriageModel  # Nathan's package, unchanged

                logger.info("Loading SentinelDesk triage model from %s (takes ~40 s)...", self.path)
                SentinelLocalModel._model = TriageModel.load(str(self.path))
                logger.info("SentinelDesk triage model loaded")
            return SentinelLocalModel._model

    def warm_up(self) -> None:
        self._load()

    def assess(self, subject: str, body: str) -> TriageDecision:
        return decision_from_contract(self._load().predict(subject, body), self.name)
