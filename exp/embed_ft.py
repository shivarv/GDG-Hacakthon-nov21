"""Pooled embeddings from a fine-tuned run (pre-head, L2-normalized) -> emb/ft_<run_id>/ for probe_knn.py.
Also writes the run's own head probabilities for test inputs already (train_mt.py does that)."""
import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

from common import DATA, HEADS, ROOT
from train_mt import MTModel


@torch.no_grad()
def pooled(model, tok, texts, max_len, bs=256):
    order = np.argsort([len(t) for t in texts])
    out = np.zeros((len(texts), model.enc.config.hidden_size), np.float32)
    for i in range(0, len(texts), bs):
        ids = order[i:i + bs]
        enc = tok([texts[j] for j in ids], truncation=True, max_length=max_len, padding=True,
                  return_tensors="pt").to("cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            h = model.enc(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"]).last_hidden_state
        m = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
        out[ids] = F.normalize(((h * m).sum(1) / m.sum(1)).float(), dim=-1).cpu().numpy()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args()
    run = f"{ROOT}/runs/{a.run_id}"
    cfg = json.load(open(f"{run}/config.json"))
    met = json.load(open(f"{run}/metrics.json"))
    model = MTModel(cfg["model"], met["sizes"]).cuda().eval()
    model.load_state_dict(torch.load(f"{run}/best.pt"))
    tok = AutoTokenizer.from_pretrained(f"{run}/tokenizer")
    px = cfg["prefix_used"]
    out = f"{ROOT}/emb/ft_{a.run_id}"
    os.makedirs(out, exist_ok=True)
    kb = pd.read_parquet(f"{DATA}/kb_train.parquet", columns=["ticket_id", "text", "split", "has_answer"])
    te = pd.read_parquet(f"{DATA}/test_inputs_all.parquet", columns=["ticket_id", "text", "eval_subset"])
    np.save(f"{out}/kb_emb.npy", pooled(model, tok, [px + t for t in kb["text"]], cfg["max_len"]))
    kb[["ticket_id", "split", "has_answer"]].to_parquet(f"{out}/kb_ids.parquet", index=False)
    np.save(f"{out}/test_emb.npy", pooled(model, tok, [px + t for t in te["text"]], cfg["max_len"]))
    te[["ticket_id", "eval_subset"]].to_parquet(f"{out}/test_ids.parquet", index=False)
    print("done", out)


if __name__ == "__main__":
    main()
