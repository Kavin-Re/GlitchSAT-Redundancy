#!/usr/bin/env python3
"""Re-synthesise the repository's synthesis-variance grid (research/c2/e2_variance: 96 configurations per design) with
the Yosys builds available here, run the survival checker on every netlist, and compare with the recorded ground truth
in research/c2/e2_variance/raw/matrix.csv (minimum flips, number of distinct compare nets, shared gates).

The Yosys script of each configuration is produced by the repository's own generator (matrix.script), not re-typed.

  python3 validation/e2_matrix.py --build apt0.33=/path/to/yosys-0.33 [--build NAME=/path/to/yosys ...] [--designs v1,v2]

A build NAME that also exists in matrix.csv is compared row by row with the recorded values; other builds are
reported with the minimum measured here only.
"""
import argparse
import collections
import copy
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

from common import ROOT, RESULTS, prf, prf_text
from survival import gnet, intent_rtl, margin, pipeline
from survival import stage_netlist as SN

sys.path.insert(0, os.path.join(ROOT, "research", "c2", "e2_variance", "scripts"))
import matrix as E2  # noqa: E402  (the repository's grid definition)

N_COPIES = {"v1": 2, "v2": 3}


def synth(job):
    yosys, design, flow, order, abc, merge, keep, work = job
    tag = f"{design}__{flow}__{order}__{abc}__{merge}__{keep}"
    out = os.path.join(work, tag + ".json")
    v = os.path.join(work, f"rtl_{keep}", f"{design}.v")
    ys = out[:-5] + ".ys"
    with open(ys, "w") as f:
        f.write("\n".join(E2.script(design, v, out, flow, order, abc, merge)) + "\n")
    p = subprocess.run([yosys, "-q", "-s", ys], capture_output=True, text=True, timeout=300)
    if p.returncode != 0 or not os.path.exists(out):
        return dict(tag=tag, ok=False, err=(p.stderr or p.stdout)[-200:])
    raw = open(out, "rb").read()
    j = json.loads(raw)
    j.pop("creator", None)
    return dict(tag=tag, ok=True, path=out, canon=hashlib.sha256(json.dumps(j, sort_keys=True).encode()).hexdigest())


