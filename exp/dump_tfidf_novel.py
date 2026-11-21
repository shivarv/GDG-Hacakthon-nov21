"""Mac-side: TF-IDF probabilities for the hand-written novel tickets (exp/robust/novel_tickets.jsonl)."""
import json, sys, numpy as np
sys.path.insert(0, "triage")
from model import TriageModel
from textprep import build_text
tm = TriageModel.load("triage/models/triage.joblib")
rows = [json.loads(l) for l in open("exp/robust/novel_tickets.jsonl")]
X = tm.transform([build_text(r["subject"], r["body"]) for r in rows])
out = {}
for h, name in (("type", "type"), ("queue", "queue"), ("priority", "priority"), ("hp_incident", "hp")):
    out[f"novel_{name}"] = tm.proba(X, h).astype(np.float32)
    out[f"{name}_classes"] = np.array([str(c) for c in tm.classes(h)])
np.savez_compressed("exp/probs/tfidf_novel.npz", **out)
print("ok", len(rows))
