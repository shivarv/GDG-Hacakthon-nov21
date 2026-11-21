# Implementation plan: SentinelDesk

- [x] 1. Project setup: config, requirements, steering docs _(Req 1)_
- [x] 2. Data layer: load from HF or CSV, clean nulls, build text, 80/20 split with ticket ids _(Req 1, 2.2)_
- [x] 3. Language detection with langdetect + stop-word fallback _(Req 3)_
- [x] 4. PII masking guardrail _(Req 7)_
- [x] 5. Multi-task calibrated classifier with save/load _(Req 2)_
- [x] 6. Embedding retriever with FAISS + NumPy fallback, injectable encoder _(Req 5)_
- [x] 7. Escalation & safety gate with reasons _(Req 4)_
- [x] 8. Grounded generator: anthropic / openai-compatible / extractive, citation + number validation _(Req 6)_
- [x] 9. Burst detector _(Req 8)_
- [x] 10. Pipeline orchestrator with latency _(Req 2–8)_
- [x] 11. build.py: train + index, leakage assertion _(Req 1)_
- [x] 12. evaluate.py: Macro-F1, high-priority recall, gate recall, latency p50/p95 _(Req 1.3, 2.3)_
- [x] 13. Streamlit console with examples and burst simulation _(Req 9)_
- [x] 14. Unit tests for data, lang, pii, gate, generator validation, retriever _(all)_
- [ ] 15. Tune CONF_THRESHOLD / SIM_THRESHOLD on holdout and record in README
- [ ] 16. Rehearse 5-minute demo script (see README)
