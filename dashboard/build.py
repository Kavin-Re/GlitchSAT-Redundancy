#!/usr/bin/env python3
"""Build dashboard/index.html from results/*.json (fallback: spike numbers).
Accepted results/vN.json keys (all optional): verdict, k, bound|T, runtime|runtime_s,
faults [[net,cycle]...], input|attacker_input|sig, explanation, evidence, rows [{design,T,k,verdict,runtime}].
Optional results/curve.json: [[design,T,k,verdict,runtime],...]."""
import html, json, pathlib
here = pathlib.Path(__file__).parent
res = here.parent / "results"
SPIKE = "from spike, re-run pending"
data = {
 "source": SPIKE, "live": False,
 "designs": {
  "v0": {"name": "V0 naive FSM", "verdict": "BROKEN", "k": 1, "T": 6, "runtime": None,
         "faults": [["new_n13_", 1]], "sig": 211, "evidence": "MEASURED", "src": SPIKE},
  "v1": {"name": "V1 duplicated + sparse FSM", "verdict": "BROKEN", "k": 1, "T": 6, "runtime": 0.17,
         "faults": [["ok", 1]], "sig": 3, "evidence": "MEASURED", "src": SPIKE},
  "v2": {"name": "V2 triplicated + split word", "verdict": "NO ATTACK (k<=2), spike netlist", "k": 2, "T": 16, "runtime": 130.0,
         "faults": [], "sig": None, "evidence": "MEASURED", "src": SPIKE},
 },
 "rows": [
  ["v0",6,1,"sat",None],
  ["v1",4,1,"sat",0.15],["v1",6,1,"sat",0.15],["v1",8,1,"sat",0.18],["v1",10,1,"sat",0.16],["v1",12,1,"sat",0.16],["v1",16,1,"sat",0.21],
  ["v2",4,2,"unsat",0.26],["v2",6,2,"unsat",1.35],["v2",8,2,"unsat",4.87],["v2",10,2,"unsat",16.05],["v2",12,2,"unsat",52.33],["v2",16,2,"unsat",130.0],
  ["v2",4,3,"sat",0.46],["v2",6,3,"sat",0.75],["v2",8,3,"sat",3.61],["v2",10,3,"sat",15.05],["v2",12,3,"sat",69.83],["v2",16,3,"sat",28.72]],
}
def load(p):
    try: return json.loads(p.read_text())
    except Exception as e: print("skip", p, e); return None
if res.is_dir():
    for key in ("v0","v1","v2"):
        d = load(res/f"{key}.json") if (res/f"{key}.json").exists() else None
        if isinstance(d, dict):
            t = data["designs"][key]
            t["verdict"] = str(d.get("verdict", t["verdict"])).upper()
            t["k"] = d.get("k", t["k"]); t["T"] = d.get("bound", d.get("T", t["T"]))
            t["runtime"] = d.get("runtime", d.get("runtime_s", t["runtime"]))
            t["faults"] = [list(f)[:2] for f in d.get("faults", t["faults"])]
            t["sig"] = d.get("input", d.get("attacker_input", d.get("sig", t["sig"])))
            if "explanation" in d: t["explanation"] = d["explanation"]
            t["evidence"] = d.get("evidence", "MEASURED"); t["src"] = f"results/{key}.json"
            data["live"] = True; data["source"] = "results/*.json"
            if isinstance(d.get("rows"), list): data["rows_live"] = d["rows"]
    if (res/"curve.json").exists():
        c = load(res/"curve.json")
        if isinstance(c, list): data["rows"] = c; data["live"] = True; data["source"] = "results/*.json"
    if data.get("rows_live"):
        data["rows"] = [[r.get("design"),r.get("T"),r.get("k"),r.get("verdict"),r.get("runtime")] for r in data["rows_live"]]
