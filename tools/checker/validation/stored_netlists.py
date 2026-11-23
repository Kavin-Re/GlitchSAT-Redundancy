#!/usr/bin/env python3
"""Every V1/V2-family netlist stored in the repository (32 distinct files, the list ext/surface validates on):
checker verdict vs the minimum number of flips MEASURED by ext/surface (results/lint_validation.json).

Reference for each design: its RTL (rtl/*.v or research/c6/p01/controls/*.v) elaborated as written with Yosys
(`proc; flatten; techmap`, no optimisation). Needs Yosys; without it the script stops and says so.
"""
import copy
import glob
import json
import os
import re
import sys
import tempfile

from common import ROOT, RESULTS, prf, prf_text
from survival import gnet, intent_rtl, margin, paths, pipeline
from survival import stage_netlist as SN

import lint_validation as LV  # noqa: E402  (ext/surface: the list of stored netlists)


def rtl_of(top):
    for pat in ("rtl/*.v", "research/c6/p01/controls/*.v", "research/**/*.v"):
        for p in sorted(glob.glob(os.path.join(ROOT, pat), recursive=True)):
            try:
                t = open(p, errors="replace").read()
            except OSError:
                continue
            if re.search(r"\bmodule\s+" + re.escape(top) + r"\b", t) and "always" in t and "sky130" not in t:
                return p
    return None


def main():
    if not paths.tool("yosys"):
        print("Yosys not available: this validation is NOT RUN", file=sys.stderr)
        return 2
    with open(os.path.join(paths.ext_root(), "surface", "results", "lint_validation.json")) as f:
        measured = {r["sha16"]: r for r in json.load(f)["rows"]}
    work = tempfile.mkdtemp(prefix="gs-stored-")
    refs, rows = {}, []
    for h, (path, top, copies) in sorted(LV.find_netlists(ROOT).items(), key=lambda kv: (kv[1][1], kv[1][0])):
        if top not in refs:
            rtl = rtl_of(top)
            ref = None
            if rtl:
                out = os.path.join(work, top + "_ref.json")
                ok, msg = pipeline.run_yosys([rtl], top, pipeline.RTL_REFERENCE_FLOW, out)
                if ok:
                    g0 = gnet.load(out, top)
                    cms = [c for c in intent_rtl.scan([rtl]) if c.intent.get("module") == top]
                    for cm in cms:
                        SN.check(cm, g0, "rtl", True)
                    m0 = margin.measure(out, top, {}, kmax=3, cycles=6, timeout_s=300)
                    ref = dict(rtl=os.path.relpath(rtl, ROOT), g=g0, cms=cms, min=m0.get("min_faults"))
            refs[top] = ref
        ref = refs[top]
        row = dict(netlist=path, top=top, sha16=h[:16])
        m = measured.get(h[:16], {})
        row.update(measured_min=m.get("measured_min"), recorded_min=m.get("recorded_min"), lint=m.get("lint_verdict"))
        if ref is None:
            row["error"] = "no RTL found for this top module"
            rows.append(row)
            continue
        row.update(rtl=ref["rtl"], reference_min=ref["min"])
        try:
            g = gnet.load(os.path.join(ROOT, path), top)
        except gnet.NetlistError as e:
            row["error"] = str(e)[:160]
            rows.append(row)
            continue
        SN.copy_init(g, ref["g"])
        for cm in ref["cms"]:
            r = SN.check(copy.deepcopy(cm), g, "netlist", False)
            row["copies" if cm.kind == "redundant_copies" else "encoding"] = r.verdict
            if cm.kind == "redundant_copies":
                row["independent"] = r.measured.get("independent")
        row["flagged"] = any(row.get(k) not in (None, "SURVIVED") for k in ("copies", "encoding"))
        rows.append(row)
        print(f"{path:62s} {top:6s} copies={row.get('copies'):9s} enc={row.get('encoding'):9s} min={row['measured_min']} (as written: {ref['min']})")
    ok = [r for r in rows if "error" not in r and r["measured_min"] is not None and r["reference_min"] is not None]
    fam = {"v1 (control, 2 copies + single voter)": [r for r in ok if r["top"] == "v1"], "v2 family": [r for r in ok if r["top"] != "v1"]}
    summary = {}
    for name, rs in fam.items():
        tp = sum(1 for r in rs if r["flagged"] and r["measured_min"] < r["reference_min"])
        fp = sum(1 for r in rs if r["flagged"] and r["measured_min"] >= r["reference_min"])
        fn = sum(1 for r in rs if not r["flagged"] and r["measured_min"] < r["reference_min"])
        summary[name] = dict(netlists=len(rs), flagged=sum(r["flagged"] for r in rs), **prf(tp, fp, fn), text=prf_text(prf(tp, fp, fn)),
                             truth="broken = measured minimum flips below the minimum of the same RTL elaborated as written",
                             misses=[dict(netlist=r["netlist"], min=r["measured_min"], as_written=r["reference_min"]) for r in rs
                                     if not r["flagged"] and r["measured_min"] < r["reference_min"]])
    with open(os.path.join(RESULTS, "stored_netlists.json"), "w") as f:
        json.dump(dict(schema="glitchsat-survival-validation/stored/1", rows=rows, summary=summary,
                       label="checker verdicts MEASURED here; measured_min is MEASURED by ext/surface (results/lint_validation.json)"), f, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
