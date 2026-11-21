"""Explicit, explainable urgency rules (EN + DE) for the escalation gate.

Why: the dataset's priority labels follow ticket "families", not urgency wording, so the classifiers can
miss an obvious outage (e.g. the brief's hospital-VPN example). These rules make sure that obvious
emergencies always escalate, and every hit says which words triggered it.

  urgent = (outage AND (wide scope OR urgency words OR critical impact))
           OR security incident
           OR (urgency words AND critical impact)
  Negated urgency ("not urgent", "nicht dringend", "no rush", "keine Eile") cancels urgency words.
"""
import re

_F = re.I | re.U

PATTERNS = {
    "outage": [
        r"\boutage\b", r"\b(?:is|are|went|goes|been)\s+down\b", r"\bdown\s+(?:since|for|again)\b",
        r"\bnot\s+(?:working|responding|reachable|accessible|loading|available)\b",
        r"\b(?:unreachable|unavailable|inaccessible|offline)\b", r"\bcrash(?:ed|es|ing)?\b",
        r"\b(?:cannot|can't|can not|unable to)\s+(?:connect|log\s?in|login|access|reach|open|sign\s?in)\b",
        r"\bno\s+(?:access|connection|connectivity)\b", r"\b(?:failing|failed|failure)\b", r"\bstopped\s+working\b",
        r"\bausfall\b", r"\bausgefallen\b", r"\bst[öo]rung\b", r"\bgest[öo]rt\b", r"\bf[äa]llt\s+aus\b",
        r"\bnicht\s+(?:erreichbar|verf[üu]gbar|zug[äa]nglich)\b", r"\bfunktioniert\s+nicht(?:\s+mehr)?\b",
        r"\babgest[üu]rzt\b", r"\bkein(?:e|en)?\s+(?:zugriff|verbindung)\b", r"\bgeht\s+nicht\s+mehr\b",
    ],
    "scope": [
        r"\ball\s+(?:users|clinicians|staff|employees|customers|sites|offices|systems|branches|stores)\b",
        r"\b(?:everyone|everybody|nobody|no\s+one)\b", r"\b(?:company|organi[sz]ation|enterprise)[-\s]wide\b",
        r"\b(?:entire|whole)\s+(?:team|company|office|organi[sz]ation|department|hospital|network)\b",
        r"\bproduction\b", r"\bmultiple\s+(?:users|sites|offices|locations)\b",
        r"\balle\s+(?:nutzer|benutzer|mitarbeiter(?:innen)?|kunden|standorte|filialen|systeme)\b",
        r"\b(?:niemand|keiner)\b", r"\b(?:gesamte|ganze)n?\s+(?:team|firma|unternehmen|abteilung|netzwerk|klinik)\b",
        r"\bproduktiv(?:system|umgebung)?\b",
    ],
    "urgency": [
        r"\burgent(?:ly)?\b", r"\basap\b", r"\bimmediate(?:ly)?\b", r"\bcritical\b", r"\bemergency\b",
        r"\bsevere(?:ly)?\b", r"\bright\s+now\b", r"\bblock(?:ing|ed)\s+(?:all|our|the)\b",
        r"\bdringend\b", r"\bsofort(?:ig)?\b", r"\bkritisch\b", r"\bnotfall\b", r"\bumgehend\b", r"\beilig\b",
    ],
    "impact": [
        r"\bpatients?\b", r"\bhospital\b", r"\btelemedicine\b", r"\bemr\b", r"\bclinical\b",
        r"\bpayments?\s+(?:are\s+)?(?:failing|down|declined)\b", r"\brevenue\b", r"\bdata\s+loss\b",
        r"\bpatient(?:en)?\b", r"\bkrankenhaus\b", r"\bklinik\b", r"\bdatenverlust\b", r"\bumsatz\b",
    ],
    "security": [
        r"\b(?:security|data)\s+breach\b", r"\bhacked\b", r"\bransomware\b", r"\bmalware\b",
        r"\bcompromised\b", r"\bunauthori[sz]ed\s+access\b", r"\bphishing\s+attack\b",
        r"\bsicherheitsvorfall\b", r"\bdatenleck\b", r"\bgehackt\b", r"\bunbefugte[rn]?\s+zugriff\b",
    ],
}
NEGATION = [r"\bnot\s+(?:urgent|critical)\b", r"\bno\s+rush\b", r"\bwhen(?:ever)?\s+you\s+(?:can|have\s+time)\b",
            r"\bnicht\s+(?:dringend|eilig|kritisch)\b", r"\bkeine\s+eile\b"]

_RX = {k: [re.compile(p, _F) for p in v] for k, v in PATTERNS.items()}
_NEG = [re.compile(p, _F) for p in NEGATION]


def _hits(text, key):
    out = []
    for rx in _RX[key]:
        m = rx.search(text)
        if m:
            out.append(m.group(0))
    return out


def urgency(text: str) -> dict:
    t = text or ""
    h = {k: _hits(t, k) for k in _RX}
    negated = any(rx.search(t) for rx in _NEG)
    if negated:
        h["urgency"] = []
    out, sc, ur, im, sec = (bool(h[k]) for k in ("outage", "scope", "urgency", "impact", "security"))
    urgent = (out and (sc or ur or im)) or sec or (ur and im)
    words = list(dict.fromkeys(w for k in ("security", "outage", "scope", "impact", "urgency") for w in h[k]))
    reason = None
    if urgent:
        cats = [k for k in ("security", "outage", "scope", "impact", "urgency") if h[k]]
        reason = "Urgency rule: " + " + ".join(cats) + " (" + ", ".join(f'"{w}"' for w in words[:5]) + ")"
    return {"urgent": bool(urgent), "matches": h, "negated": negated, "reason": reason}
