# SentinelDesk: incident triage & grounded resolution copilot

Classifies helpdesk tickets (type, queue, priority + calibrated confidence), decides whether to
escalate, retrieves similar resolved tickets, and drafts an English or German reply that cites the
ticket IDs it used. Built for the 6-hour SentinelDesk hackathon brief.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # set LLM_PROVIDER + API key, or keep "none"

python scripts/build.py --max-kb 15000   # ~5-10 min on CPU; drop --max-kb for the full KB
python scripts/evaluate.py               # holdout metrics -> artifacts/eval_report.json
streamlit run app.py                     # triage console at http://localhost:8501
pytest -q                                # unit tests (no network needed)
```
Offline/local CSV: `python scripts/build.py --csv data/aa_dataset-tickets-multi-lang-5-2-50-version.csv`

## Using it in Kiro
Open the folder in Kiro. The `.kiro/steering/` files (product, tech, structure) are always loaded, so
the agent knows the leakage rules and conventions. The spec lives in `.kiro/specs/sentineldesk/`
(requirements in EARS format, design, tasks). Tasks 1-14 are implemented; open `tasks.md` and run
task 15 (threshold tuning) and 16 (demo prep) with the agent.

## How it works
| Stage | Implementation |
|---|---|
| Classifier | word + char TF-IDF, per-target `LinearSVC(class_weight="balanced")` with sigmoid calibration |
| Language | `langdetect`, with an en/de stop-word fallback |
| Retrieval | `multilingual-e5-small` + FAISS cosine, top-5, cross-lingual by design |
| Gate | high+Incident, low confidence, low similarity, critical keywords, policy asks without precedent, prompt injection, outage burst |
| Reply | Claude / any OpenAI-compatible LLM with strict JSON + citation validation; extractive fallback with no key |
| Guardrails | PII masking before LLM calls; non-retrieved citations stripped; unsupported money/%/duration claims flagged and escalated |
| Bonus | cross-lingual precedents, burst detection banner, PII guardrail |

## Leakage protection
`build.py` uses the brief's exact split (shuffle seed 42 → `TKT-xxxxx` → 80/20). The classifier and the
index see only the KB split, and both scripts assert that no holdout ID is in the index. `evaluate.py` passes
only `subject` and `body` to the pipeline.

## Tuning (task 15)
After `evaluate.py`, look at `top1_similarity_p10_p50_p90` and set `SIM_THRESHOLD` near the p10 value,
then lower `CONF_THRESHOLD` until `gate_high_incident_escalation_recall` stays ≥ 0.95 with an acceptable
`auto_draft_rate`. Record the final values here.

## 5-minute demo script
1. **German, no subject** (sidebar example): language detected, auto-draft in German citing ticket IDs.
2. **Hospital VPN outage**: high-priority incident, red escalation badge with reasons.
3. **Refund + lawyer threat**: PII masked, escalated because no precedent supports refunds; no invented numbers.
4. **Prompt injection**: flagged and escalated.
5. **Outage simulation**: three SSO tickets → major-incident banner.
6. Open "Holdout metrics" to show Macro-F1, high-priority recall and latency.
