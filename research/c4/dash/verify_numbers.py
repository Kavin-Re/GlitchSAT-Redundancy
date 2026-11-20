#!/usr/bin/env python3
"""Compare numbers embedded in dashboard/index.html (const DATA) with the source files. usage: verify_numbers.py ROOT"""
import json, csv, sys, re, html, pathlib
root = pathlib.Path(sys.argv[1]); page = (root/"dashboard/index.html").read_text()
m = re.search(r"const DATA = (.*);\n", page); D = json.loads(m.group(1))
rows = []; bad = 0
def chk(name, pv, sv, src):
    global bad
    ok = (str(pv) == str(sv)); bad += (not ok)
    rows.append((name, pv, sv, "OK" if ok else "MISMATCH", src))
S = D["scope"]
b2 = [json.loads(l) for l in open(root/"research/c2/b2_scope/matrix.jsonl")]
def cell(des, nl, goal, ins, init):
    for x in b2:
        if (x["design"], x["netlist"], x["goal"], x["input_sites"], x["init"], x["free_input"]) == (des, nl, goal, ins, init, False):
            return x["min_cost"] if x["verdict"] == "ATTACK_FOUND" else ">" + str(x["cost_gt"])
spec = [("boot_word", False, "known"), ("boot_ok", False, "known"), ("boot_word", True, "known"), ("boot_word", False, "free_nongoal"), ("boot_word", False, "free")]
for i, (g, ins, init) in enumerate(spec):
    for key, des, nl in (("v0", "v0", "spike"), ("v1", "v1", "spike"), ("v2", "v2", "spike"), ("v2apt", "v2", "apt033_plain")):
        chk(f"scope b2 row{i} {key}", S["b2"][i][key], cell(des, nl, g, ins, init), "b2_scope/matrix.jsonl")
# hand-stated expectations from the task / reports
for n, v in zip(range(1, 9), [0, 1, 1, 2, 2, 3, 3, 3]):
    chk(f"width n={n}", dict(S["widths"])[n], v, "PS5_REPORT.md / M1 csv")
for r, exp in zip(S["e2"]["rows"], [(264, 0, 0), (233, 31, 0), (180, 60, 24)]):
    chk(f"e2 {r['d']} min1/2/3", (r["c1"], r["c2"], r["c3"]), exp, "E2_REPORT.md table 3")
cs = list(csv.reader(open(root/"research/c3/m1/m1_all_masks.csv"))); h = cs[0]
for n in range(1, 9):
    mk = (1 << n) - 1
    v = [r for r in cs[1:] if int(r[0], 16) == mk][0][h.index("v2_spike_min_flips")]
    chk(f"width n={n} vs csv", dict(S["widths"])[n], v, "m1_all_masks.csv")
b3 = [json.loads(l) for l in open(root/"research/c4/b3/matrix_T6.jsonl")]
cols = ["v0", "v1", "v2", "v2_apt033", "v5_apt033"]; mods = ["stem_flip", "rail_all", "rail_half", "rail_cone", "dip_subset"]
for mi, mo in enumerate(mods):
    for ci, c in enumerate(cols):
        sv = [x["min"] for x in b3 if x["design"] == c and x["model"] == mo and x["goal"] == "word"][0]
        chk(f"rail {mo} {c}", html.unescape(str(S["rail"]["rows"][mi]["vals"][ci])), sv, "b3/matrix_T6.jsonl")
es = json.load(open(root/"results/reproduce_summary.json"))
for r in es["rows"]:
    if r["k"] in (1, 2, 3):
        pr = [x for x in D["engine"]["rows"] if x["design"] == r["design"] and x["netlist"] == r["netlist"] and x["k"] == r["k"]][0]
        chk(f"engine {r['design']} {r['netlist']} k{r['k']}", (pr["verdict"], pr.get("min_faults")), (r["verdict"], r.get("min_faults")), "reproduce_summary.json")
for r in D["rows"]:
    if r[1] == 6:
        sr = [x for x in es["rows"] if x["design"] == r[0] and x["k"] == r[2] and x["netlist"] == "spike/given-netlist"]
        if sr: chk(f"curve {r[0]} k{r[2]} T6 runtime", r[4], sr[0]["runtime_s"], "reproduce_summary.json")
deep = json.load(open(root/"results/deep/sweep_main.json"))
for r in D["rows"]:
    if r[1] != 6:
        sr = [x for x in deep if x.get("route") == "spike" and x.get("status") == "DONE" and x["design"] == r[0] and x["k"] == r[2] and x["cycles"] == r[1]]
        chk(f"curve {r[0]} k{r[2]} T{r[1]} runtime", r[4], sr[0]["solve_s"] if sr else None, "deep/sweep_main.json")
w = max(len(r[0]) for r in rows)
print(f"{'item'.ljust(w)} | page | source | status | source file")
for r in rows: print(f"{r[0].ljust(w)} | {r[1]} | {r[2]} | {r[3]} | {r[4]}")
print(f"{len(rows)} checked, {bad} mismatches"); sys.exit(1 if bad else 0)
