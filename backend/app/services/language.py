"""Tiny English/German detector for customer-facing emails (no extra dependency)."""

import re

_DE_WORDS = frozenset(
    """ich wir sie nicht und der die das ist bitte mit für auf ein eine einen dem den des von zu
    haben wird werden kann können unser unsere ihr ihre hallo sehr geehrte grüße danke seit
    funktioniert keine kein auch noch wenn aber oder uns mein meine mich mir dringend""".split()
)
_EN_WORDS = frozenset(
    """i we you not and the is are please with for on a an of to have will can our your hello
    dear regards thanks since works no also still when but or us this that it my me""".split()
)


def detect_language(*texts: str | None) -> str:
    """Return "de" or "en". Umlauts and German stop words outvote English ones."""
    text = " ".join(t for t in texts if t).lower()
    words = re.findall(r"[a-zäöüß]+", text)
    de = sum(w in _DE_WORDS for w in words) + 2 * sum(ch in "äöüß" for ch in text)
    en = sum(w in _EN_WORDS for w in words)
    return "de" if de > en else "en"
