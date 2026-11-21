"""Resolution-time estimation for escalated tickets.

`get_eta_model()` returns the configured model (ETA_MODEL in .env). Only a dummy,
rule-based model exists today; a trained model can be added by implementing
`EtaModel.estimate()` and registering it in `_MODELS`.
"""

from app.services.eta.base import EtaModel, ResolutionEstimate
from app.services.eta.dummy import DummyEtaModel

_MODELS: dict[str, type] = {"dummy": DummyEtaModel}


def get_eta_model(name: str = "dummy") -> EtaModel:
    try:
        return _MODELS[name]()
    except KeyError:
        raise ValueError(f"Unknown ETA model {name!r}; available: {', '.join(_MODELS)}") from None


__all__ = ["EtaModel", "ResolutionEstimate", "get_eta_model"]
