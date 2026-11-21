"""English/German detection: langdetect first, stop-word heuristic as fallback."""
from __future__ import annotations

import re

_DE = set("""ich wir sie nicht und der die das ist bitte mit für auf ein eine einen dem den des
von zu haben wird werden kann können unser unsere ihr ihre hallo sehr geehrte grüße danke
problem seit funktioniert keine kein auch noch wenn aber oder uns""".split())
_EN = set("""i we you not and the is are please with for on a an of to have will can our your
hello dear regards thanks since works no also still when but or us this that it""".split())

try:
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0
except ImportError:  # optional dependency
    detect = None


def _heuristic(text: str) -> str:
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in _DE for w in words) + 2 * sum(ch in "äöüß" for ch in text.lower())
    en = sum(w in _EN for w in words)
    return "de" if de > en else "en"


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "en"
    if detect is not None:
        try:
            code = detect(text)
            if code in ("en", "de"):
                return code
        except Exception:
            pass
    return _heuristic(text)
