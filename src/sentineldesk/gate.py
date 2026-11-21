"""Escalation & safety gate. Pure function: predictions + hits + text -> decision with reasons."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .generator import safe_answer

HIGH_PRIORITY = {"high", "critical"}  # dataset also contains a "critical" level
AUTO = "AUTO_DRAFT_READY"
ESCALATE = "ESCALATE_TO_ON_CALL"

CRITICAL = re.compile(
    r"\b(outage|down for (all|everyone)|service (is )?down|all users|production (is )?down|"
    r"data (breach|leak)|breach|hacked|ransomware|malware|security incident|"
    r"hospital|patient|telemedicine|emr|life[- ]critical|emergency|"
    r"ausfall|komplett ausgefallen|störung|nicht erreichbar|datenleck|sicherheitsvorfall|"
    r"krankenhaus|patienten|notfall|gehackt)\b",
    re.I,
)

INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) (instructions|rules)|system prompt|"
    r"you are now|jailbreak|developer mode|ignoriere (alle )?(vorherigen )?anweisungen)",
    re.I,
)

# Requests that need policy authority. Escalate if no retrieved answer covers the topic.
POLICY_TOPICS = {
    "refund / compensation": (r"\b(refund|money back|compensation|reimburse|chargeback|"
                              r"rückerstattung|erstattung|entschädigung|geld zurück)\b",
                              ["refund", "reimburs", "compensat", "erstatt", "gutschrift", "credit"]),
    "pricing / discount": (r"\b(discount|price|pricing|quote|cost|rabatt|preis|angebot|kosten)\b",
                           ["price", "pricing", "discount", "quote", "preis", "rabatt", "angebot", "kosten", "cost"]),
    "SLA / legal guarantee": (r"\b(sla|guarantee|legal|lawsuit|lawyer|liability|penalty|contract terminat|"
                              r"garantie|rechtlich|anwalt|haftung|vertragsstrafe|kündigung)\b",
                              ["sla", "guarantee", "legal", "contract", "garantie", "vertrag", "rechtlich"]),
}


@dataclass
class GateDecision:
    status: str = AUTO
    reasons: list[str] = field(default_factory=list)

    @property
    def escalate(self) -> bool:
        return self.status == ESCALATE

    def add(self, reason: str):
        self.reasons.append(reason)
        self.status = ESCALATE

    def to_dict(self) -> dict:
        return {"status": self.status, "escalate": self.escalate, "reasons": list(self.reasons)}


def risk_score(preds: dict) -> float:
    """P(priority is high/critical) * P(type is Incident). 0.0 when probabilities are unavailable."""
    p_hi = sum(v for k, v in preds["priority"].get("probs", {}).items() if k in HIGH_PRIORITY)
    return p_hi * preds["type"].get("probs", {}).get("Incident", 0.0)


def decide(text: str, preds: dict, hits: list[dict], conf_threshold: float, sim_threshold: float,
           risk_threshold: float | None = None) -> GateDecision:
    d = GateDecision()

    p, ty = preds["priority"]["label"], preds["type"]["label"]
    if p in HIGH_PRIORITY and ty == "Incident":
        d.add("High-priority incident: page on-call immediately")

    if risk_threshold is not None and not (p in HIGH_PRIORITY and ty == "Incident"):
        r = risk_score(preds)
        if r >= risk_threshold:
            d.add(f"Elevated incident risk (P(high) x P(Incident) = {r:.2f} >= {risk_threshold:.2f})")

    low = [f"{t} {v['confidence']:.2f}" for t, v in preds.items() if v["confidence"] < conf_threshold]
    if low:
        d.add(f"Low classifier confidence ({', '.join(low)} < {conf_threshold:.2f})")

    top_sim = hits[0]["similarity"] if hits else 0.0
    if top_sim < sim_threshold:
        d.add(f"No close historical precedent (top similarity {top_sim:.2f} < {sim_threshold:.2f})")

    words = sorted({m.group(0).lower() for m in CRITICAL.finditer(text)})
    if words:
        d.add(f"Critical-impact language detected: {', '.join(words)}")

    if INJECTION.search(text):
        d.add("Possible prompt-injection / instruction override attempt")

    # Evidence is what a draft may actually quote: safe_answer drops money promises, so refund asks always escalate.
    evidence = " ".join(safe_answer(h.get("answer", "")) for h in hits).lower()
    for topic, (pattern, evidence_words) in POLICY_TOPICS.items():
        if re.search(pattern, text, re.I) and not any(w in evidence for w in evidence_words):
            d.add(f"Requests {topic}, which no retrieved resolution supports")

    return d
