# Clean dataset: methodology

Audience: AI coding agents and teammates who build on `dataset/data/`. It states what was done, why, the exact definitions, the guarantees you can rely on, and the rules you must not break. Every number below comes from `data/split_meta.json` or `split_audit.txt`. Statements marked *(inferred)* were not verified directly.

---

## 0. Rules for agents (read first)

1. **Never read `data/test_labels.parquet` or `data/test_labels_all.parquet`** except in the final evaluation script. Never train on, index, calibrate on, or tune thresholds with test rows.
2. **The test split has no answers.** The test files deliberately have no `answer` column. Do not try to recover answers for test IDs from the Hugging Face source.
3. **Train on `split == "base"`. Calibrate and tune every threshold on `split == "dev"`.** Both are in `kb_train.parquet`.
4. **When tuning retrieval cutoffs on dev, the FAISS/vector index must contain base rows only.** Otherwise each dev query retrieves itself. For the live demo, index base + dev rows with `has_answer == True`.
5. **Do not change the shuffle/ID/boundary lines in `split.py`.** They reproduce the brief's official split. The cleaning never moves a ticket across the 80/20 boundary.
6. Report test metrics on **both** the clean test set (headline) and the full official test set (`*_all` files), and label which is which.

---

## 1. Source and environment

- Dataset: `Tobi-Bueck/customer-support-tickets`, Hugging Face revision `ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb`, CC BY-NC 4.0.
- `load_dataset(...)["train"]` concatenates 3 CSVs into 61,765 rows:
  - `aa_dataset-tickets-multi-lang-5-2-50-version.csv`
  - `dataset-tickets-multi-lang-4-20k.csv`
  - `dataset-tickets-german_normalized_50_5_2.csv`
- Built with Python 3.9.6, datasets 4.5.0, pandas 2.3.3, pyarrow 21.0.0, numpy 2.0.2, scikit-learn 1.6.1. Runtime is about 5 minutes on a laptop CPU.
- Determinism: the official shuffle is `df.sample(frac=1.0, random_state=42)` on the row order `load_dataset` returns. A different dataset revision or file order changes every ticket ID. Pin the revision above if you rebuild.

## 2. Official split (unchanged from the brief)

```python
df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
split_idx = int(len(df) * 0.8)        # 49,412
kb = df.iloc[:split_idx]; test = df.iloc[split_idx:]
```
`TKT-00000` to `TKT-49411` are kb (the 80%); `TKT-49412` to `TKT-61764` are test (the 20%). All IDs in `data/` are these official IDs.

## 3. Findings that motivated the cleaning

From `reference/split_official_audit.txt` and ad-hoc checks on the raw official split:

| Finding | Number |
|---|---|
| Test bodies identical (after lowercasing and collapsing whitespace) to a kb body | 2,685 / 12,353 (21.7%) |
| Label agreement between those test rows and their kb twin (type / queue / priority) | 99.8% / 99.7% / 99.6% |
| Raw dev rows (old 15% slice) with an exact twin in base | 1,330 / 7,412 (18%) |
| Repeated bodies inside kb | 5,386 |
| Extra test rows that are reworded copies of a kb row (char TF-IDF cos ≥ 0.90, not exact) | ~790 |
| Rows that are duplicates across **all** columns | 0 |

**Where the duplicates come from.** Of the roughly 5,370 duplicate-body groups in kb, 5,365 pair one row with empty `version` and one row with `version == 400`. Only 3 groups are inside a single source. So the duplicates are **across files**, not within one. *(inferred)* The 4-20k file (no `version` column, so NaN after concatenation) partly overlaps the 5-2-50 file. That explains why someone checking a single CSV, or checking whole-row equality, finds no duplicates. Duplicate rows differ in `version` and sometimes in tags or subject (about 70 have a different subject).

**Why it matters.** With 22% of test tickets having a labelled twin in training, test Macro-F1 is inflated: a nearest-neighbour lookup gets those rows right almost for free. The same applies to dev, which would make calibration and the escalation gate's confidence and similarity thresholds too optimistic (too little escalation). It also lets the top-5 retrieval return the same ticket several times.

