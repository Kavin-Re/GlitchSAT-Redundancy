#!/usr/bin/env python3
"""Re-checks game.html's toy-model outcomes against the real solver verdicts.
Read-only: reads docs/explainers/game.html, results/reproduce_summary.json, results/reproduce/*.json,
docs/ENGINE_STATUS.md. Writes nothing. Usage: python3 docs/explainers/dev/check_game_answers.py
Toy model: wrong code => every check says 0. A 'check' node = 0 xor flip; 'and' = AND(inputs) xor flip;
'or' = OR(inputs) xor flip. Lock opens iff all 8 lights (each = value of its driver node) are 1."""
import json, re, itertools, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.dirname(os.path.dirname(HERE))  # HERE = the pages folder docs/explainers; this script is in its dev/ subfolder
html = open(os.path.join(HERE, "game.html"), encoding="utf-8").read()
model = json.loads(re.search(r'<script type="application/json" id="toy-model">(.*?)</script>', html, re.S).group(1))

def opens(d, flipped):
    v = {}
    for n in d["nodes"]:
        k = n["kind"]
        b = 0
        if k == "and": b = int(all(v[i] for i in n["inputs"]))
        elif k == "or": b = int(any(v[i] for i in n["inputs"]))
        v[n["id"]] = b ^ (1 if n["id"] in flipped else 0)
    return all(v[x] == 1 for x in d["lights"])

def toy_attack(d, k):
    ids = [n["id"] for n in d["nodes"]]
    return any(opens(d, set(c)) for kk in range(1, k + 1) for c in itertools.combinations(ids, kk))

summ = json.load(open(os.path.join(ROOT, "results/reproduce_summary.json")))["rows"]
def real(design, nets, k):
    vs = [r["verdict"] for r in summ if r["design"] == design and r["netlist"] in nets and r["k"] == k]
    return vs
# which real rows each toy design is checked against
MAP = {"v0": ("v0", ["rtl/plain", "rtl/opt", "spike/given-netlist"]),
       "v1": ("v1", ["rtl/plain", "rtl/opt", "spike/given-netlist"]),
       "v2": ("v2", ["spike/given-netlist"]),
       "v2a": ("v2", ["rtl/plain", "rtl/opt"])}
fails = 0
def rep(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok: fails += 1
for d in model["designs"]:
    if d["real"] is None:   # toy-only picture (three guards, one shared wire): no solver row exists
        toymin = next(k for k in range(1, 6) if toy_attack(d, k))
        rep(toymin == 1, f"{d['id']:4s} toy-only (no solver run, must be labelled 'not run'): toy minimum = {toymin}")
        continue
    for k in (1, 2, 3):
        toy = toy_attack(d, k); emb = d["real"]["attack_at_k"][str(k)]
        if d["id"] in MAP:
            des, nets = MAP[d["id"]]
            vs = real(des, nets, k)
            ok = len(vs) > 0 and all((v == "ATTACK_FOUND") == toy for v in vs) and emb == toy
            rep(ok, f"{d['id']:4s} k={k} toy={'FALLS' if toy else 'holds'} real={sorted(set(vs))} embedded={emb}")
        else:  # v2b: conda Yosys row exists only in docs/ENGINE_STATUS.md
            rep(emb == toy, f"{d['id']:4s} k={k} toy={'FALLS' if toy else 'holds'} embedded(docs)={emb}  [docs-sourced, see below]")
# minimum costs vs min_faults in the real JSONs
def minf(f):
    return json.load(open(os.path.join(ROOT, "results/reproduce", f)))["min_faults"]
exp = {"v0": minf("v0_spike_given-netlist_k3.json"), "v1": minf("v1_spike_given-netlist_k3.json"),
       "v2": minf("v2_spike_given-netlist_k3.json"), "v2a": minf("v2_rtl_plain_k3.json")}
for d in model["designs"]:
    if d["real"] is None: continue
    toymin = next(k for k in range(1, 6) if toy_attack(d, k))
    rep(toymin == d["real"]["min_flips"], f"{d['id']:4s} toy minimum {toymin} == embedded real.min_flips {d['real']['min_flips']} (shown on the result cards)")
    if d["id"] in exp:
        rep(toymin == exp[d["id"]], f"{d['id']:4s} minimum flips toy={toymin} real min_faults={exp[d['id']]} (results/reproduce JSON)")
st = open(os.path.join(ROOT, "docs/ENGINE_STATUS.md"), encoding="utf-8").read()
row = [l for l in st.splitlines() if "conda Yosys 0.38+92" in l and l.startswith("|")]
rep(bool(row) and "| NO_ATTACK | NO_ATTACK | ATTACK, min 3 |" in row[0], "v2b: docs/ENGINE_STATUS.md conda row says NO_ATTACK, NO_ATTACK, ATTACK min 3 (text check, not a solver re-run)")
# explainer.html claims block and visible numbers must match the game model
ex = open(os.path.join(HERE, "explainer.html"), encoding="utf-8").read()
cl = json.loads(re.search(r'<script type="application/json" id="claims">(.*?)</script>', ex, re.S).group(1))
mins = {d["id"]: next(k for k in range(1, 6) if toy_attack(d, k)) for d in model["designs"]}
rep(cl["shared_wire_flips"] == mins["v1x"] and cl["own_wires_flips"] == mins["v2"] and cl["tool1_flips"] == mins["v2b"] and cl["tool2_flips"] == mins["v2a"],
    f"explainer claims {cl['shared_wire_flips']}/{cl['own_wires_flips']}/{cl['tool1_flips']}/{cl['tool2_flips']} == game toy minima {mins['v1x']}/{mins['v2']}/{mins['v2b']}/{mins['v2a']}")
rep("Wiring A (wires kept separate)</span><b>3 flips" in ex and "Wiring B (two wires joined)</span><b>2 flips" in ex and "3 flips</b>, one per guard" in ex,
    "explainer visible text states 3 flips (own wires, tool 1) and 2 flips (tool 2)")
# explainer's own picture logic: need-lists in SPEC have the stated lengths
print("\nOVERALL:", "PASS" if fails == 0 else f"FAIL ({fails})")
print("Note: toy model is ILLUSTRATIVE; real verdicts are bounded (<=3 modelled flips, 6 cycles) and say nothing about unbounded safety.")
sys.exit(1 if fails else 0)
