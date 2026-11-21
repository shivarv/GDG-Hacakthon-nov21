"""Environment-driven settings. Copy .env.example to .env to override."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    artifacts_dir: Path = field(default_factory=lambda: Path(_env("ARTIFACTS_DIR", "artifacts")))
    dataset: str = field(default_factory=lambda: _env("DATASET", "Tobi-Bueck/customer-support-tickets"))
    dataset_csv: str = field(default_factory=lambda: _env("DATASET_CSV", ""))
    languages: tuple = field(default_factory=lambda: tuple(_env("LANGUAGES", "en,de").split(",")))
    seed: int = 42
    kb_fraction: float = 0.8

    embed_model: str = field(default_factory=lambda: _env("EMBED_MODEL", "intfloat/multilingual-e5-small"))
    top_k: int = field(default_factory=lambda: int(_env("TOP_K", "5")))

    conf_threshold: float = field(default_factory=lambda: float(_env("CONF_THRESHOLD", "0.45")))
    sim_threshold: float = field(default_factory=lambda: float(_env("SIM_THRESHOLD", "0.82")))

    burst_sim: float = field(default_factory=lambda: float(_env("BURST_SIM", "0.88")))
    burst_min: int = field(default_factory=lambda: int(_env("BURST_MIN", "3")))
    burst_window_min: float = field(default_factory=lambda: float(_env("BURST_WINDOW_MIN", "15")))

    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "none").lower())
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "claude-sonnet-5-5"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", ""))
    min_other_lang: int = field(default_factory=lambda: int(_env("MIN_OTHER_LANG", "1")))
    demo_mode: bool = field(default_factory=lambda: _env("DEMO_MODE", "0") == "1")
    llm_timeout_s: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT_S", "30")))


SETTINGS = Settings()