Other raw-data artifacts:
- About 10.6k bodies and 1.5k answers contain the literal two-character sequence `\n` instead of a newline. Word tokenizers then produce junk tokens such as `nich` from `\n\nich`.
- About 1.1k bodies and 300 answers contain `<br>`.
- Name placeholders are inconsistent: `[Your Name]` (816), `[Ihr Name]` (335), `[Name]`, `[Dein Name]`, next to the dataset's own `<name>`, `<tel_num>`, `<acc_num>`.
- `priority` has 5 values (critical 1,914; high 21,925; medium 23,378; low 12,765; very_low 1,783) but the brief specifies 3.
- 13,178 rows from the German-normalized file have null `type` and null `answer`, and use 42 queues of their own. The other rows use 10 queues. The two queue sets do not overlap: 52 in total.
- Subject is null or empty in 5,299 rows (8.6%). 2 bodies are empty (both in test).

## 4. Pipeline (`split.py`), in order

### 4.1 Sanitize text (subject, body, answer)
Applied in this order:
1. Unicode NFKC normalization.
2. Literal `\r\n`, `\n`, `\r` (backslash sequences) become a real `\n`.
3. `<br>`, `<br/>`, `<br />` (case-insensitive) become `\n`.
4. Regex `\[\s*(your|ihr|ihre|dein|deine)?\s*name\s*\]` (case-insensitive) becomes `<name>`.
5. Runs of spaces, tabs and NBSPs collapse to one space. Spaces around newlines are stripped. 3 or more newlines collapse to 2. The whole string is trimmed.
6. Empty subject or answer becomes null.

`text = (subject or "") + "\n\n" + body`, trimmed. This is the model input; it never crashes on a null subject.

### 4.2 Labels
- `priority_raw` is the original 5-class value. `priority` is mapped: critical→high, high→high, medium→medium, low→low, very_low→low.
- `type` is unchanged (null for the untyped German file). Mask null types in the type loss.
- `queue_core`: True if the queue is one of the 10 queues used by typed kb rows. Derived from kb only. Equals `type.notna()` in this data.
- `tags`: list of the non-empty `tag_1..8` values, stripped, lowercased and de-duplicated in order. `tag_1..8` are kept, lowercased.
- `short_body`: True if the body is under 20 characters (about 200 rows, e.g. "Can you assist?").

### 4.3 Duplicate key
`key = lower(body)`, then every run of characters other than `[\w<>]` becomes a space, then trim. It ignores case, punctuation and whitespace, and keeps placeholder tokens. Only the **body** is compared, because the same body with a different subject is still the same ticket for evaluation.

### 4.4 kb: collapse exact duplicates
- kb rows with an empty key are dropped (0 in practice).
- For each group of kb rows sharing a key, the earliest `ticket_id` is kept. In that row:
  - `type`, `queue`, `priority` and `priority_raw` are set to the group's most common non-null value (ties go to the earliest ticket);
  - `answer` is set to the first non-null answer in the group;
  - `n_copies` is the group size and `dup_ticket_ids` lists the dropped IDs;
  - `label_conflict` is True if the group disagreed on type, queue or priority (11 groups).
- Result: 49,412 rows become **44,011** (5,401 collapsed). 33,412 have an answer (`has_answer`).

### 4.5 Near-copy detector
`TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=2, sublinear_tf=True)`, **fit on kb keys only**. Similarity is the cosine (dot product of L2-normalized TF-IDF vectors); for each query row we take the maximum over the reference set. **Near copy means cos ≥ 0.90** (`--near`). Hand inspection showed pairs at 0.84 to 0.94 are reworded versions of the same synthetic ticket, for example "request enhancement of security protocols for protecting medical data…" vs "requesting improvements to security protocols for the protection of medical data…". 0.90 is a conservative cutoff.

### 4.6 test: tag, then select the clean subset
Each test row gets one `eval_subset`, checked in this order:

| `eval_subset` | Rule | Count |
|---|---|---|
| `empty_body` | key is empty | 2 |
| `exact_kb_twin` | key equals some kb key | 2,689 |
| `test_internal_dup` | key equals an earlier (lower ID) test row's key | 349 |
| `near_kb_twin` | max char TF-IDF cos to kb ≥ 0.90 | 876 |
| `clean` | everything else | **8,437** |

Only test **inputs** (body text) are compared; test labels are never read for this. `max_sim_kb_tfidf` is stored: 1.0 for exact twins, NaN for empty or internal duplicates.

The exact-twin count is 2,689 here vs 2,685 in §3 because sanitizing (for example `\n` becoming a newline) made a few more bodies identical.

### 4.7 dev slice
- `dev` is `kb.sample(frac=0.15, random_state=7)` drawn **after** de-duplication (6,602 rows).
- Dev rows whose max char TF-IDF cos to any base row is ≥ 0.90 are moved back to `base` (617 rows). `max_sim_base_tfidf` is stored for dev candidates.
- Result: **base 38,026, dev 5,985.** Dev has no exact or near copy in base.

