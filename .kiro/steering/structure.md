---
inclusion: always
---
# Project structure

```
app.py                       Streamlit triage console
scripts/build.py             load -> clean -> 80/20 split -> train classifier -> build vector index
scripts/evaluate.py          holdout metrics (Macro-F1, high-priority recall, gate recall, latency)
src/sentineldesk/
  config.py                  env-driven settings
  data.py                    loading, cleaning, text building, leakage-safe split
  lang.py                    en/de language detection
  pii.py                     PII masking guardrail
  classifier.py              multi-task triage classifier
  retriever.py               embedding + FAISS retrieval
  gate.py                    escalation & safety rules
  generator.py               grounded multilingual reply + citation validation
  burst.py                   live outage / burst detection
  pipeline.py                SentinelDesk orchestrator
tests/                       unit tests (no network, no model downloads)
```
