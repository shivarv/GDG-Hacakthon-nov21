"""Mac-side: dump the incumbent TF-IDF model's probabilities on dev rows and all test inputs (no labels read)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "triage")
from model import TriageModel
tm = TriageModel.load("triage/models/triage.joblib")
qa = TriageModel.load("triage/models/queue_all.joblib")
kb = pd.read_parquet("dataset/data/kb_train.parquet", columns=["ticket_id", "text", "split"])
dev = kb[kb.split == "dev"].reset_index(drop=True)
te = pd.read_parquet("dataset/data/test_inputs_all.parquet", columns=["ticket_id", "text"])
out = {"dev_ticket_id": dev.ticket_id.to_numpy(), "test_ticket_id": te.ticket_id.to_numpy()}
for split, df in (("dev", dev), ("test", te)):
    X = tm.transform(df.text.tolist())
    for h, name in (("type", "type"), ("queue", "queue"), ("priority", "priority"), ("hp_incident", "hp")):
        out[f"{split}_{name}"] = tm.proba(X, h).astype(np.float32)
        out[f"{name}_classes"] = np.array([str(c) for c in tm.classes(h)])
    out[f"{split}_queue_all"] = qa.proba(X, "queue_all").astype(np.float32)
    out["queue_all_classes"] = np.array([str(c) for c in qa.classes("queue_all")])
np.savez_compressed("exp/probs/tfidf.npz", **out)
print({k: v.shape for k, v in out.items()})