# live data from results/reproduce (6 cycles) and results/deep/sweep_main.json (8 to 20 cycles)
try:
    def rj(p): return json.loads(p.read_text())
    rep = res/"reproduce"
    designs = {}
    for d in ("v0", "v1"):
        j = rj(rep/f"{d}_spike_given-netlist_k1.json")
        rt = j["runtime_s"]["solve_and_minimize"] if isinstance(j["runtime_s"], dict) else j["runtime_s"]
        designs[d] = {"name": data["designs"][d]["name"], "verdict": "BROKEN", "k": 1, "T": 6, "runtime": rt,
                      "faults": [[x["net"], x["cycle"]] for x in j["faults"]],
                      "sig": int(j["attacker_input"]["sig"], 16), "evidence": "MEASURED", "src": "results/reproduce"}
    deep = rj(res/"deep"/"sweep_main.json")
    spike = [r for r in deep if r.get("route") == "spike" and r.get("status") == "DONE"]
    v2k2 = [r for r in spike if r["design"] == "v2" and r["k"] == 2]
    top = max(v2k2, key=lambda r: r["cycles"])
    designs["v2"] = {"name": data["designs"]["v2"]["name"], "verdict": "NO ATTACK (k<=2), spike netlist", "k": 2,
                     "T": top["cycles"], "runtime": top["solve_s"], "faults": [], "sig": None,
                     "evidence": "MEASURED", "src": "results/deep"}
    want = {("v0", 1), ("v1", 1), ("v2", 2), ("v2", 3)}
    rows = []
    es0 = rj(res/"reproduce_summary.json")
    for r in es0["rows"]:
        if r["netlist"] == "spike/given-netlist" and (r["design"], r["k"]) in want:
            rows.append([r["design"], 6, r["k"], "sat" if r["verdict"] == "ATTACK_FOUND" else "unsat", r["runtime_s"]])
    for r in spike:
        if (r["design"], r["k"]) in want:
            rows.append([r["design"], r["cycles"], r["k"], "sat" if r["verdict"] == "ATTACK_FOUND" else "unsat", r["solve_s"]])
    data["designs"] = designs; data["rows"] = rows; data["live"] = True; data["source"] = "results/*.json"
except Exception as e:
    print("could not load live results, keeping built-in spike numbers:", e)

# engine re-run (results/reproduce_summary.json)
try:
    es = json.loads((res/"reproduce_summary.json").read_text())
    data["engine"] = {"cycles": es.get("cycles"), "rows": [r for r in es["rows"] if r.get("k") in (1,2,3)]}
except Exception as e:
    print("no engine summary:", e)

