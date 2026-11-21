"""Presentation figures for the "ticket families" story. Reads existing reports; no model training.

Run from the repo root after findings/analyze.py:  python3 findings/figures.py
Inputs: triage/reports/{metrics,metrics_blend,knn_report}.json, findings/out/{findings.json,map2d.parquet},
        dataset/data/{kb_train,test_inputs_all}.parquet (inputs only; no test labels are read here).
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "triage"))
OUT = os.path.join(ROOT, "findings", "out")
REP = os.path.join(ROOT, "triage", "reports")

INK, MUTED, GRID = "#1f2430", "#6b7280", "#e5e7eb"
C = {"lr": "#4c6ef5", "knn": "#f08c00", "blend": "#2b8a3e", "random": "#adb5bd", "family": "#c92a2a"}
LABEL = {"lr": "TF-IDF + LR", "knn": "1-NN (copy nearest)", "blend": "LR + kNN blend",
         "knn1": "1-NN (copy nearest)"}
plt.rcParams.update({"font.size": 11, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK,
                     "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "axes.axisbelow": True, "figure.dpi": 140})


def load(p):
    with open(p) as f:
        return json.load(f)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


def staircase(lr, bl, knn, fnd):
    stairs = [("exact_kb_twin", "Exact copy\nin training"), ("near_kb_twin", "Reworded copy\n(cos ≥ 0.90)"),
              ("clean", "Clean test\n(no close copy)"), ("family", "Unseen family\n(held out)")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, head in zip(axes, ["type", "queue", "priority"]):
        x = np.arange(len(stairs))
        for j, (m, src) in enumerate((("lr", lr), ("knn", knn), ("blend", bl))):
            vals = []
            for key, _ in stairs:
                if key == "family":
                    mm = "knn1" if m == "knn" else m
                    vals.append(fnd["heldout"]["family_held_out"][head][mm]["accuracy"])
                elif m == "knn":
                    vals.append(src["test"]["full_official_test"][head]["accuracy_by_eval_subset"][key])
                else:
                    vals.append(src["full_official_test"]["by_eval_subset"][key][f"{head}_accuracy"])
            bars = ax.bar(x + (j - 1) * 0.26, vals, 0.26, color=C[m], label=LABEL[m])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=7.5, color=INK)
        ax.set_xticks(x, [s[1] for s in stairs], fontsize=9)
        ax.axvline(2.5, color=MUTED, lw=0.8, ls=":")
        ax.set_title(f"{head}: accuracy", color=INK)
        ax.set_ylim(0, 1.08)
    axes[0].set_ylabel("accuracy")
    axes[0].legend(frameon=False, loc="lower left", fontsize=9)
    fig.suptitle("The leakage staircase: the more novel the ticket, the lower every model scores",
                 color=INK, fontsize=13)
    fig.text(0.5, -0.02, "First three groups: official 20% test split by duplicate type. Last group: 15% of ticket "
             "families held out inside the 80% split (models retrained without them).", ha="center",
             color=MUTED, fontsize=9)
    save(fig, "01_leakage_staircase.png")


def kcurve(knn):
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.2))
    hc = {"type": "#4c6ef5", "queue": "#c92a2a", "priority": "#2b8a3e"}
    for head, r in knn["dev_tune"].items():
        ks = sorted(int(k) for k in r["by_k"])
        a.plot(ks, [r["by_k"][str(k)]["macro_f1"] for k in ks], "o-", color=hc[head], label=head)
        fr = sorted(float(f) for f in r["one_nn_error_curve"])
        b.plot([f * 100 for f in fr], [r["one_nn_error_curve"][str(f)] for f in fr], "o-", color=hc[head], label=head)
    a.set(xscale="log", xlabel="k (neighbours voting)", ylabel="dev Macro-F1",
          title="More neighbours make kNN worse: k = 1 wins")
    a.set_xticks([1, 5, 10, 25, 50], ["1", "5", "10", "25", "50"])
    b.set(xlabel="% of training data available", ylabel="1-NN error (dev)",
          title="1-NN error keeps falling with more data\n(more data = more chance a sibling exists)")
    for ax in (a, b):
        ax.legend(frameon=False)
    save(fig, "02_knn_signature.png")


def heldout(fnd):
    H = fnd["heldout"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), sharey=True)
    for ax, head in zip(axes, ["type", "queue", "priority"]):
        x = np.arange(3)
        for j, (split, col) in enumerate((("random_split", C["random"]), ("family_held_out", C["family"]))):
            vals = [H[split][head][m]["macro_f1"] for m in ("lr", "knn1", "blend")]
            bars = ax.bar(x + (j - 0.5) * 0.36, vals, 0.36, color=col,
                          label="random 15% held out" if j == 0 else "whole families held out")
            for bb, v in zip(bars, vals):
                ax.text(bb.get_x() + bb.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", fontsize=8)
        ax.set_xticks(x, ["TF-IDF + LR", "1-NN", "Blend"])
        ax.set_title(f"{head}: Macro-F1", color=INK)
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Macro-F1")
    axes[0].legend(frameon=False, loc="lower left", fontsize=9)
    fig.suptitle("Holding out whole ticket families costs every model 10-20 points, but kNN keeps its lead",
                 color=INK, fontsize=13)
    save(fig, "03_family_held_out.png")


def family_sizes(fnd):
    h = {int(k): v for k, v in fnd["family_size_hist"].items()}
    ks = sorted(h)
    rows = [k * h[k] for k in ks]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar([str(k) for k in ks], rows, color=C["lr"])
    ax.set(xlabel="family size (tickets that are rewrites of each other)", ylabel="tickets",
           title=f"Most tickets have siblings: family sizes (link = cosine ≥ {fnd['threshold_used']})")
    if len(ks) > 20:
        ax.set_xticks(range(0, len(ks), 2))
    save(fig, "04_family_sizes.png")


def map2d():
    m = pd.read_parquet(os.path.join(OUT, "map2d.parquet"))
    queues = sorted(m["queue"].unique())
    pal = plt.get_cmap("tab10")
    fig, (a, b) = plt.subplots(1, 2, figsize=(15, 6.4))
    for i, q in enumerate(queues):
        s = m[m["queue"] == q]
        a.scatter(s["x"], s["y"], s=4, color=pal(i % 10), alpha=0.6, label=q, linewidths=0)
    a.set_title("Every topic island mixes all departments: queue does not follow topic", color=INK)
    a.legend(markerscale=3, fontsize=7.5, frameon=False, loc="lower left", ncol=2)
    bg = m[~m["in_top"]]
    b.scatter(bg["x"], bg["y"], s=3, color="#ced4da", alpha=0.5, linewidths=0, label="other tickets")
    fams = m[m["in_top"]]
    fam_ids = fams["family"].unique()
    cmap = plt.get_cmap("hsv", len(fam_ids) + 1)
    for i, f in enumerate(fam_ids):
        s = fams[fams["family"] == f]
        b.scatter(s["x"], s["y"], s=7, color=cmap(i), alpha=0.9, linewidths=0)
    b.set_title("Largest families (8+ rewrites) are tiny, tight clumps", color=INK)
    for ax in (a, b):
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
    fig.suptitle("t-SNE map of TF-IDF features (sample of core-queue tickets from the 80% split)", color=INK)
    save(fig, "05_family_map.png")


def urgency_and_agreement(fnd):
    from urgency import urgency
    kb = pd.read_parquet(os.path.join(ROOT, "dataset", "data", "kb_train.parquet"),
                         columns=["text", "type", "priority", "split"])
    d = kb[kb["split"] == "dev"]
    fire = d["text"].map(lambda t: urgency(t)["urgent"])
    rate = fire.groupby(d["priority"]).mean().reindex(["high", "medium", "low"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.2))
    bars = a.bar(rate.index, rate.values, color=["#c92a2a", "#f08c00", "#2b8a3e"])
    for bb, v in zip(bars, rate.values):
        a.text(bb.get_x() + bb.get_width() / 2, v + 0.003, f"{v:.0%}", ha="center")
    a.set(ylabel="share of tickets with urgent wording", ylim=(0, max(0.25, rate.max() * 1.4)),
          title=f"Most high-priority tickets have no urgent wording\n(urgency rule fires on only {rate['high']:.0%} of 'high' dev tickets)")
    ag = fnd["label_agreement"]
    cols = ["type", "queue", "priority", "language"]
    x = np.arange(len(cols))
    w = [ag[c]["within_family"] for c in cols]
    r = [ag[c]["random_pairs"] for c in cols]
    b.bar(x - 0.18, w, 0.36, color=C["family"], label="two tickets from the same family")
    b.bar(x + 0.18, r, 0.36, color=C["random"], label="two random tickets")
    for xi, v in zip(x - 0.18, w):
        b.text(xi, v + 0.01, f"{v:.0%}", ha="center", fontsize=8)
    for xi, v in zip(x + 0.18, r):
        b.text(xi, v + 0.01, f"{v:.0%}", ha="center", fontsize=8)
    b.set_xticks(x, cols)
    b.set(ylim=(0, 1.3), ylabel="labels agree", title="Near-duplicate tickets share labels almost perfectly")
    b.legend(frameon=False, fontsize=9, loc="upper center", ncol=2)
    save(fig, "06_labels_vs_urgency.png")


def sim_hist():
    t = pd.read_parquet(os.path.join(ROOT, "dataset", "data", "test_inputs_all.parquet"),
                        columns=["eval_subset", "max_sim_kb_tfidf"])
    c = t[t["eval_subset"] == "clean"]["max_sim_kb_tfidf"].dropna()
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.hist(c, bins=50, color=C["lr"], alpha=0.85)
    ax.axvline(0.90, color=C["family"], ls="--", lw=1)
    ax.text(0.895, ax.get_ylim()[1] * 0.9, "removed above 0.90 ", ha="right", color=C["family"], fontsize=9)
    ax.set(xlabel="similarity to the closest training ticket (char TF-IDF cosine)", ylabel="clean test tickets",
           title=f"Clean test tickets: similarity to their closest training ticket (median {c.median():.2f})")
    save(fig, "07_clean_test_similarity.png")


def main():
    os.makedirs(OUT, exist_ok=True)
    lr, bl = load(f"{REP}/metrics.json"), load(f"{REP}/metrics_blend.json")
    knn = load(f"{REP}/knn_report.json")
    fpath = os.path.join(OUT, "findings.json")
    fnd = load(fpath) if os.path.exists(fpath) else None
    kcurve(knn)
    sim_hist()
    if fnd:
        staircase(lr, bl, knn, fnd)
        heldout(fnd)
        family_sizes(fnd)
        urgency_and_agreement(fnd)
    if os.path.exists(os.path.join(OUT, "map2d.parquet")):
        map2d()


if __name__ == "__main__":
    main()