def solve(args):
    path, design = args
    m = margin.measure(path, design, {}, kmax=3, cycles=6, timeout_s=300)
    return dict(status=m["status"], min=m.get("min_faults"), engine=m.get("engine"), reason=m.get("reason"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="append", required=True, help="NAME=/path/to/yosys")
    ap.add_argument("--designs", default="v1,v2")
    ap.add_argument("--procs", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(RESULTS, "e2_matrix.json"))
    a = ap.parse_args()
    recorded = {}
    with open(os.path.join(ROOT, "research/c2/e2_variance/raw/matrix.csv")) as f:
        for r in csv.DictReader(f):
            recorded[(r["build"], r["design"], r["flow"], r["order"], r["abc"], r["merge"], r["keep"])] = r
    rows = []
    t0 = time.time()
    for b in a.build:
        bname, yosys = b.split("=", 1)
        ver = subprocess.run([yosys, "-V"], capture_output=True, text=True).stdout.strip()
        work = tempfile.mkdtemp(prefix=f"gs-e2-{bname}-")
        for keep in E2.KEEPS:
            os.makedirs(os.path.join(work, f"rtl_{keep}"), exist_ok=True)
            for d in a.designs.split(","):
                t = open(os.path.join(ROOT, "rtl", d + ".v")).read()
                if keep == "keep_off":
                    t = t.replace("(* keep *) ", "")
                open(os.path.join(work, f"rtl_{keep}", d + ".v"), "w").write(t)
        for design in a.designs.split(","):
            rtl = os.path.join(ROOT, "rtl", design + ".v")
            cms0 = [c for c in intent_rtl.scan([rtl]) if c.intent.get("module") == design]
            ref_path = os.path.join(work, f"{design}_rtl_reference.json")
            p = subprocess.run([yosys, "-q", "-p", f"read_verilog {rtl}; hierarchy -top {design}; {pipeline.RTL_REFERENCE_FLOW}; write_json {ref_path}"],
                               capture_output=True, text=True)
            assert p.returncode == 0, p.stderr
            ref = gnet.load(ref_path, design)
            for cm in cms0:
                r0 = SN.check(cm, ref, "rtl", True)
                assert r0.verdict == "SURVIVED", (cm.id, r0.verdict, r0.evidence)
            jobs = [(yosys, design, f, o, ab, m, k, work) for f in E2.FLOWS for o in E2.ORDERS for ab in E2.ABCS
                    for m in E2.MERGES for k in E2.KEEPS]
            with Pool(a.procs) as P:
                S = P.map(synth, jobs, chunksize=4)
            uniq = {}
            for s in S:
                if s["ok"]:
                    uniq.setdefault(s["canon"], s["path"])
            with Pool(a.procs) as P:
                sol = dict(zip(uniq, P.map(solve, [(p_, design) for p_ in uniq.values()], chunksize=1)))
            for s in S:
                _, flow, order, abc, merge, keep = s["tag"].split("__")
                rec = recorded.get((bname, design, flow, order, abc, merge, keep))
                row = dict(build=bname, yosys=ver, design=design, flow=flow, order=order, abc=abc, merge=merge, keep=keep,
                           synth_ok=s["ok"])
                if rec:
                    row.update(rec_status=rec["status"], rec_min=int(rec["min_flips"]) if rec["min_flips"] else None,
                               rec_gates=int(rec["gates"]) if rec["gates"] else None,
                               rec_match_nets=int(rec["distinct_match_nets"]) if rec["distinct_match_nets"] else None,
                               rec_shared=int(rec["shared_gates_between_match_cones"]) if rec["shared_gates_between_match_cones"] else None,
                               same_netlist_as_recorded=(rec["sha256_canon"] == s.get("canon")))
                if not s["ok"]:
                    row["error"] = s["err"]
                    rows.append(row)
                    continue
                try:
                    g = gnet.load(s["path"], design)
                except gnet.NetlistError as e:
                    row["error"] = str(e)[:200]
                    rows.append(row)
                    continue
                SN.copy_init(g, ref)
                row["gates"] = len(g.gates)
                row["flops"] = len(g.flops)
                for cm in cms0:
                    c2 = copy.deepcopy(cm)
                    r = SN.check(c2, g, "synth", False)
                    key = "copies" if cm.kind == "redundant_copies" else "encoding"
                    row[key] = r.verdict
                    if key == "copies":
                        row.update(distinct_nets=r.measured.get("distinct_nets"), independent=r.measured.get("independent"),
                                   shared_cells=r.measured.get("shared_cells"))
                    else:
                        row.update(distance=r.measured.get("distance"), recoded=bool(r.measured.get("recoded")))
                m = sol[s["canon"]]
                row.update(min_here=m["min"], min_status=m["status"], min_engine=m["engine"])
                rows.append(row)
        print(f"{bname}: {len([r for r in rows if r['build'] == bname])} configurations, {time.time() - t0:.0f} s", flush=True)
    summary = summarise(rows)
    with open(a.out, "w") as f:
        json.dump(dict(schema="glitchsat-survival-validation/e2/1", rows=rows, summary=summary,
                       label="MEASURED here (netlists re-synthesised, checker verdicts, minimum flips); rec_* columns are "
                             "RECORDED values copied from research/c2/e2_variance/raw/matrix.csv"), f, indent=1)
    print(json.dumps(summary, indent=1))


def summarise(rows):
    out = {}
    for (b, d), rs in _group(rows, ("build", "design")).items():
        n = N_COPIES[d]
        ok = [r for r in rs if "copies" in r]
        s = dict(configurations=len(rs), checked=len(ok), errors=len(rs) - len(ok),
                 copies=dict(collections.Counter(r["copies"] for r in ok)),
                 encoding=dict(collections.Counter(r.get("encoding") for r in ok)))
        # ground truth 1 (structural, RECORDED): the repository's own count of distinct compare nets / shared gates
        gt = [r for r in ok if r.get("rec_match_nets") is not None]
        if gt:
            tp = sum(1 for r in gt if r["copies"] != "SURVIVED" and (r["rec_match_nets"] < n or r["rec_shared"] > 0))
            fp = sum(1 for r in gt if r["copies"] != "SURVIVED" and not (r["rec_match_nets"] < n or r["rec_shared"] > 0))
            fn = sum(1 for r in gt if r["copies"] == "SURVIVED" and (r["rec_match_nets"] < n or r["rec_shared"] > 0))
            s["vs_recorded_merge"] = dict(rows=len(gt), **prf(tp, fp, fn), text=prf_text(prf(tp, fp, fn)),
                                          same_netlist=sum(1 for r in gt if r.get("same_netlist_as_recorded")),
                                          same_gate_count=sum(1 for r in gt if r.get("rec_gates") == r.get("gates")),
                                          distinct_nets_equal=sum(1 for r in gt if r["rec_match_nets"] == r["distinct_nets"]))
        # ground truth 2 (behavioural): minimum flips; "broken" = fewer flips than the best netlist of this design/build
        for key, label in (("rec_min", "vs_recorded_min"), ("min_here", "vs_measured_min")):
            mm = [r for r in ok if r.get(key) is not None]
            if not mm:
                continue
            best = max(r[key] for r in mm)
            flagged = lambda r: r["copies"] != "SURVIVED" or r.get("encoding") not in ("SURVIVED", None)   # noqa: E731
            tp = sum(1 for r in mm if flagged(r) and r[key] < best)
            fp = sum(1 for r in mm if flagged(r) and r[key] >= best)
            fn = sum(1 for r in mm if not flagged(r) and r[key] < best)
            table = collections.Counter((r["copies"], r[key]) for r in mm)
            s[label] = dict(rows=len(mm), best_min=best, **prf(tp, fp, fn), text=prf_text(prf(tp, fp, fn)),
                            table={f"{v} / min {k}": c for (v, k), c in sorted(table.items())})
        both = [r for r in ok if r.get("rec_min") is not None and r.get("min_here") is not None]
        if both:
            s["min_reproduced"] = dict(rows=len(both), equal=sum(1 for r in both if r["rec_min"] == r["min_here"]))
        out[f"{b}/{d}"] = s
    return out


def _group(rows, keys):
    g = collections.OrderedDict()
    for r in rows:
        g.setdefault(tuple(r[k] for k in keys), []).append(r)
    return g


if __name__ == "__main__":
    main()
