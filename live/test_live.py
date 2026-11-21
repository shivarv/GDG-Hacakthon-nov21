"""Live-path checks: outage replay through BurstDetector, diverse_topk unit checks, calibration summary.

Usage: python live/test_live.py           (needs sentence-transformers + the e5-small model)
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from burst import BurstDetector, embed  # noqa: E402
from dedup import diverse_topk  # noqa: E402

T0 = 1_763_740_800.0  # arbitrary epoch base for the replay


def test_replay() -> bool:
    rp = json.loads((HERE / "replay_outage.json").read_text())["tickets"]
    vecs = embed([t["text"] for t in rp])
    det = BurstDetector()
    print("== Replay (threshold %.2f, window %d tickets / %d s) ==" % (det.threshold, det.max_items, det.window_s))
    triggered = []
    for t, v in zip(rp, vecs):
        out = det.add(t["ticket_id"], t["text"], T0 + t["offset_s"], triage_type=t["triage_type"], vec=v)
        tag = "BANNER" if out["banner"] else "      "
        print(f"  {tag} {t['ticket_id']} [{t['lang']}/{t['triage_type']:<8}] cluster={out['cluster_id']} "
              f"size={out['size']} cos={out['cos_to_centroid']:.3f}  {out['reason'] or ''}")
        if out["banner"]:
            triggered.append(t["ticket_id"])
    print(f"  tickets whose add() raised the banner: {triggered}")
    bursts = det.active_bursts()
    for b in bursts:
        print(f"  active: {b['banner']}\n          members={b['ticket_ids']}")

    outage = {t["ticket_id"] for t in rp if t["expect_outage"]}
    routine = {t["ticket_id"] for t in rp if not t["expect_outage"]}
    in_burst_now = {tid for b in bursts for tid in b["ticket_ids"]}
    ok = True
    if not triggered:
        print("  FAIL: banner never fired"); ok = False
    if set(triggered) & routine:
        print(f"  FAIL: routine tickets raised the banner: {set(triggered) & routine}"); ok = False
    if in_burst_now & routine:
        print(f"  FAIL: routine tickets inside the burst cluster: {in_burst_now & routine}"); ok = False
    missed = outage - in_burst_now
    if missed:
        print(f"  WARN: outage tickets not in the burst cluster: {sorted(missed)}")
    print(f"  outage recall {len(outage & in_burst_now)}/{len(outage)}; routine false alarms {len(in_burst_now & routine)}/{len(routine)}")

    oi = [k for k, t in enumerate(rp) if t["expect_outage"]]
    ri = [k for k, t in enumerate(rp) if not t["expect_outage"]]
    for name, V in (("raw", vecs), ("debiased", det.debias(vecs))):
        sims = V @ V.T
        oo = [sims[a, b] for a in oi for b in oi if a < b]
        orr = [sims[a, b] for a in oi for b in ri]
        print(f"  pairwise cos [{name}]: outage-outage min {min(oo):.3f} mean {np.mean(oo):.3f}; "
              f"outage-routine max {max(orr):.3f} mean {np.mean(orr):.3f}")

    # Same tickets but labelled Request: cluster may form, banner must not fire (type gate).
    det2 = BurstDetector()
    fired2 = any(det2.add(t["ticket_id"], t["text"], T0 + t["offset_s"], triage_type="Request", vec=v)["banner"]
                 for t, v in zip(rp, vecs))
    print(f"  type gate (all labelled Request) -> banner fired: {fired2}")
    ok &= not fired2

    # Window expiry: the outage tickets age out after 15 min.
    print(f"  bursts 16 min after last ticket: {len(det.active_bursts(now=T0 + 540 + 960))}")
    ok &= len(det.active_bursts(now=T0 + 540 + 960)) == 0
    print("  replay:", "PASS" if ok else "FAIL")
    return ok


def test_dedup() -> bool:
    rng = np.random.default_rng(0)
    base = rng.normal(size=(6, 32)).astype(np.float32)
    base /= np.linalg.norm(base, axis=1, keepdims=True)
    # 20 candidates: families of rewordings around 6 base vectors
    fam = np.array([0, 0, 0, 1, 1, 2, 0, 3, 1, 4, 2, 5, 3, 0, 4, 5, 1, 2, 3, 4])
    vecs = base[fam] + 0.03 * rng.normal(size=(20, 32)).astype(np.float32)
    sims = np.linspace(0.93, 0.80, 20)
    ids = [f"T{k:02d}" for k in range(20)]
    kept, ksims, skipped = diverse_topk(ids, vecs, sims, k=5, max_cos=0.95)
    kf = [int(fam[ids.index(x)]) for x in kept]
    ok = len(kept) == 5 and len(set(kf)) == 5 and list(ksims) == sorted(ksims, reverse=True)
    print("== diverse_topk ==")
    print(f"  kept {kept} families {kf}; skipped {len(skipped)} near-copies e.g. {skipped[:2]}")
    # all-identical candidates -> 1 result
    k1, _, _ = diverse_topk(ids[:4], np.tile(base[:1], (4, 1)), sims[:4], k=5)
    ok &= k1 == ["T00"]
    print("  dedup:", "PASS" if ok else "FAIL")
    return ok


def show_calibration():
    p = HERE / "calibration.json"
    print("== Calibration (dev rows only; random pairs + 200-ticket dev streams with gold type) ==")
    if not p.exists():
        print("  live/calibration.json missing: run python live/calibrate.py"); return
    c = json.loads(p.read_text())
    for space, rp in c["random_pairs"].items():
        print(f"  [{space}] {rp['n_pairs']} random dev pairs: mean cos {rp['mean']}, quantiles {rp['quantiles']}")
        print("    thr   pairs>=thr  same-lang   streams w/ banner   banner-ticket rate   median max cluster")
        for t, s in rp["share_ge"].items():
            st = c["stream_200_windows"][space][t]
            print(f"    {t}  {100 * s:8.2f}%  {100 * rp['share_ge_same_language'][t]:8.2f}%   "
                  f"{st['windows_with_banner']:>6}/{st['windows']:<6}       {100 * st['banner_ticket_rate']:6.2f}%"
                  f"            {st['median_max_cluster']:.0f}")


if __name__ == "__main__":
    ok = test_replay()
    ok &= test_dedup()
    show_calibration()
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)
