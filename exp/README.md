# Experimental track: transformer fine-tuning + kNN for triage

GPU experiments (2× RTX 3090 Ti, offline only) testing whether encoders beat the TF-IDF + logistic-regression triage in `triage/`.
- **Splits:** training uses `split == "base"`; weights are fit on `dev_cal`; selection is on `dev_tune`. These are the same 50/50 dev halves as `triage/train.py`, asserted by sha1 in `common.py`.
- **Test protocol:** test labels never went to the GPU box. Test predictions were made from inputs only, the decision was frozen in `results/decision.json`, and then `eval_test_preds.py` scored the test set **once** on the Mac (`results/test_metrics.json`).

## Result

**Recommendation:** replace TF-IDF-only triage with the fused policy (`serve/fused_triage.py` + bundle).

| | Mean Macro-F1 (type / queue / priority) | HP-Incident gate: recall / flag rate |
|---|---|---|
| **Clean test (8,437)**, TF-IDF + LR | 0.682 (0.842 / 0.495 / 0.708) | 0.946 / 0.537 |
| **Clean test**, fused policy | **0.864** (0.932 / 0.782 / 0.879) | 0.936 / **0.335** |
| Full official test (12,353), TF-IDF + LR | 0.773 | 0.965 / 0.506 |
| Full official test, fused policy | **0.910** | 0.959 / **0.285** |

- HP recall on clean test (0.936) lands just under the 95% target set on dev. For a safety margin, use the threshold for 97% dev recall.
- On dev_tune, the classifier-rule escalation rate falls from 0.92 (TF-IDF) to 0.46.
- On 28 hand-written in-scope tickets:
  - fused policy: 12/12 obvious outages flagged, 1/16 false flags;
  - TF-IDF: 9/12 outages, 4/16 false flags.

## What the policy is

Four probability sources per head:
1. TF-IDF + LR (`triage/models/triage.joblib`);
2. kNN over frozen multilingual-e5-small (the same embeddings retrieval uses);
3. a multilingual-e5-base fine-tune (4 epochs, multi-task heads, `train_mt.py`);
4. kNN over that fine-tune's embeddings.

They are combined by log-linear pooling, with weights fit on dev_cal by NLL. The weights are **gated by the e5-small top-1 similarity to the kb**:
- **≥ 0.97 ("near"):** a near-paraphrase exists, and the weights lean on kNN.
- **0.93–0.97 ("novel"):** separate weights.
- **< 0.93 ("far"):** no close precedent. Type, queue and priority use 0.7·kNN(fine-tuned embeddings) + 0.3·fine-tuned head. The HP flag comes from the fine-tuned head.

## Key findings

1. **The data is families of paraphrases.** Even after `dataset/` removed copies at char-TF-IDF ≥ 0.90, about half of dev has an e5-small neighbour at cosine ≥ 0.97, where 1-NN is 94–99% accurate. Holdout scores mostly reward memorization; judge-typed tickets don't. Our new tickets have a median top-1 similarity of 0.909.
2. **The neighbour-removed protocol is the fair generalization test.** We trained on base minus every row within 0.95 of a dev_tune row (25,438 rows left) and scored all 2,947 dev_tune rows:

   | Model | Mean Macro-F1 |
   |---|---|
   | TF-IDF | 0.546 |
   | frozen e5-small kNN | 0.507 |
   | e5-base head | 0.585 |
   | **kNN on fine-tuned e5-base embeddings** | **0.641** |
3. **The learning rate wasn't the bottleneck.** On the same protocol, lr 2e-5 / 3e-5 / 5e-5, and 3e-5 without label smoothing or augmentation, all land within ±0.01. The head plateaus by epochs 3–5 and doesn't degrade with more epochs. The ceiling is label noise.
4. **The fine-tune's value is its embedding.** kNN on fine-tuned embeddings is the best source both near the kb (0.829–0.850 on dev) and far from it (protocol above). This dissolves the memorize-vs-generalize dilemma.
5. **Seeds are stable.** e5-base kNN-ft: 0.829 / 0.832 / 0.828 across three seeds. e5-large is best (0.850), but at about 3× the CPU latency and 2.2 GB, so it was not chosen.
6. **Things that didn't work:**
   - mDeBERTa-v3-base collapsed to a constant prediction in bf16.
   - e5-small fine-tunes are weaker (kNN-ft 0.75).
   - int8 breaks e5-base: queue predictions agree with fp32 only 78–85% of the time. Serve fp32.
7. **Retracted claim.** An early note said "short fine-tunes generalize better", based on 28 hand-written tickets and a 67-row far slice. The protocol sweep does not support it.

## Serving

- **Wrapper:** `serve/fused_triage.py` (`FusedTriage`) is CPU-only. It returns `TriageModel.predict`'s output plus `evidence` (kNN top-1 similarity, nearest ticket, regime) and a "no similar past ticket" gate reason.
- **Bundle:** 1.6 GB, too big for git, so it lives in GCS. Built by `build_bundle.py`:
  - fp32 ONNX e5-small (shared with retrieval) and fp32 ONNX fine-tuned e5-base;
  - fp16 kNN indexes over the kb;
  - `config.json` (copied to `results/bundle_config.json`).
- **Latency:** 165 ms p50 and 212 ms p95 per ticket on 4 desktop P-cores (`serve/test_bundle.py`). Plan on about 2× that on Cloud Run vCPUs. Use 4 vCPUs and 4 GB.
- **Gate thresholds:** recomputed on dev_tune with the exact serving policy. The "no similar past ticket" cutoff (0.89) is a judgment call: dev's 1st percentile is 0.907, which would escalate about half of live tickets.

## Files

**Scripts:**
- `common.py`: splits, labels, metrics.
- `train_mt.py`: multi-task fine-tune, with `--exclude` for the protocol.
- `embed_frozen.py` / `embed_ft.py`: embeddings.
- `probe_knn.py`: kNN.
- `fuse.py`: leaderboard and blend.
- `policy.py`: serving policy.
- `far_eval.py`: far slice.
- `tfidf_protocol.py`: TF-IDF under the protocol.
- `robust_eval.py` + `robust/novel_tickets.jsonl`: hand-written tickets.
- `export_onnx.py`, `build_bundle.py`, `serve/`: serving.
- `make_test_preds.py` / `eval_test_preds.py`: the one-shot test.

**Results:**
- `results/`: the decision, test metrics and bundle config.
- `results/box/`: all dev-side JSONs.
