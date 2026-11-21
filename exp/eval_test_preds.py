"""Mac-side, ONE SHOT: score exp/results/test_preds.npz against the test labels.
Refuses to run without exp/results/decision.json, and refuses to overwrite exp/results/test_metrics.json.

  python3 exp/eval_test_preds.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

R = "exp/results"
if not os.path.exists(f"{R}/decision.json"):
    sys.exit("decision.json missing: freeze the decision before touching test labels")
if os.path.exists(f"{R}/test_metrics.json"):
    sys.exit("test_metrics.json exists: the test set has already been used once")

z = np.load(f"{R}/test_preds.npz", allow_pickle=False)
classes = json.loads(str(z["classes_json"]))
ids = z["ticket_id"]
lab = pd.read_parquet("dataset/data/test_labels_all.parquet").set_index("ticket_id").loc[ids].reset_index()
sub = pd.read_parquet("dataset/data/test_inputs_all.parquet", columns=["ticket_id", "eval_subset"]).set_index("ticket_id").loc[ids]
systems = sorted({k.split("|")[0] for k in z.files if k.endswith("|type")})
typed = lab["type"].notna().to_numpy()
hp_true = ((lab["type"] == "Incident") & (lab["priority"] == "high")).to_numpy()
out = {}
for part, mask in (("clean", (sub["eval_subset"] == "clean").to_numpy()), ("all_official", np.ones(len(ids), bool))):
    out[part] = {"n": int(mask.sum())}
    for s in systems:
        r = {}
        for h, col, m in (("type", "type", typed), ("queue", "queue", lab["queue_core"].to_numpy()),
                          ("priority", "priority", np.ones(len(ids), bool))):
            mm = mask & m
            pred = np.array(classes[h])[z[f"{s}|{h}"].argmax(1)]
            r[f"{h}_macro_f1"] = round(float(f1_score(lab[col][mm], pred[mm], average="macro")), 4)
        r["mean_main_f1"] = round(float(np.mean([r["type_macro_f1"], r["queue_macro_f1"], r["priority_macro_f1"]])), 4)
        flag = z[f"{s}|hp_flag"]
        pos = mask & typed & hp_true
        r["hp_gate_recall"] = round(float(flag[pos].mean()), 4)
        r["hp_flag_rate"] = round(float(flag[mask].mean()), 4)
        pt = np.array(classes["type"])[z[f"{s}|type"].argmax(1)]
        pp = np.array(classes["priority"])[z[f"{s}|priority"].argmax(1)]
        r["hp_classifier_recall"] = round(float(((pt == "Incident") & (pp == "high"))[pos].mean()), 4)
        out[part][s] = r
json.dump(out, open(f"{R}/test_metrics.json", "w"), indent=2)
for part in out:
    print(f"== {part} (n={out[part]['n']:,})")
    for s in systems:
        print(f"  {s:14s}", out[part][s])
