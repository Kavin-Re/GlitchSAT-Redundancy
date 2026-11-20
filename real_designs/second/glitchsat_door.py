#!/usr/bin/env python3
"""
Adapted glitchsat-style bounded fault solver for a SECOND real design:
Rameshwar-12/Door_lock_system (tt_um_rameshwar_door_lock), Apache-2.0.
See REPORT.md for provenance.

Design is PURELY COMBINATIONAL (no DFF cells in the synthesized netlist,
confirmed from door5.json: only $_AND_, $_NOT_, $_OR_). So there is no
sequential state to carry across cycles; T (cycle count) is modelled only
to mirror the project's report format, but the goal re-evaluates
independently every cycle from the free, attacker-controlled ui_in bits.

Security goal: unlock asserted (uo_out[0]==1) while the real password
input (ui_in[3:0]) is NOT the correct code (4'b1010), under <=k single-net
bit-flip faults anywhere in the gate netlist (AND/OR/NOT outputs), at any
of the T modelled cycles, same fault budget shared across all cycles
(matches glitchsat_adapted.py's k-budget-per-run convention).
"""
import json, sys, time
from z3 import *

def load(path, top):
    m = json.load(open(path))['modules'][top]
    names = {}
    for n, x in m['netnames'].items():
        for i, b in enumerate(x['bits']):
            if isinstance(b, int):
                names.setdefault(b, f"{n}[{i}]" if len(x['bits']) > 1 else n)
    return m, names

def build(m, names, T, k):
    cells = m['cells']; ports = m['ports']
    s = Solver()
    drivers = {}
    for cn, c in cells.items():
        t = c['type']; con = c['connections']
        drivers[con['Y'][0]] = (cn, t, con)

    ui_bits = ports['ui_in']['bits']          # [2..9] == ui_in[0..7]
    unlock_bit = ports['uo_out']['bits'][0]    # net 10
    sites = list(drivers.keys())
    F = {(t, b): Bool(f"f_{t}_{b}") for t in range(T) for b in sites}

    goal_terms = []
    for t in range(T):
        atk = [Bool(f"ui_{t}_{i}") for i in range(8)]
        val = {}
        def get(b):
            if b in (0, '0'): return BoolVal(False)
            if b == '1': return BoolVal(True)
            if b == 'x': return BoolVal(False)
            if b in val: return val[b]
            if b in ui_bits:
                v = atk[ui_bits.index(b)]
            else:
                _, ty, con = drivers[b]
                g = lambda p: get(con[p][0])
                if ty == '$_AND_': v = And(g('A'), g('B'))
                elif ty == '$_OR_': v = Or(g('A'), g('B'))
                elif ty == '$_NOT_': v = Not(g('A'))
                elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
                else: raise Exception(f"unsupported cell type {ty}")
            v = Xor(v, F[(t, b)]) if b in sites else v
            val[b] = v; return v
        unlock_v = get(unlock_bit)
        # real-world mismatch computed from the true (unfaulted) attacker inputs,
        # not from any (possibly faulted) internal net
        wrong_pw = Not(And(Not(atk[0]), atk[1], Not(atk[2]), atk[3]))  # != 4'b1010
        goal_terms.append(And(unlock_v, wrong_pw))
    s.add(Or(*goal_terms))
    allf = list(F.values())
    return s, F, allf

def solve(m, names, T, k):
    s, F, allf = build(m, names, T, k)
    s.add(PbLe([(f, 1) for f in allf], k))
    t0 = time.time(); r = s.check(); dt = time.time() - t0
    if r != sat: return str(r), dt, None
    mod = s.model()
    best = [kk for kk, f in F.items() if is_true(mod.eval(f, model_completion=True))]
    while len(best) > 0:
        s.push(); s.add(PbLe([(f, 1) for f in allf], len(best) - 1))
        if s.check() == sat:
            mod = s.model(); best = [kk for kk, f in F.items() if is_true(mod.eval(f, model_completion=True))]; s.pop()
        else:
            s.pop(); break
    return 'sat', dt, [(t, names.get(b, str(b))) for t, b in sorted(best)]

if __name__ == '__main__':
    m, names = load('door5.json', 'tt_um_rameshwar_door_lock')
    rows = []
    for T in (4, 6):
        r, dt, res = solve(m, names, T, 0)
        print(f"T={T} k=0 (sanity, no faults):", r, f"{dt:.3f}s")
        rows.append(('sanity', T, 0, r, round(dt, 4), res))
    for k in (1, 2):
        for T in (4, 6):
            r, dt, res = solve(m, names, T, k)
            print(f"T={T} k<={k}:", r, f"{dt:.3f}s", res)
            rows.append(('attack', T, k, r, round(dt, 4), res))
    json.dump(rows, open('door_results.json', 'w'))
