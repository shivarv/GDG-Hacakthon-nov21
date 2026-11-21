# Design: SentinelDesk

## Architecture
```
ticket (subject?, body)
   │
   ├─ data.build_text ── handles null subject
   ├─ lang.detect_language ──────────────► en | de
   ├─ classifier.predict ────────────────► type/queue/priority + probs
   ├─ retriever.search (e5 + FAISS) ─────► top-k hits + query embedding
   ├─ gate.decide(preds, hits, text) ────► status + reasons
   ├─ burst.observe(embedding) ──────────► outage banner?
   ├─ pii.mask ──► generator.generate ───► reply + validated citations + warnings
   └─ result dict (+ latency_ms) ────────► Streamlit console / evaluate.py
```

## Components
- **Classifier:** one shared word(1–2)+char(3–5) TF-IDF feature space; per-target `CalibratedClassifierCV(LinearSVC(class_weight="balanced"), method="sigmoid", cv=3)`.
  Balanced weights favour minority classes, which helps Macro-F1 and high-priority recall.
- **Retriever:** e5 requires the `query: ` prefix for symmetric similarity; vectors are normalised so inner product = cosine.
  The encoder is injectable so tests can run without downloading a model.
- **Gate:** pure function of predictions, hits and text. Ordered rules, all reasons collected (not first-match).
- **Generator:** strict JSON contract `{reply, cited_ticket_ids}`. Post-validation removes unknown ids and
  detects unsupported numeric claims. Escalated tickets still get a draft, marked as needing human approval.
- **Burst detector:** in-memory sliding window of recent query embeddings; cosine ≥ `BURST_SIM`.

## Thresholds (tune on holdout)
| Setting | Default | Meaning |
|---|---|---|
| CONF_THRESHOLD | 0.45 | min class probability per target |
| SIM_THRESHOLD | 0.82 | min top-1 cosine (e5 cosines cluster high) |
| BURST_SIM | 0.88 | similarity for "same outage" |
| BURST_MIN | 3 | tickets needed for banner |

## Error handling
- Empty subject and body → `ValueError` shown in UI.
- LLM failure / bad JSON → fall back to extractive draft and add a warning.
