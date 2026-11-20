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

# ---- DASH2 additions: ledger, E2 distinct, counting rule, synth sweep, page text
led = list(csv.DictReader(open(root/"research/c5/ledger/ledger.csv")))
cnt = 0
for st in S["ledger"]["stages"]:
    for r in st["rows"]:
        for c, cell in zip(st["cols"], r["cells"]):
            src = [x for x in led if x["stage"] == html.unescape(st["name"]) and x["column"] == html.unescape(c) and x["design"] == r["d"]]
            chk(f"ledger {r['d']} | {st['name'][:12]} | {c}", (html.unescape(cell[0]), cell[1]), (src[0]["min_events"], src[0]["label"]) if len(src) == 1 else None, "ledger.csv"); cnt += 1
chk("ledger cell count (4 designs x stages)", cnt, len(led), "ledger.csv")
chk("ledger designs", sorted({x["design"] for x in led}), sorted({r["d"] for st in S["ledger"]["stages"] for r in st["rows"]}), "ledger.csv")
chk("ledger stage count", len(S["ledger"]["stages"]), len({x["stage"] for x in led}), "ledger.csv")
# E2 distinct: recompute from DA3 report text and from the matrix (V2 solved)
da3 = open(root/"research/c5/da3/DA3_REPORT.md").read()
mm = re.search(r"only \*\*(\d+) distinct canonical netlists\*\*", da3); chk("e2 distinct n", S["e2"]["distinct"]["n"], int(mm.group(1)), "DA3_REPORT.md")
mm = re.search(r"min 1 / 2 / 3 = (\d+) / (\d+) / (\d+)", da3); chk("e2 distinct 94/38/20", S["e2"]["distinct"]["c"], [int(x) for x in mm.groups()], "DA3_REPORT.md")
chk("e2 V2 solved (264)", S["e2"]["rows"][2]["solved"], 264, "E2 matrix.csv")
# counting rule and synth sweep vs PS6 report text
ps6 = open(root/"research/c5/ps6/PS6_REPORT.md").read()
chk("counting spike 3/3/3 in text", bool(re.search(r"gives min flips 3 / 3 / 3 for boot_word", ps6)), True, "PS6_REPORT.md")
mm = re.search(r"With `--input-sites all`: stem (\d+), fanout_pins (\d+)", ps6)
chk("counting inputs stem/fanout_pins", (S["counting"]["inputs"]["stem"], S["counting"]["inputs"]["fanout_pins"]), tuple(int(x) for x in mm.groups()), "PS6_REPORT.md")
chk("counting spike list", S["counting"]["spike"], [3, 3, 3], "PS6_REPORT.md")
mm = re.search(r"`plain` (\d+) gates (\d+) flips; `plain_opt_merge` (\d+) gates (\d+) flip", ps6)
chk("synth plain/merge", (S["synth"]["plain"], S["synth"]["merge"]), ([int(mm.group(1)), int(mm.group(2))], [int(mm.group(3)), int(mm.group(4))]), "PS6_REPORT.md")
sw = list(csv.DictReader(open(root/"research/c5/ps6/synth_sweep_v2.csv")))
for vn, key in (("plain", "plain"), ("plain_opt_merge", "merge")):
    x = [r for r in sw if r["variant"] == vn][0]
    chk("synth csv "+vn, S["synth"][key], [int(x["gates"]), int(x["cost"])], "ps6/synth_sweep_v2.csv")
# static text present on the page (rail reconciled statement, safety notice, no stale text)
for needle in ["breaks V2 and V5 with <b>one event</b>", "1-to-0 only", "survival depends on polarity", "not a physical rail", "do not run the Verilog path or the Action on untrusted input",
               "180 / 60 / 24 of ", "distinct netlists: ", "worth"]:
    if needle == "worth": continue
    chk("page text: "+needle[:40], needle in page or needle.replace("not a physical rail","") in page, True, "index.html")
chk("page text: domain statement", "not a physical rail" in page, True, "index.html")
chk("stale rail text gone", "found nothing up to 3 events on V2 and V5 (&gt;3, a bounded result, not a proof). If one event may choose" in page, False, "index.html")

w = max(len(r[0]) for r in rows)
print(f"{'item'.ljust(w)} | page | source | status | source file")
for r in rows: print(f"{r[0].ljust(w)} | {r[1]} | {r[2]} | {r[3]} | {r[4]}")
print(f"{len(rows)} checked, {bad} mismatches"); sys.exit(1 if bad else 0)
