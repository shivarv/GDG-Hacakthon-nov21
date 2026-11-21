"""Frozen e5 embeddings for kb (base+dev) and all test inputs. Same recipe as dataset/embed.py:
"query: " prefix, mean pooling, L2-normalized, max 512 tokens. Output matches merge.py's format:
  emb/<name>/{kb_emb.npy, kb_ids.parquet (ticket_id, split, has_answer), test_emb.npy, test_ids.parquet}
"""
import argparse
import os
import time

import numpy as np
import pandas as pd
import torch
from transformers import AutoModel, AutoTokenizer

from common import DATA, ROOT


@torch.no_grad()
def embed(model, tok, texts, max_len, bs=256):
    order = np.argsort([len(t) for t in texts])
    out = np.zeros((len(texts), model.config.hidden_size), np.float32)
    for i in range(0, len(texts), bs):
        ids = order[i:i + bs]
        enc = tok([texts[j] for j in ids], truncation=True, max_length=max_len, padding=True,
                  return_tensors="pt").to("cuda")
        with torch.autocast("cuda", dtype=torch.float16):
            h = model(**enc).last_hidden_state
        m = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
        e = ((h * m).sum(1) / m.sum(1)).float()
        out[ids] = torch.nn.functional.normalize(e, dim=-1).cpu().numpy()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="intfloat/multilingual-e5-small")
    ap.add_argument("--name", default="e5-small")
    ap.add_argument("--prefix", default="query: ")
    ap.add_argument("--max-len", type=int, default=512)
    a = ap.parse_args()
    t0 = time.time()
    out = f"{ROOT}/emb/{a.name}"
    os.makedirs(out, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModel.from_pretrained(a.model).cuda().eval()
    kb = pd.read_parquet(f"{DATA}/kb_train.parquet", columns=["ticket_id", "text", "split", "has_answer"])
    te = pd.read_parquet(f"{DATA}/test_inputs_all.parquet", columns=["ticket_id", "text", "eval_subset"])
    np.save(f"{out}/kb_emb.npy", embed(model, tok, [a.prefix + t for t in kb["text"]], a.max_len))
    kb[["ticket_id", "split", "has_answer"]].to_parquet(f"{out}/kb_ids.parquet", index=False)
    np.save(f"{out}/test_emb.npy", embed(model, tok, [a.prefix + t for t in te["text"]], a.max_len))
    te[["ticket_id", "eval_subset"]].to_parquet(f"{out}/test_ids.parquet", index=False)
    print(a.name, "done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