### 4.8 Asserted invariants (the script fails if any is violated)
- Every kb ID is below `split_idx`, which is at or below every test ID. kb and test IDs are disjoint.
- Clean test: no key in kb, every `max_sim_kb_tfidf` < 0.90, keys unique.
- Dev: no key equal to a base key, every `max_sim_base_tfidf` < 0.90.

## 5. Output schema (`data/`)

| File | Rows | Columns | Who may read it |
|---|---|---|---|
| `kb_train.parquet` | 44,011 | ticket_id, subject, body, answer, text, type, queue, queue_core, priority, priority_raw, language, version, tags, tag_1..8, split, has_answer, n_copies, dup_ticket_ids, label_conflict, short_body, max_sim_base_tfidf | training, indexing, tuning |
| `test_inputs.parquet` | 8,437 | ticket_id, subject, body, text | inference/eval (clean) |
| `test_labels.parquet` | 8,437 | ticket_id, type, queue, queue_core, priority, priority_raw, language | **final eval only** |
| `test_inputs_all.parquet` | 12,353 | ticket_id, subject, body, text, eval_subset, max_sim_kb_tfidf, short_body | inference/eval (full) |
| `test_labels_all.parquet` | 12,353 | same as test_labels | **final eval only** |
| `split_meta.json` | none | all counts above, and the list of core queues | anyone |

Row order is ascending by `ticket_id`. `test_inputs` and `test_labels` share the same row order.

## 6. Distribution after cleaning

- **kb (44,011):**
  - type: Incident 13,423; null 10,592; Request 9,607; Problem 6,988; Change 3,401.
  - priority: high 16,917; medium 16,566; low 10,528.
  - language: de 24,428; en 19,583.
- **Clean test (8,437):**
  - type: null 2,538; Incident 2,390; Request 1,668; Problem 1,272; Change 569.
  - priority: high 3,297; medium 3,098; low 2,042.
  - language: de 5,174; en 3,263.
- **Shift to be aware of:** null-type rows (the German-normalized file) are 30% of clean test vs 24% of kb. That file had few cross-file duplicates, so removing copies over-represents it. Report type and queue metrics separately on core queues and typed rows, and compare clean vs full with this in mind.

## 7. Embedding stage (prepared, NOT yet run)

`embed.py` is a Cloud Run job (CPU, 10 tasks) using `intfloat/multilingual-e5-small`, with the `"query: "` prefix on every text (symmetric similarity), L2-normalized, max 512 tokens. It reads `gs://$BUCKET/data-clean/{kb_train,test_inputs_all}.parquet` and writes shards to `gs://$BUCKET/emb-clean/e5-small/`. All 12,353 test inputs are embedded so both evaluations work.

`merge.py` writes:
- `kb_emb.npy` + `kb_ids.parquet` (with `split` and `has_answer`);
- `test_emb.npy` + `test_ids.parquet` (with `eval_subset`);
- `twin_report.parquet`, with e5 near-twin counts at cos ≥ 0.95 / 0.98 / 0.995 for all test rows and for clean test rows.

`merge.py` was tested only on synthetic shards. Commands are in `run_embed.sh`.

## 8. Known limitations

- Reworded (non-exact) duplicates **inside** kb are not collapsed. For diverse retrieval, apply MMR or skip a hit whose cos to an already-selected hit is ≥ 0.95.
- Cross-language duplicates (the same ticket in EN and DE) are not detected by character TF-IDF. The e5 twin report in `merge.py` will show them.
- One body still has a malformed `<brWarm regards…` tag.
- Most of the dataset appears to be LLM-generated, so label noise, especially queue vs type, is the main ceiling on Macro-F1. De-duplication does not fix label noise.
- No model has been trained on this data yet, so the benefit of cleaning for **model quality** is unmeasured. The main measured benefit is more honest dev and test estimates.

## 9. Reproduce

```bash
pip install datasets pandas pyarrow numpy scikit-learn
cd dataset && python3 split.py      # writes data/, prints the audit, about 5 min
```
Options: `--dev-frac 0.15 --dev-seed 7 --near 0.90 --out data`. The original uncleaned split is `reference/split_official.py`, and its audit printout is `reference/split_official_audit.txt`. **It also writes to `data/` by default, so run it with `--out data_official` or it will overwrite the clean files.**
