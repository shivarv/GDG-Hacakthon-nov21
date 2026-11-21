# SentinelDesk: incident triage & grounded resolution copilot

For each helpdesk ticket (subject optional, English or German) SentinelDesk:

1. predicts **type, queue and priority** with calibrated confidence,
2. runs an **escalation and safety gate** (Auto-Draft Ready or Escalate to On-Call Engineer, with reasons),
3. retrieves the **top-5 most similar resolved tickets** (cross-lingual),
4. drafts a **reply in the requester's language** that cites the ticket IDs it used and never invents
   prices, refunds, SLA credits or legal guarantees.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # LLM_PROVIDER=none works without any API key
python scripts/build.py                                # split, train classifier, build FAISS index (~25 min CPU)
python scripts/build.py --max-kb 15000                 # faster build: index 15k tickets (classifier uses all)
python scripts/tune_gate.py                            # tune gate thresholds on a KB validation slice
python scripts/evaluate.py                             # holdout metrics -> artifacts/eval_report.json
streamlit run app.py                                   # console at http://localhost:8501
pytest -q                                              # 17 unit tests, no network or model download
```

**No dataset or artifacts?** `python scripts/demo.py` runs the pipeline on a 24-ticket built-in knowledge
base. `streamlit run app.py` falls back to the same demo knowledge base (with a visible warning) when
`artifacts/` is empty. Set `DEMO_MODE=1` to force it.

## Results (20% holdout, 12,353 tickets never seen in training or indexing)

| Metric | Value |
|---|---|
| Type Macro-F1 | 0.912 |
| Queue Macro-F1 | 0.921 |
| Priority Macro-F1 | 0.814 |
| High-priority recall (classifier alone) | 0.788 |
| High-priority Incident recall (classifier alone) | 0.757 |
| **Gate escalation recall on true high-priority incidents** | **0.939** |
| Auto-draft rate | 27% (the gate escalates when in doubt) |
| Latency p50 / p95 (classify + retrieve + draft) | 82 ms / 282 ms |

Gate figures come from a random 1,000-ticket holdout sample. Full report: `artifacts/eval_report.json`.
The dataset has five priority levels (`critical`, `high`, `medium`, `low`, `very_low`); `critical` is
treated as high for the gate and for high-priority recall.

## How it works

| Stage | Implementation |
|---|---|
| Classifier | word + char TF-IDF, one `LinearSVC(class_weight="balanced")` per target with sigmoid calibration |
| Language | `langdetect` with an en/de stop-word fallback |
| Retrieval | `multilingual-e5-small` + FAISS cosine (NumPy fallback), top-5. At least one hit from the other language is guaranteed when one exists, so a German ticket can use an English resolution |
| Gate | high/critical + Incident, incident-risk score, low classifier confidence, low retrieval similarity, critical-impact keywords, prompt injection, refund / pricing / SLA asks without supporting precedent, outage burst, draft guardrail failures |
| Reply | Claude or any OpenAI-compatible LLM returning strict JSON with citations; deterministic extractive fallback without a key |
| Guardrails | PII masked before any LLM call; citations to non-retrieved tickets removed; placeholders (`<name>`), money/credit sentences and weak precedents never quoted; unsupported numbers or commitment language flagged and escalated |
| Bonus | cross-lingual precedents, live outage-burst banner, PII guardrail |

## Zero data leakage

- `build.py` uses the brief's split: shuffle with seed 42, assign `TKT-xxxxx` IDs, first 80% is the KB.
  The classifier is trained on and the index built from the KB split only.
- `build.py` and `evaluate.py` assert that no holdout ticket ID is in the index.
- `evaluate.py` gives the pipeline only `subject` and `body` of holdout tickets. Labels stay aside for scoring.
- **Gate thresholds are tuned on a validation slice of the KB split** (`scripts/tune_gate.py`), never on the
  holdout. The holdout is used only to report final metrics.

## Configuration

All settings are environment variables read in `src/sentineldesk/config.py` (see `.env.example`).
Tuned gate thresholds live in `artifacts/gate_thresholds.json` (committed). A `SIM_THRESHOLD` env var
overrides the tuned similarity threshold.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `none` | `anthropic`, `openai` (any OpenAI-compatible endpoint, incl. Ollama/Groq) or `none` |
| `CONF_THRESHOLD` | `0.45` | escalate when any prediction is less confident |
| `MIN_OTHER_LANG` | `1` | cross-lingual hits guaranteed in the top-k |
| `BURST_SIM`, `BURST_MIN`, `BURST_WINDOW_MIN` | `0.88`, `3`, `15` | outage burst detection |

## Known limits

- The gate escalates about 73% of tickets. That is deliberate (a missed outage costs more than a false
  escalation). Lower `risk_threshold` in `gate_thresholds.json` to auto-draft more.
- Dataset answers are noisy, so extractive drafts (no LLM) can read awkwardly. An LLM provider gives
  fluent replies while the same citation and money guardrails apply. The real LLM path is covered by
  mocked unit tests only; it was not run against a live API.
- The queue label has about 50 classes, many unrelated to IT (for example Pets or Games).
- Burst detection uses similarity 0.88. Unrelated tickets peak near 0.87 with e5, so keep that value.
- The app runs locally. For a hosted demo, deploy `app.py` to Streamlit Community Cloud or any host and
  run `scripts/build.py` there first (or rely on the demo-mode fallback).

## Project structure

```
app.py                       Streamlit triage console
scripts/build.py             load -> clean -> 80/20 split -> train classifier -> build vector index
scripts/tune_gate.py         tune gate thresholds on a KB validation slice
scripts/evaluate.py          holdout metrics (Macro-F1, high-priority recall, gate recall, latency)
scripts/demo.py              dataset-free end-to-end demo
src/sentineldesk/            config, data, lang, pii, classifier, retriever, gate, generator, burst, pipeline, demo
tests/                       unit tests (no network, no model downloads)
```

## 5-minute demo script

1. **German, no subject**: language detected, German draft citing ticket IDs.
2. **Hospital VPN outage**: high-priority incident, escalation badge with reasons.
3. **Refund + SLA demand**: PII masked, escalated, the draft promises nothing.
4. **Prompt injection**: flagged and escalated.
5. **Outage simulation** (sidebar): three SSO tickets raise the major-incident banner.
6. Open "Holdout metrics" for Macro-F1, high-priority recall and latency.
