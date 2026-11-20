"""Compare the product's counting rules with research/c3/rep/rep_results.csv on the apt-0.33 REP netlists.
usage: python3 -I rep_compare.py NETDIR REP_CSV OUT_CSV   (needs faultbound_wt importable)"""
import csv, sys, os, hashlib
from faultbound_wt import runner
from faultbound_wt.config import Threat, validate
net, rep, out = sys.argv[1:4]
rows = {r["netlist"]: r for r in csv.DictReader(open(rep))}
res = []
bad = 0
for name in sorted(rows):
    p = os.path.join(net, name + ".json")
    if not os.path.isfile(p):
        continue
    top = name.split("_")[0]
    sha = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    vals = {}
    for rule in ("stem", "fanout_pins", "fanout_gates"):
        th = Threat(max_flips=4, cycles=6, count_rule=rule); validate(th)
        r = runner.analyze(p, th, top=top)
        vals[rule] = (r.get("min_cost", r.get("min_faults")) if r["verdict"] == runner.ATTACK else ">4")
    R = rows[name]
    ok = (str(vals["stem"]) == R["rep_unit_cli"] and str(vals["fanout_pins"]) == R["rep_fanout_pins"] and str(vals["fanout_gates"]) == R["rep_fanout_gates"] and sha == R["sha16"])
    bad += not ok
    res.append([name, sha, R["sha16"], r["provenance"]["netlist_stats"]["gates"], R["gates"], vals["stem"], R["rep_unit_cli"], vals["fanout_pins"], R["rep_fanout_pins"], vals["fanout_gates"], R["rep_fanout_gates"], ok])
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow("netlist,sha16_here,sha16_rep,gates_here,gates_rep,unit_here,unit_rep,fanout_pins_here,fanout_pins_rep,fanout_gates_here,fanout_gates_rep,agree".split(",")); w.writerows(res)
print(f"{len(res)} netlists compared, {len(res)-bad} agree on sha16 and all three costs, {bad} differ")
