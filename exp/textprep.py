"""Text normalization shared by training and live inference.

Mirrors dataset/split.py clean_text/build_text so live tickets look like the training data
(literal "\\n" and <br> -> newline, name placeholders -> <name>, whitespace collapsed).
Kept dependency-free (stdlib only) so the serving container stays small.
"""
import re
import unicodedata

_LIT_NL = re.compile(r"\\r\\n|\\n|\\r")
_BR = re.compile(r"<br\s*/?>", re.I)
_NAME = re.compile(r"\[\s*(?:your|ihr|ihre|dein|deine)?\s*name\s*\]", re.I)
_SPACES = re.compile(r"[ \t ]+")
_NL_SPACES = re.compile(r" *\n *")
_MANY_NL = re.compile(r"\n{3,}")


def clean_text(s) -> str:
    if s is None or (isinstance(s, float) and s != s):  # None / NaN
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = _LIT_NL.sub("\n", s)
    s = _BR.sub("\n", s)
    s = _NAME.sub("<name>", s)
    s = _SPACES.sub(" ", s)
    s = _NL_SPACES.sub("\n", s)
    s = _MANY_NL.sub("\n\n", s)
    return s.strip()


def build_text(subject, body) -> str:
    """subject (optional) + body -> one model input. Never fails on a missing subject."""
    return (clean_text(subject) + "\n\n" + clean_text(body)).strip()
