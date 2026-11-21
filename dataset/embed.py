"""Embed every ticket (clean kb_train + ALL official test INPUTS, so eval can report clean and full) with multilingual-e5-small on CPU.

Runs as a Cloud Run job with N parallel tasks; each task embeds every N-th row and writes one shard:
  gs://$BUCKET/$OUT_PREFIX/shard_XXX.npy        float32 [n, 384], L2-normalized
  gs://$BUCKET/$OUT_PREFIX/shard_XXX_ids.parquet ticket_id per row, same order

Embedding test inputs is allowed: they are inputs, not labels. Labels/answers are never read here.
e5 note: ticket-to-ticket matching is a *symmetric* task, so every text gets the "query: " prefix
(the model card recommends "query: " for symmetric similarity and for embeddings used as features).
"""
import os
import time

import gcsfs
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer

BUCKET = os.environ["BUCKET"]
MODEL = os.environ.get("MODEL", "intfloat/multilingual-e5-small")
PREFIX = os.environ.get("PREFIX", "query: ")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "data-clean")
OUT_PREFIX = os.environ.get("OUT_PREFIX", "emb-clean/e5-small")
THREADS = int(os.environ.get("THREADS", "4"))  # match the job's --cpu
TASK = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
N_TASKS = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))


def main() -> None:
    t0 = time.time()
    torch.set_num_threads(THREADS)
    fs = gcsfs.GCSFileSystem()

    kb = pd.read_parquet(f"gs://{BUCKET}/{DATA_PREFIX}/kb_train.parquet", columns=["ticket_id", "text"])
    te = pd.read_parquet(f"gs://{BUCKET}/{DATA_PREFIX}/test_inputs_all.parquet", columns=["ticket_id", "text"])
    df = pd.concat([kb, te], ignore_index=True).sort_values("ticket_id").reset_index(drop=True)
    shard = df.iloc[TASK::N_TASKS]
    print(f"task {TASK}/{N_TASKS}: {len(shard):,} rows", flush=True)

    model = SentenceTransformer(MODEL, device="cpu")
    model.max_seq_length = 512
    texts = [PREFIX + t for t in shard["text"].tolist()]
    emb = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ).astype(np.float32)

    base = f"{BUCKET}/{OUT_PREFIX}/shard_{TASK:03d}"
    with fs.open(f"{base}.npy", "wb") as f:
        np.save(f, emb)
    shard[["ticket_id"]].to_parquet(f"gs://{base}_ids.parquet", index=False)
    print(f"task {TASK}: wrote {emb.shape} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
