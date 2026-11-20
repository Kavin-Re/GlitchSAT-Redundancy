#!/usr/bin/env python3
"""Independent explicit-state check (no z3, no sby) of the FREE per-cycle input model.
State = flop vector (<=2^8); at every cycle sig is chosen freely among the 255 values != 0xC3 (bit-parallel lanes);
up to K single-cycle flips on any gate-output/flop-Q net per cycle. Computes the exact reachable set of
(flop state, flips used <= K) as a FIXPOINT (so it covers any number of cycles), and reports whether a state with
boot_word == 0x96 observed (flips applied on observed nets) is reachable. Usage: explicit_state_free.py netlist.json top K [maxT]"""
import json, sys, itertools, time
path, top, K = sys.argv[1], sys.argv[2], int(sys.argv[3])
MAXT = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
m = json.load(open(path))['modules'][top]
KEY = 0xC3
LANES = [s for s in range(256) if s != KEY]; NL = len(LANES); ALL = (1 << NL) - 1
sigl = [sum(1 << j for j, s in enumerate(LANES) if (s >> i) & 1) for i in range(8)]
gates, dffs, init = {}, [], {}
for cn, c in m['cells'].items():
    con = c['connections']
    if c['type'] == '$_DFF_P_': dffs.append((con['D'][0], con['Q'][0]))
    else: gates[con['Y'][0]] = (c['type'], {p: v[0] for p, v in con.items() if p != 'Y'})
for n, x in m['netnames'].items():
    iv = x['attributes'].get('init')
    if iv:
        for i, b in enumerate(reversed(iv)): init[x['bits'][i]] = (b == '1')
qs = [q for _, q in dffs]
sigmap = {b: sigl[i] for i, b in enumerate(m['ports']['sig']['bits'])}
out = m['ports']['boot_word']['bits']
sites = qs + list(gates)
order, seen = [], set(qs) | set(sigmap)
def vis(b):
    if not isinstance(b, int) or b in seen: return
    seen.add(b); vis_in = gates[b][1]
    for v in vis_in.values(): vis(v)
    order.append(b)
for d, _ in dffs: vis(d)
for b in out: vis(b)
def step(state, flips):
    """state: tuple of bits per qs; flips: frozenset of nets. returns (next_state tuple of lane-masks, out lane-masks)"""
    v = {}
    for q, s in zip(qs, state): v[q] = ALL if s else 0
    for q in qs:
        if q in flips: v[q] ^= ALL
    def g(b):
        if b in ('0', 'x', 'z'): return 0
        if b == '1': return ALL
        if b in sigmap: return sigmap[b]
        return v[b]
    for b in order:
        t, p = gates[b]
        if t == '$_AND_': r = g(p['A']) & g(p['B'])
        elif t == '$_OR_': r = g(p['A']) | g(p['B'])
        elif t == '$_XOR_': r = g(p['A']) ^ g(p['B'])
        elif t == '$_NOT_': r = ALL ^ g(p['A'])
        elif t == '$_MUX_': S = g(p['S']); r = (g(p['B']) & S) | (g(p['A']) & (ALL ^ S))
        else: raise SystemExit('cell ' + t)
        v[b] = r ^ (ALL if b in flips else 0)
    nxt = [g(d) for d, _ in dffs]
    o = [g(b) for b in out]
    return nxt, o
GOAL = 0x96
def hit(o):
    r = ALL
    for i, x in enumerate(o): r &= x if (GOAL >> i) & 1 else ALL ^ x
    return r
st0 = tuple(init.get(q, False) for q in qs)
frontier = {(st0, 0)}; seenS = set(frontier); t0 = time.time(); T = 0
subsets = [frozenset()] + [frozenset(c) for r in range(1, K + 1) for c in itertools.combinations(sites, r)]
cache = {}
found = None
while frontier and T < MAXT and not found:
    new = set()
    for (s, used) in frontier:
        for fl in subsets:
            if used + len(fl) > K: continue
            nxt, o = step(s, fl)
            if hit(o):
                found = (T, s, sorted(fl)); break
            # successor states: one per distinct lane combination of next-state bits
            combos = set()
            for lane in range(NL): combos.add(tuple(bool((x >> lane) & 1) for x in nxt))
            for c in combos:
                key = (c, used + len(fl))
                if key not in seenS: seenS.add(key); new.add(key)
        if found: break
    frontier = new; T += 1
print(json.dumps(dict(netlist=path, top=top, K=K, goal_hit_reachable=bool(found), at_cycle=found[0] if found else None,
                      fixpoint_reached=(not frontier and not found), cycles_explored=T, reachable_state_used_pairs=len(seenS),
                      sites=len(sites), seconds=round(time.time() - t0, 1))))
