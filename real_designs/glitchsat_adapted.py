#!/usr/bin/env python3
"""
Adapted copy of glitchsat.py (the toy-design spike solver) for a REAL design:
raghul-g1322/tiny_hardware_authentication_tto  -- fsm.v (OTP unlock FSM).

Differences from the original (never edits the original, see REPORT.md):
  - Supports multiple named input ports, each either:
      * "secret"   : one free Bool per bit, held CONSTANT across all T cycles
                     (models the LFSR-generated OTP the attacker does not know)
      * "attacker" : one free Bool per (bit, cycle) -- full control every cycle
                     (models user_digit / user_latch / lfsr_latch button inputs)
  - No `init` attributes exist in this netlist (the design's state reset was
    tied off during synthesis -- see REPORT.md); initial state of every DFF
    is therefore assumed all-zero (the design's own async-reset-to-0 value).
  - Goal is design-specific: unlock==1 at some cycle while user_otp_out !=
    otp at that same cycle (bypassing the compare without knowing the secret).
  - Adds $_DFF_PN0_ support (unused by this particular netlist but kept for
    portability) is NOT included; this netlist only contains $_DFF_P_.
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

def build(m, names, T, k, secret_ports, attacker_ports, goal_ports, minimize=True):
    cells = m['cells']; ports = m['ports']
    s = Solver()
    drivers = {}; dffs = []
    for cn, c in cells.items():
        t = c['type']; con = c['connections']
        if t == '$_DFF_P_':
            dffs.append((cn, con['D'][0], con['Q'][0]))
        else:
            drivers[con['Y'][0]] = (cn, t, con)

    # secret bits: one free Bool per bit, constant across time
    secret_bits = {}
    for pn in secret_ports:
        for b in ports[pn]['bits']:
            secret_bits[b] = Bool(f"secret_{b}")
    # attacker bits: free Bool per (t,bit)
    attacker_bits = {}
    for pn in attacker_ports:
        for b in ports[pn]['bits']:
            for t in range(T):
                attacker_bits[(t, b)] = Bool(f"atk_{b}_{t}")

    sites = [q for _, _, q in dffs] + list(drivers.keys())
    F = {(t, b): Bool(f"f_{t}_{b}") for t in range(T) for b in sites}
    # No init attrs in this netlist -> assume all-zero power-on state
    state = {q: BoolVal(False) for _, _, q in dffs}

    goal_terms = []
    for t in range(T):
        val = {}
        def get(b):
            if b in ('0', 0) or b == '0': return BoolVal(False)
            if b == '1': return BoolVal(True)
            if b == 'x': return BoolVal(False)
            if b in val: return val[b]
            if b in secret_bits: v = secret_bits[b]
            elif (t, b) in attacker_bits: v = attacker_bits[(t, b)]
            elif b in state: v = state[b]
            else:
                _, ty, con = drivers[b]
                g = lambda p: get(con[p][0])
                if ty == '$_AND_': v = And(g('A'), g('B'))
                elif ty == '$_OR_': v = Or(g('A'), g('B'))
                elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
                elif ty == '$_NOT_': v = Not(g('A'))
                elif ty == '$_MUX_': v = If(g('S'), g('B'), g('A'))
                else: raise Exception(f"unsupported cell type {ty}")
            v = Xor(v, F[(t, b)]) if b in sites else v
            val[b] = v; return v
        nxt = {q: get(d) for _, d, q in dffs}
        unlock_bit = get(ports[goal_ports['unlock']]['bits'][0])
        otp_bits = [get(b) for b in ports[goal_ports['otp']]['bits']]
        uotp_bits = [get(b) for b in ports[goal_ports['user_otp']]['bits']]
        mismatch = Or(*[otp_bits[i] != uotp_bits[i] for i in range(len(otp_bits))])
        goal_terms.append(And(unlock_bit, mismatch))
        state = nxt
    s.add(Or(*goal_terms))
    allf = list(F.values())
    return s, F, allf, sites

def solve(m, names, T, k, secret_ports, attacker_ports, goal_ports):
    s, F, allf, sites = build(m, names, T, k, secret_ports, attacker_ports, goal_ports)
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
    m, names = load('fsm5.json', 'wrapper')
    secret_ports = ['lfsr_digit']
    attacker_ports = ['lfsr_latch', 'user_digit', 'user_latch']
    goal_ports = {'unlock': 'unlock', 'otp': 'otp', 'user_otp': 'user_otp_out'}
    rows = []
    for T in (4, 6):
        r, dt, res = solve(m, names, T, 0, secret_ports, attacker_ports, goal_ports)
        print(f"T={T} k=0 (sanity, no faults):", r, f"{dt:.2f}s")
        rows.append(('sanity', T, 0, r, round(dt, 3), res))
    for k in (1, 2):
        for T in (4, 6):
            r, dt, res = solve(m, names, T, k, secret_ports, attacker_ports, goal_ports)
            print(f"T={T} k<={k}:", r, f"{dt:.2f}s", res)
            rows.append(('attack', T, k, r, round(dt, 3), res))
    json.dump(rows, open('fsm_results.json', 'w'))
