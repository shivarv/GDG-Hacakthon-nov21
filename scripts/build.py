"""Build all artifacts: split -> classifier -> vector index.

Usage:
    python scripts/build.py                 # full run
    python scripts/build.py --max-kb 10000  # faster: index only 10k KB tickets (classifier still uses all)
    python scripts/build.py --csv data/dataset-tickets-multi-lang-4-20k.csv
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentineldesk.classifier import TriageClassifier  # noqa: E402
from sentineldesk.config import SETTINGS  # noqa: E402
from sentineldesk.data import TARGETS, clean, load_raw, split  # noqa: E402
from sentineldesk.retriever import E5Encoder, Retriever  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="", help="local CSV instead of Hugging Face download")
    ap.add_argument("--max-kb", type=int, default=0, help="limit tickets embedded into the index")
    ap.add_argument("--skip-index", action="store_true")
    args = ap.parse_args()

    s = replace(SETTINGS, dataset_csv=args.csv) if args.csv else SETTINGS
    art = Path(s.artifacts_dir)
    art.mkdir(parents=True, exist_ok=True)

    print("1/4 Loading dataset…")
    df = clean(load_raw(s), s)
    kb, test = split(df, s)
    kb.to_parquet(art / "kb_train.parquet", index=False)
    test.to_parquet(art / "test_holdout.parquet", index=False)
    print(f"    {len(df):,} clean tickets -> KB {len(kb):,} / holdout {len(test):,}")
    print("    null/empty subjects:", int((df['subject'].str.len() == 0).sum()))
    for t in TARGETS:
        print(f"    {t}: {kb[t].value_counts().to_dict()}")

    print("2/4 Training classifier on KB split…")
    t0 = time.time()
    clf = TriageClassifier().fit(kb["text"].tolist(), {t: kb[t].tolist() for t in TARGETS})
    clf.save(art / "classifier.joblib")
    print(f"    done in {time.time() - t0:.0f}s")

    if not args.skip_index:
        print("3/4 Embedding KB and building index (first run downloads the model)…")
        t0 = time.time()
        kb_index = kb.sample(n=args.max_kb, random_state=s.seed) if 0 < args.max_kb < len(kb) else kb
        r = Retriever(E5Encoder(s.embed_model)).build(kb_index)
        r.save(art / "index")
        print(f"    indexed {len(kb_index):,} tickets in {time.time() - t0:.0f}s")

        print("4/4 Leakage check…")
        overlap = r.ticket_ids() & set(test["ticket_id"])
        assert not overlap, f"LEAKAGE: {len(overlap)} holdout tickets in index!"
        print("    OK: no holdout ticket in the index")

    (art / "build_info.json").write_text(json.dumps({
        "kb": len(kb), "holdout": len(test), "embed_model": s.embed_model, "max_kb": args.max_kb,
    }, indent=2))
    print("Build complete. Next: python scripts/evaluate.py  and  streamlit run app.py")


if __name__ == "__main__":
    main()
