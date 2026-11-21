"""Data loading, cleaning and the leakage-safe 80/20 split."""
from __future__ import annotations

import pandas as pd

from .config import SETTINGS, Settings

TARGETS = ["type", "queue", "priority"]
META_COLS = ["ticket_id", "subject", "body", "answer", "type", "queue", "priority", "language"]


def build_text(subject, body) -> str:
    """Combine subject and body. Null/NaN/empty subjects are handled safely."""
    def _s(x) -> str:
        if x is None:
            return ""
        try:
            if pd.isna(x):
                return ""
        except (TypeError, ValueError):
            pass
        return str(x).strip()

    s, b = _s(subject), _s(body)
    return f"{s}\n{b}" if s and b else (s or b)


def load_raw(settings: Settings = SETTINGS) -> pd.DataFrame:
    if settings.dataset_csv:
        return pd.read_csv(settings.dataset_csv)
    from datasets import load_dataset  # heavy import, only when needed

    ds = load_dataset(settings.dataset)
    return ds["train"].to_pandas()


def clean(df: pd.DataFrame, settings: Settings = SETTINGS) -> pd.DataFrame:
    df = df.copy()
    for col in ["subject", "body", "answer"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)
    for col in TARGETS:
        df[col] = df[col].astype(str).str.strip()
    df["priority"] = df["priority"].str.lower()
    if "language" in df.columns:
        df["language"] = df["language"].astype(str).str.lower().str.strip()
        if settings.languages:
            df = df[df["language"].isin(settings.languages)]
    else:
        df["language"] = ""
    df["text"] = [build_text(s, b) for s, b in zip(df["subject"], df["body"])]
    bad = df["text"].str.len().eq(0) | df[TARGETS].isin(["", "nan", "None"]).any(axis=1)
    return df[~bad].reset_index(drop=True)


def split(df: pd.DataFrame, settings: Settings = SETTINGS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Exactly the split from the brief: shuffle(seed=42) -> ticket ids -> 80/20."""
    df = df.sample(frac=1.0, random_state=settings.seed).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    idx = int(len(df) * settings.kb_fraction)
    return df.iloc[:idx].copy(), df.iloc[idx:].copy()
