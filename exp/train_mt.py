"""Multi-task fine-tune: shared encoder, mean pooling, one linear layer sliced into heads.

  CUDA_VISIBLE_DEVICES=0 python train_mt.py --model intfloat/multilingual-e5-base --run-id e5b --epochs 4

Writes runs/<id>/{config.json, log.jsonl, dev_logits_ep*.npz, best.pt, metrics.json, test_logits.npz, DONE}.
Selection: best epoch by mean Macro-F1 (type, queue, priority) on dev_tune. Test INPUTS are only
predicted (never scored here); test labels are not on this machine.
"""
import argparse
import json
import math
import os
import random
import re
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from common import HEADS, MAIN, ROOT, DATA, dump, head_metrics, label_space, load_kb, softmax, targets

LOSS_W = {"type": 1.0, "queue": 1.0, "priority": 1.0, "hp": 0.5, "queue_all": 0.3}


class MTModel(nn.Module):
    def __init__(self, name, sizes):
        super().__init__()
        self.enc = AutoModel.from_pretrained(name)
        H = self.enc.config.hidden_size
        self.sizes = sizes
        self.drop = nn.Dropout(0.1)
        self.head = nn.Linear(H, sum(sizes.values()))
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def forward(self, input_ids, attention_mask):
        h = self.enc(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        m = attention_mask.unsqueeze(-1).to(h.dtype)
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1)
        return self.head(self.drop(pooled))

    def split(self, logits):
        out, s = {}, 0
        for h, k in self.sizes.items():
            out[h] = logits[:, s:s + k]
            s += k
        return out


def augment(subject, body, rng):
    """p=0.3: drop subject / first 2 sentences / lowercase / 3% char noise. Mirrors judge-style input variety."""
    subject = subject if isinstance(subject, str) else ""
    r = rng.random()
    if r < 0.10:
        subject = ""
    elif r < 0.17:
        body = " ".join(re.split(r"(?<=[.!?])\s+", body)[:2])
    elif r < 0.23:
        subject, body = subject.lower(), body.lower()
    elif r < 0.30:
        chars = list(body)
        for i in rng.sample(range(len(chars)), k=max(0, int(0.03 * len(chars)))):
            chars[i] = rng.choice("abcdefghijklmnopqrstuvwxyz ")
        body = "".join(chars)
    return (subject + "\n\n" + body).strip()


def batches_by_length(lengths, bs, rng):
    idx = np.argsort(lengths + rng.random(len(lengths)) * 20)  # sorted with jitter
    chunks = [idx[i:i + bs] for i in range(0, len(idx), bs)]
    rng.shuffle(chunks)
    return chunks


