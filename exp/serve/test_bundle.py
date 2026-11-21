"""Box-side CPU test of the serving bundle: latency + agreement with the GPU policy path on the novel tickets."""
import json, sys, time, warnings
warnings.simplefilter("ignore")
import numpy as np
sys.path.insert(0, "serve")
from fused_triage import FusedTriage
ROOT = "/home/nathan/sentineldesk-exp"
ft = FusedTriage(f"{ROOT}/artifacts/bundle", f"{ROOT}/triage/models/triage.joblib", threads=4)
rows = [json.loads(l) for l in open("robust/novel_tickets.jsonl")]
lat, res = [], []
for r in rows:
    t0 = time.perf_counter(); o = ft.predict(r["subject"], r["body"]); lat.append((time.perf_counter() - t0) * 1000); res.append(o)
ins = [i for i, r in enumerate(rows) if not r["ood"]]; hp = [i for i, r in enumerate(rows) if r["hp_expected"]]; ood = [i for i, r in enumerate(rows) if r["ood"]]
print("latency ms p50 %.0f p95 %.0f max %.0f" % tuple(np.percentile(lat, [50, 95, 100])))
print("type acc %.2f  queue in-set %.2f  priority in-set %.2f" % (
    np.mean([res[i]["type"]["label"] == rows[i]["type"] for i in ins]),
    np.mean([res[i]["queue"]["label"] in rows[i]["queue_ok"] for i in ins]),
    np.mean([res[i]["priority"]["label"] in rows[i]["priority_ok"] for i in ins])))
print("outages flagged %d/%d; false flags %d/%d" % (sum(res[i]["hp_incident"]["flag"] for i in hp), len(hp),
      sum(res[i]["hp_incident"]["flag"] for i in ins if i not in hp), len(ins) - len(hp)))
print("escalated: in-scope %.2f  OOD %.2f" % (np.mean([res[i]["gate_hints"]["escalate"] for i in ins]), np.mean([res[i]["gate_hints"]["escalate"] for i in ood])))
print(json.dumps(res[0], indent=1)[:1500])
