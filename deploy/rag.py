"""Retrieval + grounded reply over the 80% knowledge base (kb_train.parquet). No test data is used.

Retrieval: same TF-IDF features as the classifier (word 1-2 + char 2-5 grams). Cosine = dot / 2, because
the FeatureUnion holds two L2-normalised blocks. Near-copies are dropped from the top-k, since about 29%
of tickets have reworded siblings that would otherwise fill the list.
Reply: extractive. Each sentence is taken from a precedent's agent answer and cites that ticket ID.
A guard drops sentences with numbers, placeholders or promises we can't check, so the reply never
invents a figure or a deadline. If the closest precedent is weak, the reply says so and asks for a human.
"""
import re
import time

import numpy as np
import pandas as pd

DE_WORDS = set("der die das und nicht ist ich wir sie ein eine mit für auf bei unser unsere bitte können "
               "wurde haben dass sich auch noch kein keine sehr vielen dank grüßen sehr geehrte".split())
EN_WORDS = set("the and is are we you to of for with our please can not have this that thank thanks "
               "regards dear issue been".split())
PLACEHOLDER = re.compile(r"<[^>]{1,40}>|\{[^}]{1,40}\}|\[[A-Z_ ]{2,40}\]")
RISKY = re.compile(r"\d|%|€|\$|guarantee|garantier|refund|erstatt|within\s+\w+\s+(hours|days)|"
                   r"innerhalb von|immediately credit|free of charge|kostenlos", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
MIN_SIM = 0.15  # below this the closest precedent is too far away to ground a reply (gibberish ~0.05)


def lang_of(text: str) -> str:
    w = re.findall(r"[a-zäöüß]+", (text or "").lower())
    de = sum(t in DE_WORDS for t in w) + 3 * sum(ch in "äöüß" for ch in (text or "").lower()[:2000])
    en = sum(t in EN_WORDS for t in w)
    return "de" if de > en else "en"


class RAG:
    def __init__(self, features, kb_path: str):
        t0 = time.perf_counter()
        kb = pd.read_parquet(kb_path, columns=["ticket_id", "subject", "body", "answer", "text", "type",
                                               "queue", "priority", "has_answer"])
        kb = kb[kb["has_answer"] & kb["answer"].fillna("").str.len().gt(20)].reset_index(drop=True)
        self.kb = kb
        self.features = features
        X = features.transform(kb["text"]).tocsr()
        X.data = X.data.astype(np.float32)
        self.X = X
        self.lang = np.array([lang_of(a) for a in kb["answer"]])
        self.build_s = round(time.perf_counter() - t0, 1)

    def retrieve(self, text: str, k: int = 5, pool: int = 40):
        q = self.features.transform([text]).tocsr()
        q.data = q.data.astype(np.float32)
        s = (self.X @ q.T).toarray().ravel() / 2.0
        qlang = lang_of(text)
        s_lang = np.where(self.lang == qlang, s, s - 0.05)  # prefer answers in the customer's language
        cand = np.argpartition(-s_lang, pool)[:pool]
        cand = cand[np.argsort(-s_lang[cand])]
        chosen = []
        for c in cand:  # diversity: skip reworded copies of a precedent already chosen
            if chosen:
                dup = (self.X[chosen] @ self.X[c].T).toarray().ravel() / 2.0
                if dup.max() >= 0.80:
                    continue
            chosen.append(int(c))
            if len(chosen) == k:
                break
        out = []
        for c in chosen:
            r = self.kb.iloc[c]
            out.append({"ticket_id": r["ticket_id"], "similarity": round(float(s[c]), 3),
                        "subject": r["subject"], "body": (r["body"] or "")[:400],
                        "answer": r["answer"], "type": r["type"], "queue": r["queue"],
                        "priority": r["priority"], "language": str(self.lang[c])})
        return out, qlang

    def reply(self, precedents, qlang: str) -> dict:
        de = qlang == "de"
        hello = "Guten Tag," if de else "Hello,"
        bye = "Mit freundlichen Grüßen\nIhr Support-Team" if de else "Best regards,\nSupport team"
        if not precedents or precedents[0]["similarity"] < MIN_SIM:
            top = precedents[0]["similarity"] if precedents else 0.0
            msg = ("vielen Dank für Ihre Nachricht. Wir haben keinen ausreichend ähnlichen gelösten Fall "
                   "gefunden und leiten Ihre Anfrage an einen Mitarbeiter weiter." if de else
                   "thank you for your message. We found no sufficiently similar resolved case, so a member "
                   "of our team will review your request personally.")
            return {"text": f"{hello}\n\n{msg}\n\n{bye}", "sentences": [], "cited_ticket_ids": [],
                    "grounded": False, "needs_human": True,
                    "reason": f"closest precedent similarity {top:.2f} < {MIN_SIM}"}
        sents, dropped = [], 0
        for p in precedents[:3]:
            if p["language"] != qlang or p["similarity"] < MIN_SIM:
                continue
            for s in SENT_SPLIT.split(p["answer"].strip()):
                s = s.strip()
                if len(s) < 25:
                    continue
                if PLACEHOLDER.search(s) or RISKY.search(s):
                    dropped += 1
                    continue
                if any(s == x["text"] for x in sents):
                    continue
                sents.append({"text": s, "ticket_id": p["ticket_id"]})
                if len(sents) >= 3:
                    break
            if len(sents) >= 3:
                break
        if not sents:
            return {"text": f"{hello}\n\n" + ("vielen Dank, ein Mitarbeiter meldet sich in Kürze bei Ihnen." if de
                                              else "thank you, a member of our team will follow up shortly.")
                    + f"\n\n{bye}", "sentences": [], "cited_ticket_ids": [], "grounded": False,
                    "needs_human": True, "reason": "no safe sentence in the precedents' answers"}
        body = " ".join(f"{x['text']} [{x['ticket_id']}]" for x in sents)
        return {"text": f"{hello}\n\n{body}\n\n{bye}", "sentences": sents,
                "cited_ticket_ids": sorted({x["ticket_id"] for x in sents}), "grounded": True,
                "needs_human": False, "guard_dropped_sentences": dropped}

    def run(self, text: str, k: int = 5) -> dict:
        t0 = time.perf_counter()
        prec, qlang = self.retrieve(text, k)
        rep = self.reply(prec, qlang)
        return {"language": qlang, "precedents": prec, "reply": rep,
                "top_similarity": prec[0]["similarity"] if prec else 0.0,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
