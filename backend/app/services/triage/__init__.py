"""Triage for new email tickets: how severe is it, and should it be escalated right away?

`get_triage_model()` returns the configured model (TRIAGE_MODEL in .env). Only a dummy,
keyword-based model exists today; the SentinelDesk classifier can replace it by
implementing `TriageModel.assess()` and registering it in `_MODELS`.
"""

from app.services.triage.base import TriageDecision, TriageModel
from app.services.triage.dummy import DummyTriageModel
from app.services.triage.sentinel import SentinelLocalModel, SentinelRemoteModel

_MODELS: dict[str, type] = {
    "dummy": DummyTriageModel,
    "sentinel_remote": SentinelRemoteModel,
    "sentinel_local": SentinelLocalModel,
}
_instances: dict[str, TriageModel] = {}


def get_triage_model(name: str = "dummy") -> TriageModel:
    """Models are created once per process (the local Sentinel model takes ~40 s to load)."""
    if name not in _MODELS:
        raise ValueError(f"Unknown triage model {name!r}; available: {', '.join(_MODELS)}")
    if name not in _instances:
        _instances[name] = _MODELS[name]()
    return _instances[name]


__all__ = ["TriageDecision", "TriageModel", "get_triage_model"]
