"""Triage for new email tickets: how severe is it, and should it be escalated right away?

`get_triage_model()` returns the configured model (TRIAGE_MODEL in .env). Only a dummy,
keyword-based model exists today; the SentinelDesk classifier can replace it by
implementing `TriageModel.assess()` and registering it in `_MODELS`.
"""

from app.services.triage.base import TriageDecision, TriageModel
from app.services.triage.dummy import DummyTriageModel

_MODELS: dict[str, type] = {"dummy": DummyTriageModel}


def get_triage_model(name: str = "dummy") -> TriageModel:
    try:
        return _MODELS[name]()
    except KeyError:
        raise ValueError(f"Unknown triage model {name!r}; available: {', '.join(_MODELS)}") from None


__all__ = ["TriageDecision", "TriageModel", "get_triage_model"]