# Scope tab data: read from the stored result files; each value is re-read from its source by research/c4/dash/verify_numbers.py.
try:
    import csv
    root = here.parent
    def _ledger(root):
        P = "research/c5/ledger/ledger.csv"; names = []; out = {}
        for r in csv.DictReader(open(root/P)):
            n = r["stage"]
            if n not in out: out[n] = {"cols": [], "rows": {}}; names.append(n)
            o = out[n]
            if r["column"] not in o["cols"]: o["cols"].append(r["column"])
            o["rows"].setdefault(r["design"], {})[r["column"]] = [r["min_events"], r["label"]]
        return {"src": P, "stages": [{"name": n, "cols": out[n]["cols"], "rows": [{"d": d, "cells": [out[n]["rows"][d][c] for c in out[n]["cols"]]} for d in out[n]["rows"]]} for n in names]}
    P_B2, P_M1, P_E2, P_B3 = ("research/c2/b2_scope/matrix.jsonl", "research/c3/m1/m1_all_masks.csv",
                              "research/c2/e2_variance/raw/matrix.csv", "research/c4/b3/matrix_T6.jsonl")
    b2 = [json.loads(l) for l in (root/P_B2).read_text().splitlines() if l.strip()]
    def b2v(des, goal, ins, init, nl="spike"):
        r = [x for x in b2 if x["design"] == des and x["netlist"] == nl and x["goal"] == goal and x["input_sites"] == ins
             and x["init"] == init and x["free_input"] is False]
        assert len(r) == 1, (des, goal, ins, init, len(r))
        return r[0]["min_cost"] if r[0]["verdict"] == "ATTACK_FOUND" else ">%s" % r[0]["cost_gt"]
    scope_rows = [("Goal = result word; input nets NOT fault sites; known power-up state (the claim 'V2 holds up to 2 flips')", "boot_word", False, "known"),
                  ("Goal = accept flag boot_ok (same assumptions otherwise)", "boot_ok", False, "known"),
                  ("Goal = result word; input nets ARE fault sites (input buffers)", "boot_word", True, "known"),
                  ("Goal = result word; arbitrary non-accepting power-up state", "boot_word", False, "free_nongoal"),
                  ("Goal = result word; arbitrary power-up state (no reset)", "boot_word", False, "free")]
    m1 = {int(r["mask_hex"], 16): r for r in csv.DictReader(open(root/P_M1))}
    e2 = list(csv.DictReader(open(root/P_E2)))
    def e2row(d):
        s = [r for r in e2 if r["design"] == d and r["status"] == "SOLVED"]
        c = lambda k: sum(1 for r in s if r["min_flips"] == str(k))
        return {"d": d, "c1": c(1), "c2": c(2), "c3": c(3), "solved": len(s), "unsup": sum(1 for r in e2 if r["design"] == d and r["status"] != "SOLVED")}
    b3 = [json.loads(l) for l in (root/P_B3).read_text().splitlines() if l.strip()]
    rcols = [("v0", "V0 spike"), ("v1", "V1 spike"), ("v2", "V2 spike"), ("v2_apt033", "V2 apt-0.33"), ("v5_apt033", "V5 apt-0.33")]
    rrows = [("stem_flip", "Single-wire flip (baseline model)"), ("rail_all", "Rail event: whole design 1 to 0"),
             ("rail_half", "Rail event: any hierarchy union up to half"), ("rail_cone", "Rail event: fanout cone of one net"),
             ("dip_subset", "Bound: one event may pick ANY gate subset (not supported by SPICE)")]
    def b3v(des, mod):
        r = [x for x in b3 if x["design"] == des and x["model"] == mod and x["goal"] == "word"]
        assert len(r) == 1, (des, mod, len(r)); return r[0]["min"]
    data["scope"] = {
        "src": {"b2": P_B2, "m1": P_M1, "e2": P_E2, "b3": P_B3},
        "b2": [{"label": lab, "v0": b2v("v0", g, i, n), "v1": b2v("v1", g, i, n), "v2": b2v("v2", g, i, n), "v2apt": b2v("v2", g, i, n, "apt033_plain")} for lab, g, i, n in scope_rows],
        "widths": [[n, int(m1[(1 << n) - 1]["v2_spike_min_flips"])] for n in range(1, 9)],
        "e2": {"total": 288, "rows": [e2row(d) for d in ("v0", "v1", "v2")], "distinct": {"n": 152, "c": [94, 38, 20]}},
        "counting": {"src": "research/c5/ps6/PS6_REPORT.md", "spike": [3, 3, 3], "inputs": {"stem": 1, "fanout_pins": 3}},
        "synth": {"src": "research/c5/ps6/PS6_REPORT.md", "plain": [85, 2], "merge": [63, 1]},
        "ledger": _ledger(root),
        "rail": {"cols": [c[1] for c in rcols], "rows": [{"label": lab, "vals": [b3v(d, m) for d, _ in rcols]} for m, lab in rrows]}}
except Exception as e:
    print("no scope data (Scope tab hidden):", e)