@torch.no_grad()
def predict(model, tok, texts, max_len, bs=128, prefix=""):
    model.eval()
    order = np.argsort([len(t) for t in texts])
    out = np.zeros((len(texts), model.head.out_features), np.float32)
    for i in range(0, len(texts), bs):
        ids = order[i:i + bs]
        enc = tok([prefix + texts[j] for j in ids], truncation=True, max_length=max_len,
                  padding=True, return_tensors="pt").to("cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            lg = model(enc["input_ids"], enc["attention_mask"])
        out[ids] = lg.float().cpu().numpy()
    model.train()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--head-lr", type=float, default=1e-3)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--warmup", type=float, default=0.06)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--aug", type=float, default=1.0, help="scale on augmentation probability (0 disables)")
    ap.add_argument("--limit", type=int, default=0, help="smoke test: use first N base rows")
    ap.add_argument("--prefix", default=None, help="text prefix; default 'query: ' for e5 models")
    ap.add_argument("--exclude", default="", help="parquet of base ticket_ids to drop (neighbour-removed protocol)")
    ap.add_argument("--label-smoothing", type=float, default=0.05)
    args = ap.parse_args()
    prefix = args.prefix if args.prefix is not None else ("query: " if "e5" in args.model else "")
    out = f"{ROOT}/runs/{args.run_id}"
    os.makedirs(out, exist_ok=True)
    dump(vars(args) | {"prefix_used": prefix}, f"{out}/config.json")
    torch.manual_seed(args.seed)
    rng_py, rng_np = random.Random(args.seed), np.random.default_rng(args.seed)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    kb, base, dev, is_cal = load_kb()
    if args.limit:
        base = base.iloc[:args.limit].reset_index(drop=True)
    if args.exclude:
        drop = set(pd.read_parquet(args.exclude)["ticket_id"])
        base = base[~base["ticket_id"].isin(drop)].reset_index(drop=True)
        print(f"neighbour-removed protocol: {len(base):,} base rows", flush=True)
    space = label_space(kb)
    sizes = {h: len(space[h]) if h != "hp" else 1 for h in HEADS}
    yb, yd = targets(base, space), targets(dev, space)

    # Class weights: sqrt inverse frequency for type/queue (balanced-ish but gentler than LR's 'balanced').
    cw = {}
    for h in ["type", "queue"]:
        cnt = np.bincount(yb[h][yb[h] >= 0], minlength=sizes[h]).astype(float)
        w = 1 / np.sqrt(np.maximum(cnt, 1))
        cw[h] = torch.tensor(w / (w * cnt).sum() * cnt.sum(), dtype=torch.float32, device="cuda")

    tok = AutoTokenizer.from_pretrained(args.model)
    model = MTModel(args.model, sizes).cuda()
    enc_p = [p for n, p in model.named_parameters() if n.startswith("enc.")]
    head_p = list(model.head.parameters())
    opt = torch.optim.AdamW([{"params": enc_p, "lr": args.lr}, {"params": head_p, "lr": args.head_lr}],
                            weight_decay=0.01, fused=True)
    steps_per_epoch = math.ceil(len(base) / args.bs)
    total = steps_per_epoch * args.epochs
    warm = int(args.warmup * total)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / max(1, warm)) * max(0.0, (total - s) / max(1, total - warm)))

    Y = {h: torch.tensor(yb[h]) for h in HEADS}
    subj, body = base["subject"].tolist(), base["body"].tolist()
    lengths = base["text"].str.len().to_numpy()
    dev_texts = dev["text"].tolist()
    tune = ~is_cal
    best, best_ep, log = -1, -1, open(f"{out}/log.jsonl", "a")
    t0, step = time.time(), 0
    for ep in range(1, args.epochs + 1):
        te = time.time()
        for ids in batches_by_length(lengths, args.bs, rng_np):
            texts = [prefix + (augment(subj[j], body[j], rng_py) if rng_py.random() < 1.0 * args.aug
                               else base["text"].iat[j]) for j in ids]
            # augment() itself only perturbs ~30% of the time; the outer draw just allows --aug 0.
            enc = tok(texts, truncation=True, max_length=args.max_len, padding=True, return_tensors="pt").to("cuda")
            with torch.autocast("cuda", dtype=torch.bfloat16):
                lg = model.split(model(enc["input_ids"], enc["attention_mask"]))
            loss = 0.0
            for h in HEADS:
                y = Y[h][ids].cuda()
                m = y >= 0
                if not m.any():
                    continue
                z = lg[h][m].float()
                if h == "hp":
                    l = F.binary_cross_entropy_with_logits(z[:, 0], y[m].float(),
                                                           pos_weight=torch.tensor(2.2, device="cuda"))
                else:
                    l = F.cross_entropy(z, y[m], weight=cw.get(h), label_smoothing=args.label_smoothing)
                loss = loss + LOSS_W[h] * l
            if not torch.isfinite(loss):
                dump({"error": f"non-finite loss at step {step}"}, f"{out}/FAILED.json")
                raise SystemExit("non-finite loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
            step += 1
            if step % 200 == 0:
                rate = step * args.bs / (time.time() - t0)
                print(f"ep{ep} step {step}/{total} loss {loss.item():.4f} {rate:.0f} samples/s", flush=True)
        # ---- epoch eval on all dev rows ----
        L = predict(model, tok, dev_texts, args.max_len, prefix=prefix)
        D = model.split(torch.from_numpy(L))
        logits = {h: D[h].numpy() for h in HEADS}
        np.savez_compressed(f"{out}/dev_logits_ep{ep}.npz", **logits)
        m = {}
        for h in HEADS:
            z = logits[h]
            P = np.column_stack([1 / (1 + np.exp(z[:, 0])), 1 / (1 + np.exp(-z[:, 0]))]) if h == "hp" else softmax(z)
            m[h] = head_metrics(P[tune], yd[h][tune], h)
        mean = float(np.mean([m[h]["macro_f1"] for h in MAIN]))
        rec = {"epoch": ep, "mean_main_f1": round(mean, 4), "secs": round(time.time() - te),
               "samples_per_s": round(len(base) / (time.time() - te)), **m}
        log.write(json.dumps(rec) + "\n"); log.flush()
        print(json.dumps(rec), flush=True)
        if mean > best:
            best, best_ep = mean, ep
            torch.save(model.state_dict(), f"{out}/best.pt")

    # ---- reload best, predict test inputs (not scored here) ----
    model.load_state_dict(torch.load(f"{out}/best.pt"))
    te_in = pd.read_parquet(f"{DATA}/test_inputs_all.parquet", columns=["ticket_id", "text"])
    L = predict(model, tok, te_in["text"].tolist(), args.max_len, prefix=prefix)
    T = model.split(torch.from_numpy(L))
    np.savez_compressed(f"{out}/test_logits.npz", ticket_id=te_in["ticket_id"].to_numpy(),
                        **{h: T[h].numpy() for h in HEADS})
    tok.save_pretrained(f"{out}/tokenizer")
    dump({"best_epoch": best_ep, "best_mean_main_f1": best, "space": space, "sizes": sizes,
          "secs_total": round(time.time() - t0)}, f"{out}/metrics.json")
    open(f"{out}/DONE", "w").close()
    print("DONE", args.run_id, best_ep, round(best, 4))


if __name__ == "__main__":
    main()
