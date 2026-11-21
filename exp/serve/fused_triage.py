"""CPU-only fused triage: TF-IDF + kNN (frozen e5-small) + fine-tuned e5-base (head + kNN on its embeddings).

Same output shape as triage.model.TriageModel.predict, plus "evidence" (kNN top-1 similarity and regime).
Deps: numpy, onnxruntime, tokenizers, joblib/scikit-learn (for the TF-IDF part). Python >= 3.9.

  from fused_triage import FusedTriage
  ft = FusedTriage("bundle/", tfidf_path="triage/models/triage.joblib")
  ft.predict("VPN down", "Nobody can connect since 8am ...")
"""
import json
import os
import sys
import time

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

HEADS = ["type", "queue", "priority", "hp"]
MAIN = ["type", "queue", "priority"]
TFIDF_HEAD = {"type": "type", "queue": "queue", "priority": "priority", "hp": "hp_incident"}


def _softmax(z):
    z = z - z.max(-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(-1, keepdims=True)


class _Encoder:
    def __init__(self, onnx_path, tok_path, max_len, prefix, threads):
        so = ort.SessionOptions()
        so.intra_op_num_threads, so.inter_op_num_threads = threads, 1
        self.sess = ort.InferenceSession(onnx_path, so, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(tok_path)
        self.tok.enable_truncation(max_length=max_len)
        self.prefix = prefix

    def __call__(self, text):
        e = self.tok.encode(self.prefix + text)
        ids = np.array([e.ids], dtype=np.int64)
        return self.sess.run(None, {"input_ids": ids, "attention_mask": np.ones_like(ids)})


class FusedTriage:
    def __init__(self, bundle, tfidf_path, threads=4):
        cfg = json.load(open(os.path.join(bundle, "config.json")))
        self.cfg = cfg
        here = os.path.dirname(os.path.abspath(tfidf_path))
        sys.path.insert(0, os.path.dirname(here))  # triage/ package dir
        from model import TriageModel  # noqa: E402  (triage/model.py)
        from textprep import build_text  # noqa: E402
        self.build_text = build_text
        self.tfidf = TriageModel.load(tfidf_path)
        self.e5s = _Encoder(os.path.join(bundle, "e5small.onnx"), os.path.join(bundle, "e5small_tokenizer.json"),
                            cfg["e5s_max_len"], "query: ", threads)
        self.ft = _Encoder(os.path.join(bundle, "ft.onnx"), os.path.join(bundle, "ft_tokenizer.json"),
                           cfg["ft_max_len"], cfg["ft_prefix"], threads)
        self.idx = {"e5s": np.load(os.path.join(bundle, "kb_e5s.npy")).astype(np.float32),
                    "ft": np.load(os.path.join(bundle, "kb_ft.npy")).astype(np.float32)}
        lab = np.load(os.path.join(bundle, "kb_labels.npz"))
        self.labels = {h: lab[h].astype(np.int64) for h in HEADS}
        self.ok = {h: self.labels[h] >= 0 for h in HEADS}
        self.ticket_ids = lab["ticket_id"]
        self.classes = cfg["classes"]

    def _knn(self, s_all, which, h):
        """s_all: similarities of the query to every kb row (computed once per index)."""
        y = self.labels[h]
        ok = self.ok[h]
        s = s_all[ok]
        kcfg = self.cfg["knn"][which][h]
        k, tau, eps = kcfg["k"], kcfg["tau"], self.cfg["knn_eps"]
        top = np.argpartition(-s, k)[:k] if k < len(s) else np.arange(len(s))
        top = top[np.argsort(-s[top])]
        w = np.exp((s[top] - s[top[0]]) / tau)
        n = len(self.classes[h])
        P = np.bincount(y[ok][top], weights=w, minlength=n)
        P = P / P.sum()
        return (1 - eps) * P + eps / n, float(s[top[0]]), self.ticket_ids[ok][top[0]]

    def predict(self, subject, body):
        t0 = time.perf_counter()
        text = self.build_text(subject, body)
        X = self.tfidf.transform([text])
        src = {"tfidf": {}}
        for h in HEADS:
            cls_t = [str(c) for c in self.tfidf.classes(TFIDF_HEAD[h])]
            p = self.tfidf.proba(X, TFIDF_HEAD[h])[0]
            src["tfidf"][h] = p[[cls_t.index(str(c)) for c in self.classes[h]]]
        t1 = time.perf_counter()
        q_e5s = self.e5s(text)[0][0]
        emb_ft, logits = self.ft(text)
        q_ft, L = emb_ft[0], logits[0]
        t2 = time.perf_counter()
        sl = self.cfg["ft_slices"]
        src[self.cfg["ft_name"]] = {h: _softmax(L[sl[h][0]:sl[h][1]]) for h in MAIN}
        p1 = 1 / (1 + np.exp(-L[sl["hp"][0]]))
        src[self.cfg["ft_name"]]["hp"] = np.array([1 - p1, p1])
        src["knn_e5-small"], src["knn_ft"], top1, nn_id = {}, {}, {}, {}
        s_e5s, s_ft = self.idx["e5s"] @ q_e5s, self.idx["ft"] @ q_ft
        for h in HEADS:
            src["knn_e5-small"][h], top1[h], nn_id[h] = self._knn(s_e5s, "e5s", h)
            src["knn_ft"][h], _, _ = self._knn(s_ft, "ft", h)
        out, gate = {}, self.cfg["gate"]
        for h in HEADS:
            regime = "far" if top1[h] < self.cfg["far"] else ("near" if top1[h] >= gate else "novel")
            if regime == "far":
                if h == "hp":
                    P = src[self.cfg["ft_name"]][h]
                else:
                    w = self.cfg["far_knn_weight"]
                    P = _softmax(w * np.log(np.clip(src["knn_ft"][h], 1e-9, 1))
                                 + (1 - w) * np.log(np.clip(src[self.cfg["ft_name"]][h], 1e-9, 1)))
            else:
                W = self.cfg["weights"][h][regime]
                z = sum(W[s] * np.log(np.clip(src[self.cfg["src_map"][s]][h], 1e-9, 1)) for s in W)
                P = _softmax(z)
            out[h] = (P, regime)
        res = {}
        for h in MAIN:
            P, regime = out[h]
            i = int(P.argmax())
            res[h] = {"label": self.classes[h][i], "conf": float(P[i]), "regime": regime,
                      "probs": {c: round(float(v), 4) for c, v in sorted(zip(self.classes[h], P), key=lambda z: -z[1])}}
        p_hp = float(out["hp"][0][1])
        res["hp_incident"] = {"prob": p_hp, "flag": p_hp >= self.cfg["hp_tau"]}
        res["evidence"] = {"knn_top1_sim": round(top1["type"], 4), "knn_top1_ticket": str(nn_id["type"]),
                           "regime": out["type"][1]}
        reasons = []
        if res["hp_incident"]["flag"]:
            reasons.append(f"Likely high-priority Incident (p={p_hp:.2f} >= {self.cfg['hp_tau']:.2f})")
        for h in ("type", "queue"):
            th = self.cfg["conf_threshold"][h]
            if res[h]["conf"] < th:
                reasons.append(f"Low {h} confidence ({res[h]['conf']:.2f} < {th:.2f})")
        if top1["type"] < self.cfg["ood_sim"]:
            reasons.append(f"No similar past ticket (top-1 similarity {top1['type']:.2f} < {self.cfg['ood_sim']:.2f})")
        res["gate_hints"] = {"escalate": bool(reasons), "reasons": reasons}
        t3 = time.perf_counter()
        res["latency_ms"] = {"tfidf": round((t1 - t0) * 1000, 1), "encoders": round((t2 - t1) * 1000, 1),
                             "knn_fuse": round((t3 - t2) * 1000, 1), "total": round((t3 - t0) * 1000, 1)}
        return res