tpl = (here/"template.html").read_text()
# Text-only corrections applied to the template at build time (review findings CC-5, CC-8, CC-9, CC-12, CC-13, CC-14, CC-4, E1; F1).
# Each pair must match exactly once; no styling or structure is changed.
TEXT_FIXES = [
 ('"No attack found" is a proof only within those limits.',
  '"No attack found" is a bounded SAT result: it holds only within those limits.'),
 ('Only one exists here: V2 on one netlist, up to 2 flips.',
  'Unbounded results exist only for the V2 spike netlist (k up to 2; ABC PDR via SymbiYosys, constant attacker input, no independent certificate; also with a free per-cycle attacker input under the rule "key never presented at any cycle", E1) and, at k=1, for the stored 85-gate apt-0.33 netlist.'),
 ('<h1>Breaking and fixing a secure-boot FSM with faults</h1>', '<h1>Breaking and fixing a toy secure-boot FSM model with modelled faults</h1>'),
 ('<h2>Act 2: Try a fix (V2)</h2>', '<h2>Act 2: Try a fix (V2; on the spike netlist)</h2>'),
 ('An attacker has to corrupt all three copies.</p>',
  'The smallest attacks found use three flips: some hit all three compare copies, some hit two copies plus a bit of the result word. On the spike netlist split copies resisted 1 and 2 flips; on the apt-0.33 re-synthesis they did not.</p>'),
 ('An attacker then has to corrupt all three copies (3 flips). This held against up to 2 flips on the netlist checked,',
  'The smallest attacks found use 3 flips (some hit all three compare copies, some two copies plus a bit of the result word). This held against up to 2 flips on the spike netlist checked (and not on the apt-0.33 re-synthesis),'),
 ('<b>MEASURED (flow results):</b> 35 cells, 399 um2 placed at 77%, setup slack +7.05 ns at 10 ns (post-route estimate),',
  '<b>MEASURED (flow results):</b> 35 synthesized cells (357.8 um2); 76 placed components including taps and fill, 399 um2 core area used at 77% utilisation (flow-tool values); setup slack +7.05 ns at 10 ns (ESTIMATED, post-route),'),
 ('The standard-cell errors are false positives of checking a cell without tap cells (tested for one cell only).',
  'The standard-cell errors are tap-dependent rules (nwell.4, LU.2, LU.3): clean in context for one cell (dfxtp_1); the other cell types were not tested in context; the layout is not claimed DRC-clean.'),
 ('So the answer depends on the exact netlist the tool produces: always name the tool build.',
  'On a third netlist (validation flow B, hierarchy stripped) the same V2 falls to a single flip (4 of 378 single-flip sites at 6 cycles; validation/VALIDATION.md). So the answer depends on the exact netlist the tool produces, and on counting a flip of a shared net as one fault (a 32-netlist re-synthesis matrix from one recipe: V2 held against 2 flips on 6 of 32; first in research/c2/devils_advocate/DA_CYCLE1.md and replicated on 64 of 64 rows by an independent re-run, research/c3/rep/REP_REPORT.md). It is not a version effect (the spike netlist is also Yosys 0.33): the armed word 0xCC touches only 2 of the 3 copies, so encoding sets the floor at 2 and the flow decides whether it is reached (docs/report/WHY_TWO_FLIPS.md). Always name the netlist hash and flow.'),
 ('<li><b>Found (measured):</b> flipping one wire',
  '<li><b>Scope of every V2 statement:</b> on the stored spike netlist, with the goal being the 8-bit result word, input nets not treated as fault sites, a known power-up state and a constant non-key attacker input, no set of at most 2 flips reaches the word. The accept output <code>boot_ok</code> itself can be flipped with 1 flip (MEASURED, re-checked). Treating input nets as fault sites reduces the minimum to 1 (MEASURED in the scope matrix, research/c2/b2_scope/B2_REPORT.md). The apt Yosys 0.33 re-synthesis (85 gates) has a 2-flip attack; the conda 0.38 one (83 gates) did not.</li>\n<li><b>Found (measured):</b> flipping one wire'),
 ("V2 has no attack with up to 2 flips for any number of cycles. This covers that fault model and that netlist only.",
  "V2 has no attack on the 8-bit result word with up to 2 flips for any number of cycles. This covers that fault model, that netlist, that goal (the accept flag boot_ok falls to 1 flip), a known power-up state, input nets that are not fault sites and a constant attacker input only."),
 ("No single flip, and no pair of flips, got through within the bound (and on this netlist a formal proof covers any number of cycles).",
  "No single flip, and no pair of flips, changed the 8-bit result word within the bound (on this netlist and goal a formal proof covers any number of cycles; the accept flag boot_ok is not covered and falls to 1 flip; input nets are not fault sites)."),
 ("(up to 2 flips, on this netlist). ${B(ev(d))}",
  "(up to 2 flips, on this netlist, for the 8-bit result word; not for the accept flag boot_ok). ${B(ev(d))}"),
 ("(and none for any number of cycles on this netlist, by the formal proof).",
  "(and none for any number of cycles on this netlist, by the formal proof, for the result-word goal only; the accept flag boot_ok falls to 1 flip)."),
 ("<b>Important caveat (measured):</b> this result holds for the <b>specific netlist from the spike</b>.",
  "<b>Important caveat (measured):</b> this result holds for the <b>specific netlist from the spike</b>, for the 8-bit result word as the goal (the accept output boot_ok falls to 1 flip), with input nets not treated as fault sites (treating input nets as fault sites reduces the minimum to 1 (MEASURED, scope matrix)) and a known power-up state."),
]
TEXT_FIXES += [
 # page review 2026-11-20: no process codenames, no "prove" wording, the safety notice lives in SECURITY.md
 (tpl[tpl.index('<div class="banner" id="safety"'):tpl.index('</div>', tpl.index('<div class="banner" id="safety"')) + 6],
  '<div class="banner" id="safety" role="note"><b>Running on your own files:</b> the Verilog path calls Yosys, which is not sandboxed; '
  'only analyse files you trust. Details: <code>SECURITY.md</code> in the repository.</div>'),
 ('<h2>Act 3: Prove it, within a bound</h2>', '<h2>Act 3: Check it, within a bound</h2>'),
 ('that makes a chip boot with the wrong key.', 'that makes a toy boot-lock model accept the wrong key.'),
 ('with Yosys 0.38 and with Yosys 0.52 (Docker, H5) on the plain flow.', 'with Yosys 0.38 and with Yosys 0.52 (Docker) on the plain flow.'),
]
for _old, _new in TEXT_FIXES:
    assert tpl.count(_old) == 1, ("TEXT_FIXES: expected exactly one match", _old[:60], tpl.count(_old))
    tpl = tpl.replace(_old, _new)
# H1 hardening (escaping only): results/*.json is untrusted input (e.g. produced from a hostile netlist).
# 1) every string that the template puts into innerHTML is HTML-escaped here (the template itself esc()s fault net names, so
#    the 'faults' lists are left alone to avoid double escaping); 2) the JSON embedded in the <script> element cannot contain
#    '</script>', '<!--' or U+2028/9 because <, >, & are written as \\uXXXX escapes (still valid JSON/JS, identical values).
def _clean(o, key=None):
    if key == "faults": return o
    if isinstance(o, str): return html.escape(o, quote=True)
    if isinstance(o, list): return [_clean(x) for x in o]
    if isinstance(o, dict): return {k: _clean(v, k) for k, v in o.items()}
    return o
def _script_json(o):
    return json.dumps(o).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
tpl = tpl.replace("a formal proof covers", "an unbounded model-checker result (ABC PDR, tool-reported, not independently replicated) covers").replace(
    "by the formal proof", "by an unbounded model-checker result (ABC PDR, tool-reported)")
(here/"index.html").write_text(tpl.replace("/*DATA*/", "const DATA = " + _script_json(_clean(data)) + ";"))
print("wrote index.html; live =", data["live"])
