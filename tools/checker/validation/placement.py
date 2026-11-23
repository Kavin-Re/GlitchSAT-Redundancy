#!/usr/bin/env python3
"""Placed layouts: the geometric verdict of the placement stage vs the shot search of ext/shots.

For the six placed designs of ext/shots and every radius sampled there (rule "centre", free aim on a 0.1 um grid,
bit-flip, 6 cycles), the checker's verdict for the redundant copies at that radius is compared with the recorded
minimum number of shots (SIMULATED by ext/shots):
   truth REMOVED  = 1 shot suffices      truth WEAKENED = fewer shots than at radius 0 (but more than 1)
"""
import copy
import json
import os
import sys

from common import ROOT, RESULTS, prf, prf_text
from survival import gnet, intent_rtl, paths
from survival import stage_netlist as SN
from survival import stage_place as SP


def main():
    sp = paths.optional("shotmodel.paths")
    with open(os.path.join(paths.ext_root(), "shots", "results", "shots_results.json")) as f:
        shots = json.load(f)
    rows, per = [], {}
    for did, (top, def_rel, nl_rel, note) in sp.DESIGNS.items():
        rtl = os.path.join(ROOT, "rtl", top + ".v")
        cms = [c for c in intent_rtl.scan([rtl]) if c.kind == "redundant_copies" and c.intent.get("module") == top]
        ref = gnet.load(os.path.join(ROOT, "reference", "spike_netlists", top + ".json"), top)
        for cm in cms:
            SN.check(cm, ref, "ref", True)
        g = gnet.load(os.path.join(ROOT, nl_rel), top)
        pl = SP.Placement(os.path.join(ROOT, def_rel))
        curve = next(c for c in shots["curves"] if (c["design"], c["rule"], c["aim"], c["effect"], c["targets"], c["goal"], c["T"], c["clk"])
                     == (did, "centre", "grid", "flip", "all", "word", 6, "ignore"))
        base = next(s["min"] for s in curve["steps"] if s["r_from"] == 0.0)
        r0 = SP.check(copy.deepcopy(cms[0]), g, pl, "placed", 0.0)
        per[did] = dict(copies=cms[0].intent["copies"], r_pair_um=r0.measured["r_pair_um"], r_all_um=r0.measured["r_all_um"],
                        shots_at_r0=base, note=note)
        for radius, mn, _ in curve["samples"]:
            if mn is None:
                continue
            r = SP.check(copy.deepcopy(cms[0]), g, pl, "placed", radius)
            truth = "REMOVED" if (mn == 1 and base > 1) else ("WEAKENED" if mn < base else "SURVIVED")
            rows.append(dict(design=did, radius_um=radius, min_shots=mn, shots_at_r0=base, truth=truth, verdict=r.verdict))
    def conf(sel):
        rs = [r for r in rows if sel(r)]
        tp = sum(1 for r in rs if r["verdict"] != "SURVIVED" and r["truth"] != "SURVIVED")
        fp = sum(1 for r in rs if r["verdict"] != "SURVIVED" and r["truth"] == "SURVIVED")
        fn = sum(1 for r in rs if r["verdict"] == "SURVIVED" and r["truth"] != "SURVIVED")
        exact = sum(1 for r in rs if r["verdict"] == r["truth"])
        return dict(points=len(rs), exact_class=exact, **prf(tp, fp, fn), text=prf_text(prf(tp, fp, fn)))
    summary = dict(v2_layouts=conf(lambda r: r["design"] != "v1"),
                   v1_control=dict(points=sum(1 for r in rows if r["design"] == "v1"),
                                   note="V1 needs 1 shot at every radius (single voter net): placement cannot weaken it; the checker "
                                        "still reports when its two copies are within one spot",
                                   flagged=sum(1 for r in rows if r["design"] == "v1" and r["verdict"] != "SURVIVED")),
                   per_design=per)
    with open(os.path.join(RESULTS, "placement.json"), "w") as f:
        json.dump(dict(schema="glitchsat-survival-validation/placement/1", rows=rows, summary=summary,
                       label="verdicts: MEASURED geometry (DEF); truth: SIMULATED shot search recorded by ext/shots"), f, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
