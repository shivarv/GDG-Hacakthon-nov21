"""Export an encoder to ONNX (fp32 + int8 dynamic quant) and benchmark single-ticket CPU latency.

  python export_onnx.py --frozen intfloat/multilingual-e5-small --name e5-small    # outputs: emb
  python export_onnx.py --run-id e5s_s13 --name ft_e5s_s13                         # outputs: emb, logits

Checks: fp32 vs torch, int8 vs fp32 cosine on 300 dev texts. Bench: 2 threads pinned to 2 cores.
Writes artifacts/<name>/{model.onnx, model.int8.onnx, tokenizer/, meta.json, bench.json}.
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from common import DATA, ROOT, dump


class Wrap(torch.nn.Module):
    def __init__(self, enc, head=None):
        super().__init__()
        self.enc, self.head = enc, head

    def forward(self, input_ids, attention_mask):
        h = self.enc(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        m = attention_mask.unsqueeze(-1).to(h.dtype)
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1)
        emb = F.normalize(pooled, dim=-1)
        if self.head is None:
            return emb
        return emb, self.head(pooled)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen")
    ap.add_argument("--run-id")
    ap.add_argument("--name", required=True)
    ap.add_argument("--max-len", type=int, default=512)
    a = ap.parse_args()
    out = f"{ROOT}/artifacts/{a.name}"
    os.makedirs(out, exist_ok=True)
    if a.frozen:
        tok = AutoTokenizer.from_pretrained(a.frozen)
        model = Wrap(AutoModel.from_pretrained(a.frozen)).eval()
        prefix, outputs, meta = "query: ", ["emb"], {"model": a.frozen}
    else:
        from train_mt import MTModel
        run = f"{ROOT}/runs/{a.run_id}"
        cfg, met = json.load(open(f"{run}/config.json")), json.load(open(f"{run}/metrics.json"))
        mt = MTModel(cfg["model"], met["sizes"])
        mt.load_state_dict(torch.load(f"{run}/best.pt", map_location="cpu"))
        tok = AutoTokenizer.from_pretrained(f"{run}/tokenizer")
        model = Wrap(mt.enc, mt.head).eval()
        prefix, outputs = cfg["prefix_used"], ["emb", "logits"]
        meta = {"model": cfg["model"], "run_id": a.run_id, "sizes": met["sizes"], "space": met["space"]}
        a.max_len = cfg["max_len"]
    tok.save_pretrained(f"{out}/tokenizer")
    dummy = tok(["query: hello world"] * 2, return_tensors="pt", padding=True)
    dyn = {"input_ids": {0: "b", 1: "t"}, "attention_mask": {0: "b", 1: "t"}, **{o: {0: "b"} for o in outputs}}
    torch.onnx.export(model, (dummy["input_ids"], dummy["attention_mask"]), f"{out}/model.onnx",
                      input_names=["input_ids", "attention_mask"], output_names=outputs,
                      dynamic_axes=dyn, opset_version=17, dynamo=False)
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(f"{out}/model.onnx", f"{out}/model.int8.onnx", weight_type=QuantType.QInt8)
    import onnxruntime as ort

    kb = pd.read_parquet(f"{DATA}/kb_train.parquet", columns=["text", "split"])
    texts = [prefix + t for t in kb.loc[kb.split == "dev", "text"].iloc[:300]]
    res = {"max_len": a.max_len, "prefix": prefix, "outputs": outputs,
           "size_mb": {f: round(os.path.getsize(f"{out}/{f}") / 1e6) for f in ["model.onnx", "model.int8.onnx"]}}
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads = 2, 1
    sess = {k: ort.InferenceSession(f"{out}/{f}", so, providers=["CPUExecutionProvider"])
            for k, f in (("fp32", "model.onnx"), ("int8", "model.int8.onnx"))}
    embs = {k: [] for k in sess}
    logits = {k: [] for k in sess}
    lat = {k: [] for k in sess}
    for t in texts:
        enc = tok([t], truncation=True, max_length=a.max_len, return_tensors="np")
        feed = {"input_ids": enc["input_ids"].astype(np.int64), "attention_mask": enc["attention_mask"].astype(np.int64)}
        for k, s in sess.items():
            t0 = time.perf_counter()
            o = s.run(None, feed)
            lat[k].append((time.perf_counter() - t0) * 1000)
            embs[k].append(o[0][0])
            if len(o) > 1:
                logits[k].append(o[1][0])
    with torch.no_grad():
        enc = tok(texts[:32], truncation=True, max_length=a.max_len, padding=True, return_tensors="pt")
        ref = model(enc["input_ids"], enc["attention_mask"])
        ref = (ref[0] if isinstance(ref, tuple) else ref).numpy()
    E32, E8 = np.array(embs["fp32"]), np.array(embs["int8"])
    res["torch_vs_fp32_maxdiff"] = float(np.abs(ref - E32[:32]).max())
    res["int8_vs_fp32_cos"] = {"mean": float((E32 * E8).sum(1).mean()), "min": float((E32 * E8).sum(1).min())}
    if logits["fp32"]:
        L32, L8 = np.array(logits["fp32"]), np.array(logits["int8"])
        agree, s0 = {}, 0
        for h, k in meta["sizes"].items():
            a32, a8 = L32[:, s0:s0 + k], L8[:, s0:s0 + k]
            agree[h] = float(((a32 > 0) == (a8 > 0)).mean() if k == 1 else (a32.argmax(1) == a8.argmax(1)).mean())
            s0 += k
        res["int8_vs_fp32_argmax_agree"] = agree
    res["latency_ms_2threads"] = {k: {"p50": round(float(np.percentile(v, 50)), 1),
                                      "p95": round(float(np.percentile(v, 95)), 1)} for k, v in lat.items()}
    dump(meta | res, f"{out}/meta.json")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
