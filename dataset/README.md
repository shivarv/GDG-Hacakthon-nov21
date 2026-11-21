# SentinelDesk: clean dataset

The ready-made data is in `data/`; you don't need to re-run anything to use it. `split.py` builds it from the Hugging Face dataset: it sanitizes and de-duplicates the official split.
The full methodology (written for both people and AI agents) is in **[METHODOLOGY.md](METHODOLOGY.md)**.
The brief's official shuffle (`random_state=42`), `TKT-xxxxx` IDs and 80/20 boundary are **unchanged**.
Every ticket ID here is the official one. Cleaning only removes or flags rows on each side of the boundary.

Run: `python3 split.py` takes about 5 minutes on a laptop (needs `datasets pandas pyarrow numpy scikit-learn`).
The full printout is in `split_audit.txt` and the numbers in `data/split_meta.json`.

## What changed vs the raw official split

| Step | Raw | Clean |
|---|---|---|
| kb_train (80%) | 49,412 | **44,011** (5,401 exact duplicate bodies collapsed) |
| base / dev | 42,000 / 7,412 | **38,026 / 5,985** (617 dev rows that nearly copy base moved back to base) |
| kb rows with an answer (indexable) | 38,810 | **33,412** |
| test (20%) | 12,353 | **8,437 clean** |

Test rows removed from the clean set. They are still in `test_*_all.parquet`, tagged by `eval_subset`:
- exact copy of a kb body: 2,689
- near copy of a kb body (char TF-IDF cosine ≥ 0.90; these are reworded versions of the same ticket): 876
- duplicate of an earlier test row: 349
- empty body: 2

## Sanitizing
- Literal `\n` text (about 10.6k bodies, 1.5k answers) and `<br>` tags became real newlines. NFKC normalization, whitespace collapsed, blank lines capped at one.
- `[Your Name]`, `[Ihr Name]`, `[Dein Name]` and `[Name]` became `<name>`, the token the dataset already uses next to `<tel_num>` and `<acc_num>`. Use the same tokens in the PII masker.
- `priority` is now 3 classes (critical→high, very_low→low). The original is kept in `priority_raw`.
- `queue_core` is True for the 10 queues used by typed rows. The other 42 queues all belong to the German file with no type (`type` null), and none of the names overlap.
- `tags` is a cleaned list: lowercased, stripped, de-duplicated. `tag_1..8` are kept, lowercased.
- Duplicate groups: labels decided by majority vote (only 11 groups disagree, flagged `label_conflict`). `n_copies` and `dup_ticket_ids` keep the provenance.
- `short_body` flags bodies under 20 characters (about 200, e.g. "Can you assist?"). They are kept, but expect them to be low-confidence or escalated.

## How teammates should use it
- **Train classifiers** on `split == "base"`. **Calibrate and tune every threshold** on `split == "dev"`.
- **FAISS index:** rows with `has_answer`. While tuning similarity cutoffs on dev, build the index from base rows only. For the live demo, index base + dev.
- **eval.py:** report metrics on the clean test set (`test_inputs.parquet` / `test_labels.parquet`) as the headline number. Also report the full official 20% from `test_*_all.parquet`, for comparison with other teams. `test_labels*` are for eval.py only.
- **Heads-up on the clean test mix:** 30% of clean test rows are from the German file with no type, vs 24% in kb. That file had few duplicates, so removing copies shifts the mix. Keep this in mind when comparing clean and full numbers, and report type F1 on typed rows only.
- Embeddings: `run_embed.sh` now writes to `gs://$BUCKET/data-clean/` and `emb-clean/`, through a Cloud Run job named `embed-clean`, so nothing in the original run is overwritten. The job embeds **all** 12,353 test inputs, so both evaluations work. `kb_ids.parquet` carries `split` / `has_answer`, and `test_ids.parquet` carries `eval_subset`.

## Leak guards (asserted in split.py)
- Split boundary and ID disjointness are unchanged.
- The clean test set has no exact or near (≥ 0.90) copy in kb, and no internal duplicates.
- Dev has no exact or near copy in base.
- Duplicate detection compares test **inputs** only, never labels or answers. The TF-IDF detector is fit on kb text only.

## Files
- `data/`: clean outputs (Parquet). `split_meta.json` has every count.
- `split.py`: builds `data/`. `split_audit.txt` is its printout.
- `embed.py`, `merge.py`, `Dockerfile`, `requirements-embed.txt`, `run_embed.sh`, `.gcloudignore`: the e5-small embedding job on Cloud Run (CPU) plus the merge step. **Not run yet.**
- `reference/split_official.py` and its audit: the original, uncleaned split, kept for comparison.

## License
Derived from [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) (CC BY-NC 4.0). Changes are described above and in METHODOLOGY.md. Non-commercial use only.

## Known leftovers
- One body still contains a malformed `<brWarm regards` tag.
- Duplicates **inside** kb that are reworded rather than exact are not collapsed. For diverse top-5 results, skip a retrieved hit whose similarity to an already-picked hit is ≥ 0.95.
- Cross-language copies (the same ticket in EN and DE) aren't caught by character TF-IDF. `merge.py`'s e5 near-twin report will show them.
