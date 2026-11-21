# live/: burst banner + diverse precedents

Owner: live-path side session. Nothing here is imported by `triage/` or `deploy/` yet; wire it in from the app.

## `burst.py`: Major Incident banner
```python
from live.burst import BurstDetector
det = BurstDetector()          # one per process; Cloud Run: max-instances=1, or state is per instance
out = det.add(ticket_id, text, ts, triage_type=pred_type, vec=e5_query_vec)  # vec optional: reuse the FAISS query vector
# -> {"in_burst", "cluster_id", "size", "cos_to_centroid", "banner", "reason"}
# reason e.g. "Part of active outage cluster (n=4)"  -> add to the escalation gate reasons
det.active_bursts()            # for a page-level banner poll (list of bursting clusters + member ids)
det.status(ticket_id)          # earlier tickets join a burst after their own add(); re-check here
```
- Window: last 200 tickets AND last 15 min. Burst = cluster with >= 3 live tickets, strict majority Incident/Problem.
- `vec` must be the **raw** L2-normalized e5-small vector of `"query: " + text` (what FAISS uses). The detector de-biases it itself.

### Why not raw cosine 0.86
Raw e5-small cosines on this dataset are very compressed. Over 2,000 random dev pairs, the median is 0.850 and 39% of pairs are >= 0.86. The 99.5th percentile is 0.928, while the hand-written VPN-outage tickets sit at 0.896–0.96. At raw 0.86, a 200-ticket dev stream ends up with one cluster of about 180 tickets.
The fix is to de-bias the vectors: subtract the corpus mean, project out the top 2 principal directions, and renormalize. The mean and PCs are fit on 6,000 `base` rows and stored in `e5_debias.npz`. After that, random pairs centre on 0. The default threshold of **0.45** (in de-biased space) leaves 0.30% of random dev pairs above it (0.49% same-language). Replay outage tickets join their cluster at cos 0.63–0.73. Full sweep: `calibration.json`.
If dataset tickets are replayed fast (200 in 13 min), real topic families in the synthetic data still form Incident clusters of 3+, for example "dashboard timeouts" and a hospital security breach. Raise the threshold to 0.50 to make those rarer.

## `dedup.py`
`diverse_topk(cand_ids, cand_vecs, cand_sims, k=5, max_cos=0.95) -> (ids, sims, skipped)`: a greedy walk in similarity order. It skips a hit whose raw cosine to an already-kept hit is >= 0.95. `skipped` lists `(id, kept_id, cos)`.

## Run
```
python live/calibrate.py [--rebuild]   # dev rows only; writes calibration.json (+ e5_debias.npz with --rebuild)
python live/test_live.py               # replay + dedup checks + calibration table; exit 0 = pass
```
Needs `sentence-transformers` (CPU torch is fine). Verified on pocket-battleship `~/dev/sentineldesk/.venv-live`.
