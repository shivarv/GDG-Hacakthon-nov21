"""PII guardrail: mask sensitive values before text leaves the process."""
from __future__ import annotations

import re

# Order matters: more specific patterns first.
_PATTERNS = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("IP", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("PHONE", re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")),
    # The number must contain a digit: otherwise "Konto einloggen" or "account settings" would be masked.
    ("ACCOUNT", re.compile(
        r"\b(?:account\s*(?:no\.?|number|#)?|acct|customer\s*id|kontonummer|konto(?:-?nr\.?)?|"
        r"kundennummer|kunden-?nr\.?|vertragsnummer)[\s#:.-]*(?=[A-Z0-9-]*\d)[A-Z0-9-]{5,}\b", re.I)),
]


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    if not text:
        return text, counts
    for label, pat in _PATTERNS:
        text, n = pat.subn(f"<{label}>", text)
        if n:
            counts[label] = counts.get(label, 0) + n
    return text, counts
