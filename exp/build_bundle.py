"""Assemble the CPU serving bundle for serve/fused_triage.py from a frozen leaderboard + fine-tune run.

  python build_bundle.py --lb lb_final --run e5b_long --far 0.93
Thresholds (HP tau, confidence thresholds, no-precedent similarity) are recomputed on dev_tune with the
exact serving policy. Writes artifacts/bundle/.
"""
import argparse
import json
import os
import shutil

import numpy as np

from common import HEADS, MAIN, ROOT, dump, hp_threshold, label_space, load_kb, targets
from fuse import FUSE_HEADS, load_source
from policy import FAR_W, apply


def conf_threshold(P, y, target):
    m = y >= 0
    conf, ok = P[m].max(1), P[m].argmax(1) == y[m]
    for t in np.arange(0.30, 0.96, 0.05):
        keep = conf >= t
        if keep.any() and ok[keep].mean() >= target:
            return round(float(t), 2), round(float(keep.mean()), 3)
    return 0.95, round(float((conf >= 0.95).mean()), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lb", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--far", type=float, default=0.93)
    ap.add_argument("--type-acc", type=float, default=0.85)
    ap.add_argument("--queue-acc", type=float, default=0.80)
    a = ap.parse_args()
    out = f"{ROOT}/artifacts/bundle"
    os.makedirs(out, exist_ok=True)
    lb = json.load(open(f"{ROOT}/results/{a.lb}.json"))
    kb, base, dev, is_cal = load_kb()
    space = label_space(kb)
    yd, ykb = targets(dev, space), targets(kb, space)
    tune = ~is_cal
    ft_name = f"ft:{a.run}"
    srcs = list(lb["sources"].keys())
    assert ft_name in srcs, f"{ft_name} not in {srcs}"
    Pd = {s: load_source(s, space, len(dev)) for s in srcs}
    simz = np.load(f"{ROOT}/probs/knn_e5-small.npz")
    top1 = {h: simz[f"dev_{h}_top1sim"] for h in FUSE_HEADS}
    D = apply(Pd, top1, lb, ft_name, a.far, lb["gate"])
    hp = hp_threshold(D["hp"][tune][:, 1], yd["hp"][tune])
    ct = {"type": conf_threshold(D["type"][tune], yd["type"][tune], a.type_acc),
          "queue": conf_threshold(D["queue"][tune], yd["queue"][tune], a.queue_acc)}
    ood_sim = 0.89  # judgment call: dev 1st pct is 0.907 (too strict for live tickets, median 0.909); OOD junk median 0.873
    # escalation rate of the classifier rules on dev_tune
    esc = (D["hp"][tune][:, 1] >= hp["tau"]) | (top1["type"][tune] < ood_sim)
    for h in ("type", "queue"):
        esc |= D[h][tune].max(1) < ct[h][0]

    met = json.load(open(f"{ROOT}/runs/{a.run}/metrics.json"))
    sl, s0 = {}, 0
    for h in HEADS:
        sl[h] = [s0, s0 + met["sizes"][h]]
        s0 += met["sizes"][h]
    knn = {"e5s": json.load(open(f"{ROOT}/results/knn_e5-small.json"))["heads"],
           "ft": json.load(open(f"{ROOT}/results/knn_ft_{a.run}.json"))["heads"]}
    src_map = {s: ("tfidf" if s == "tfidf" else "knn_e5-small" if s == "knn_e5-small"
                   else ft_name if s == ft_name else "knn_ft") for s in srcs}
    assert sorted(src_map.values()) == sorted(["tfidf", "knn_e5-small", ft_name, "knn_ft"]), src_map
    cfg_run = json.load(open(f"{ROOT}/runs/{a.run}/config.json"))
    cfg = {"classes": {h: [str(c) for c in space[h]] for h in FUSE_HEADS}, "ft_name": ft_name, "ft_slices": sl,
           "ft_prefix": cfg_run["prefix_used"], "ft_max_len": cfg_run["max_len"], "e5s_max_len": 512,
           "knn": {w: {h: {"k": knn[w][h]["k"], "tau": knn[w][h]["tau"]} for h in FUSE_HEADS} for w in knn},
           "knn_eps": 0.02, "weights": {h: lb["fused"]["weights"][h] for h in FUSE_HEADS}, "src_map": src_map,
           "gate": lb["gate"], "far": a.far, "far_knn_weight": FAR_W, "hp_tau": hp["tau"],
           "conf_threshold": {h: ct[h][0] for h in ct}, "ood_sim": ood_sim,
           "dev_tune": {"hp": hp, "conf_coverage": {h: ct[h][1] for h in ct},
                        "escalation_rate_classifier_rules": round(float(esc.mean()), 4)},
           "built_from": {"lb": a.lb, "run": a.run}}
    dump(cfg, f"{out}/config.json")
    shutil.copy(f"{ROOT}/artifacts/e5-small/model.onnx", f"{out}/e5small.onnx")
    shutil.copy(f"{ROOT}/artifacts/e5-small/tokenizer/tokenizer.json", f"{out}/e5small_tokenizer.json")
    shutil.copy(f"{ROOT}/artifacts/ft_{a.run}/model.onnx", f"{out}/ft.onnx")
    shutil.copy(f"{ROOT}/artifacts/ft_{a.run}/tokenizer/tokenizer.json", f"{out}/ft_tokenizer.json")
    np.save(f"{out}/kb_e5s.npy", np.load(f"{ROOT}/emb/e5-small/kb_emb.npy").astype(np.float16))
    np.save(f"{out}/kb_ft.npy", np.load(f"{ROOT}/emb/ft_{a.run}/kb_emb.npy").astype(np.float16))
    np.savez_compressed(f"{out}/kb_labels.npz", ticket_id=kb["ticket_id"].to_numpy().astype("U9"),
                        **{h: ykb[h].astype(np.int16) for h in HEADS4})
    print(json.dumps({k: cfg[k] for k in ("hp_tau", "conf_threshold", "ood_sim", "dev_tune")}, indent=1))


HEADS4 = ["type", "queue", "priority", "hp"]

if __name__ == "__main__":
    main()
