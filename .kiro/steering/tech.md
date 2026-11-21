---
inclusion: always
---
# Tech stack

- Python 3.10+
- Classifier: scikit-learn (word + char TF-IDF, LinearSVC with sigmoid calibration), one model per target.
- Retrieval: sentence-transformers `intfloat/multilingual-e5-small` (cross-lingual en/de) + FAISS inner-product index
  on L2-normalised vectors (cosine similarity). NumPy fallback when FAISS is unavailable.
- LLM: pluggable provider via `LLM_PROVIDER` = `anthropic` | `openai` (any OpenAI-compatible endpoint, incl. Ollama/Groq) | `none`
  (deterministic extractive fallback, no API key needed).
- UI: Streamlit.
- Tests: pytest.

Conventions:
- All config comes from environment variables read in `src/sentineldesk/config.py`.
- Artifacts (models, index, splits, eval reports) live in `artifacts/` and are git-ignored.
- PII is masked before any text leaves the process (LLM calls).
- Keep functions pure where possible; the `SentinelDesk` class in `pipeline.py` is the only orchestrator.
