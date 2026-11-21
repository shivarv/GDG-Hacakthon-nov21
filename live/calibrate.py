"""Calibrate the burst join threshold on DEV rows only (kb_train.parquet, split == "dev"; test files never read).

0. Build live/e5_debias.npz (corpus mean + top-2 PCs) from 6,000 random kb `base` rows (not dev, not test).
1. Random-pair false-match rate: ~2,000 random dev pairs, share with cos >= t for t in 0.84..0.90.
2. Stream check: replay random 200-ticket windows of dev rows (gold `type` as triage_type) through
   BurstDetector and count how often a banner would fire with no real outage. Dev rows come from
   reworded ticket families, so some of these "bursts" are genuine near-duplicates, not noise; the
   examples are printed so you can judge.

Writes live/calibration.json.  Usage: python live/calibrate.py [--pairs 2000] [--streams 20]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from burst import DEBIAS_PATH, BurstDetector, Debias, embed  # noqa: E402

KB = HERE.parent / "dataset" / "data" / "kb_train.parquet"
SPACES = {"raw": [0.84, 0.85, 0.86, 0.87, 0.88, 0.89, 0.90, 0.92, 0.93],
          "debiased": [0.35, 0.38, 0.40, 0.42, 0.45, 0.48, 0.50, 0.55]}
N_PCS = 2


def build_debias(kb, rng_seed=1, n=6000):
    base = kb[kb["split"] == "base"].sample(n, random_state=rng_seed)
    vb = embed(base["text"].tolist())
    mu = vb.mean(0)
    _, _, vt = np.linalg.svd(vb - mu, full_matrices=False)
    np.savez(DEBIAS_PATH, mu=mu.astype(np.float32), pcs=vt[:N_PCS].astype(np.float32))
    return Debias(mu, vt[:N_PCS])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=2000)
    ap.add_argument("--streams", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rebuild", action="store_true", help="rebuild live/e5_debias.npz from base rows")
    a = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(a.seed)

    kb = pd.read_parquet(KB, columns=["ticket_id", "text", "type", "language", "split"])
    deb = build_debias(kb) if (a.rebuild or not DEBIAS_PATH.exists()) else Debias.load()
    dev = kb[kb["split"] == "dev"].reset_index(drop=True)
    print(f"dev rows: {len(dev):,}", flush=True)

    i = rng.integers(0, len(dev), a.pairs)
    j = rng.integers(0, len(dev), a.pairs)
    keep = i != j
    i, j = i[keep], j[keep]
    windows = [rng.choice(len(dev), 200, replace=False) for _ in range(a.streams)]
    need = np.unique(np.concatenate([i, j] + windows))
    raw = np.zeros((len(dev), 384), dtype=np.float32)
    raw[need] = embed(dev["text"].iloc[need].tolist())
    print(f"embedded {len(need):,} dev texts in {time.time() - t0:.0f}s", flush=True)
    same_lang = dev["language"].values[i] == dev["language"].values[j]
    no_embed = lambda x: (_ for _ in ()).throw(RuntimeError("no embed"))  # noqa: E731

    pair, stream, examples = {}, {}, {}
    for space, grid in SPACES.items():
        V = raw if space == "raw" else deb(raw)
        cos = np.einsum("nd,nd->n", V[i], V[j])
        pair[space] = {
            "n_pairs": int(len(cos)),
            "mean": round(float(cos.mean()), 4),
            "quantiles": {q: round(float(np.quantile(cos, float(q))), 4) for q in ["0.5", "0.9", "0.99", "0.995", "0.999"]},
            "share_ge": {f"{t:.2f}": round(float((cos >= t).mean()), 5) for t in grid},
            "share_ge_same_language": {f"{t:.2f}": round(float((cos[same_lang] >= t).mean()), 5) for t in grid},
            "top_pairs": [{"cos": round(float(cos[k]), 4), "a": dev["text"].iloc[i[k]][:90], "b": dev["text"].iloc[j[k]][:90]}
                          for k in np.argsort(-cos)[:3]],
        }
        stream[space] = {}
        for t in grid:
            n_fired, n_banner, max_sizes = 0, 0, []
            for w in windows:
                det = BurstDetector(threshold=t, embed_fn=no_embed, space=space, debias=deb)
                fired = False
                for step, r in enumerate(w):  # 200 tickets over ~13 min
                    out = det.add(dev["ticket_id"].iloc[r], "", ts=step * 4.0, triage_type=dev["type"].iloc[r], vec=raw[r])
                    n_banner += out["in_burst"]
                    fired |= out["in_burst"]
                max_sizes.append(max(len(c.members) for c in det._clusters.values()))
                n_fired += fired
                key = f"{space}@{t:.2f}"
                if fired and len(examples.get(key, [])) < 2:
                    b = det.active_bursts()
                    if b:
                        txt = dev.set_index("ticket_id")["text"]
                        examples.setdefault(key, []).append([txt.loc[x][:90] for x in b[0]["ticket_ids"][:4]])
            stream[space][f"{t:.2f}"] = {"windows": len(windows), "windows_with_banner": int(n_fired),
                                         "banner_ticket_rate": round(n_banner / (200 * len(windows)), 5),
                                         "median_max_cluster": float(np.median(max_sizes))}
    out = {"model": "intfloat/multilingual-e5-small", "prefix": "query: ", "source": "kb_train.parquet split==dev",
           "debias": {"file": "live/e5_debias.npz", "fit_on": "6000 random kb base rows", "n_pcs": N_PCS},
           "random_pairs": pair, "stream_200_windows": stream, "stream_burst_examples": examples,
           "seconds": round(time.time() - t0)}
    (HERE / "calibration.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps({k: out[k] for k in ("random_pairs", "stream_200_windows")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
