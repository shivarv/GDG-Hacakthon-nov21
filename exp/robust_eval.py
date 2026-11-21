"""Score each source and the fused system on the hand-written novel tickets (reporting only; never tuned on).

  python robust_eval.py --lb lb_v3
Uses the sources, fusion weights and HP thresholds stored in results/<lb>.json.
"""
import argparse
import json

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

from common import DATA, MAIN, ROOT, dump, label_space, softmax, targets
from probe_knn import topk, vote
from textprep import build_text

HEADS4 = ["type", "queue", "priority", "hp"]


@torch.no_grad()
def enc_pool(enc, tok, texts, max_len):
    b = tok(texts, truncation=True, max_length=max_len, padding=True, return_tensors="pt").to("cuda")
    h = enc(input_ids=b["input_ids"], attention_mask=b["attention_mask"]).last_hidden_state
    m = b["attention_mask"].unsqueeze(-1).to(h.dtype)
    return (h * m).sum(1) / m.sum(1).clamp(min=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lb", required=True)
    a = ap.parse_args()
    lb = json.load(open(f"{ROOT}/results/{a.lb}.json"))
    sources = list(lb["sources"].keys())
    rows = [json.loads(l) for l in open(f"{ROOT}/code/robust/novel_tickets.jsonl")]
    texts = [build_text(r["subject"], r["body"]) for r in rows]
    kb = pd.read_parquet(f"{DATA}/kb_train.parquet", columns=["ticket_id", "text", "type", "queue", "queue_core",
                                                              "priority", "split"])
    space = label_space(kb)
    P = {}
    # tfidf
    z = np.load(f"{ROOT}/probs/tfidf_novel.npz")
    P["tfidf"] = {h: z[f"novel_{h}"][:, [list(z[f"{h}_classes"]).index(str(c)) for c in space[h]]] for h in HEADS4}
    # kNN on frozen e5-small (index = base+dev, as at serving time)
    tok = AutoTokenizer.from_pretrained("intfloat/multilingual-e5-small")
    enc = AutoModel.from_pretrained("intfloat/multilingual-e5-small").cuda().eval()
    q = F.normalize(enc_pool(enc, tok, ["query: " + t for t in texts], 512), dim=-1)
    E = torch.from_numpy(np.load(f"{ROOT}/emb/e5-small/kb_emb.npy")).cuda()
    kcfg = json.load(open(f"{ROOT}/results/knn_e5-small.json"))["heads"]
    ykb = targets(kb, space)
    P["knn_e5-small"], top1 = {}, {}
    for h in HEADS4:
        lab = torch.from_numpy(ykb[h]).cuda()
        ok = lab >= 0
        S, I = topk(q, E[ok])
        P["knn_e5-small"][h] = vote(S, lab[ok][I], kcfg[h]["k"], kcfg[h]["tau"], len(space[h])).cpu().numpy()
        top1[h] = S[:, 0].cpu().numpy()
    # fine-tuned runs
    from train_mt import MTModel
    for s in sources:
        if not s.startswith("ft:"):
            continue
        rid = s[3:]
        cfg = json.load(open(f"{ROOT}/runs/{rid}/config.json"))
        met = json.load(open(f"{ROOT}/runs/{rid}/metrics.json"))
        m = MTModel(cfg["model"], met["sizes"]).cuda().eval()
        m.load_state_dict(torch.load(f"{ROOT}/runs/{rid}/best.pt"))
        t2 = AutoTokenizer.from_pretrained(f"{ROOT}/runs/{rid}/tokenizer")
        with torch.no_grad():
            b = t2([cfg["prefix_used"] + t for t in texts], truncation=True, max_length=cfg["max_len"],
                   padding=True, return_tensors="pt").to("cuda")
            L = m.split(m(b["input_ids"], b["attention_mask"]).float().cpu())
        P[s] = {h: softmax(L[h].numpy()) for h in MAIN}
        p1 = 1 / (1 + np.exp(-L["hp"][:, 0].numpy()))
        P[s]["hp"] = np.column_stack([1 - p1, p1])
    # kNN on fine-tuned embeddings (knn_ft_<rid>): query with the fine-tuned encoder, index = base+dev
    for s in sources:
        if not s.startswith("knn_ft_"):
            continue
        rid = s[len("knn_ft_"):]
        cfg = json.load(open(f"{ROOT}/runs/{rid}/config.json"))
        met = json.load(open(f"{ROOT}/runs/{rid}/metrics.json"))
        m = MTModel(cfg["model"], met["sizes"]).cuda().eval()
        m.load_state_dict(torch.load(f"{ROOT}/runs/{rid}/best.pt"))
        t2 = AutoTokenizer.from_pretrained(f"{ROOT}/runs/{rid}/tokenizer")
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            qf = F.normalize(enc_pool(m.enc, t2, [cfg["prefix_used"] + t for t in texts], cfg["max_len"]).float(), dim=-1)
        Ef = torch.from_numpy(np.load(f"{ROOT}/emb/ft_{rid}/kb_emb.npy")).cuda()
        kc = json.load(open(f"{ROOT}/results/knn_ft_{rid}.json"))["heads"]
        P[s] = {}
        for h in HEADS4:
            lab = torch.from_numpy(ykb[h]).cuda()
            ok = lab >= 0
            S, I = topk(qf, Ef[ok])
            P[s][h] = vote(S, lab[ok][I], kc[h]["k"], kc[h]["tau"], len(space[h])).cpu().numpy()
    # fused
    W = lb["fused"]["weights"]
    fused = {}
    for h in HEADS4:
        near = top1[h] >= lb["gate"]
        out = np.zeros_like(P[sources[0]][h])
        for regime, msk in (("near", near), ("novel", ~near)):
            w = W[h][regime]
            zz = sum(w[s] * np.log(np.clip(P[s][h][msk], 1e-9, 1)) for s in sources)
            out[msk] = softmax(zz) if msk.any() else out[msk]
        fused[h] = out
    P["FUSED"] = fused
    np.savez_compressed(f"{ROOT}/probs/novel_{a.lb}.npz",
                        **{f"{src}|{h}": v for src, d in P.items() for h, v in d.items()},
                        **{f"top1|{h}": v for h, v in top1.items()})
    taus = {s: lb["sources"][s]["hp_gate_dedicated"]["tau"] for s in sources} | {"FUSED": lb["fused"]["hp_gate_dedicated"]["tau"]}

    inscope = [i for i, r in enumerate(rows) if not r["ood"]]
    hp_rows = [i for i, r in enumerate(rows) if r["hp_expected"]]
    ood = [i for i, r in enumerate(rows) if r["ood"]]
    rep = {"n": len(rows), "top1_sim_e5": {"inscope_median": float(np.median(top1["type"][inscope])),
                                           "ood_median": float(np.median(top1["type"][ood]))}, "systems": {}}
    for name, Ps in P.items():
        lab = {h: [space[h][j] for j in Ps[h].argmax(1)] for h in MAIN}
        r = {"type_acc": float(np.mean([lab["type"][i] == rows[i]["type"] for i in inscope])),
             "queue_in_set": float(np.mean([lab["queue"][i] in rows[i]["queue_ok"] for i in inscope])),
             "priority_in_set": float(np.mean([lab["priority"][i] in rows[i]["priority_ok"] for i in inscope])),
             "hp_flag_recall": float(np.mean([Ps["hp"][i, 1] >= taus[name] for i in hp_rows])),
             "hp_flag_rate_nonhp_inscope": float(np.mean([Ps["hp"][i, 1] >= taus[name] for i in inscope
                                                           if not rows[i]["hp_expected"]])),
             "ood_mean_type_conf": float(np.mean([Ps["type"][i].max() for i in ood]))}
        rep["systems"][name] = {k: round(v, 3) for k, v in r.items()}
        print(f"{name:16s} " + "  ".join(f"{k}={v:.2f}" for k, v in r.items()), flush=True)
    print("e5 top-1 sim to kb: in-scope median", round(rep["top1_sim_e5"]["inscope_median"], 3),
          " OOD median", round(rep["top1_sim_e5"]["ood_median"], 3))
    dump(rep, f"{ROOT}/results/robust_{a.lb}.json")


if __name__ == "__main__":
    main()
