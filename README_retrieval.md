# SentinelDesk: Retrieval

Finds the most similar past tickets for a new ticket. Their resolutions are passed to the LLM as grounded precedents, and a low top-1 similarity triggers escalation ("no historical precedent").

Uses the clean split in `dataset/data/` (see `dataset/README.md`).

## How it works

- **Model:** `intfloat/multilingual-e5-small` (EN + DE in one vector space, so cross-lingual matches work).
- **Index:** FAISS inner product on normalized vectors (cosine), built only on KB rows with `has_answer`.
- **Two indexes:**
  - `kb_all` (base + dev, 33,412 tickets) for the live demo
  - `kb_base` (base only) for tuning the threshold on dev, so dev queries never match themselves
- **Diverse top-k:** a hit is skipped if its similarity to an already-picked hit is >= 0.95.

## Files

| File | Where | What it is |
|---|---|---|
| `Retrieval.ipynb` | repo | builds the indexes on Colab GPU (clones this repo, no upload needed) |
| `retriever.py` | repo | `retrieve()`, `load_threshold()`, threshold tuning |
| `kb_all.index`, `kb_all_ids.parquet` | `data/` (Google Drive) | demo index + row-to-ticket_id map |
| `kb_base.index`, `kb_base_ids.parquet` | `data/` (Google Drive) | tuning index + map |
| `retriever_config.json` | `data/` | tuned similarity threshold |

## Rebuild / re-tune

1. Open `Retrieval.ipynb` in Colab, set Runtime to T4 GPU, Run all (about 5 min). Download the 4 index files into `data/`.
2. Run `python retriever.py` to tune the threshold on dev and print demo queries.

## Usage

```python
from retriever import retrieve, load_threshold

hits = retrieve(f"{subject} {body}", k=5)
# [{"ticket_id", "score", "subject", "answer", "language", "queue"}, ...]

no_precedent = hits[0]["score"] < load_threshold()
```

Many tickets have an empty subject, so show an answer snippet in the UI.

## Results (dev)

- **No-precedent threshold: 0.861.** Dev 5th percentile top-1 similarity is 0.900; the highest out-of-scope probe (pizza, weather, movies, EN + DE) is 0.823, so there is a clean gap.
- **Top-1 precedent label agreement:** type 0.848 / queue 0.673 / priority 0.648 (about 2x a majority-class guess).
- **Model comparison:**

| Model | type | queue | priority |
|---|---|---|---|
| e5-small (used) | 0.848 | 0.673 | 0.648 |
| e5-large | 0.838 | 0.696 | 0.658 |

e5-large gave only about +2 points on queue, so we kept e5-small for lower latency in the live demo.
