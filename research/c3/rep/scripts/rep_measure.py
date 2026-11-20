#!/usr/bin/env python3
"""REP: min fault cost to make boot_word==0x96 with sig != 0xC3, N=6, per counting rule. Uses glitchsat.build() semantics (flip var per (cycle,net)),
adds my own weighted cardinality. Rules: unit (stem flip=1), fanout_pins (cost = # sink pins incl. output-port bits), fanout_gates (cost = # sink pins excluding output ports)."""
import sys, glob, os, time, csv, collections
sys.path.insert(0, '/tmp/work_rep/scripts')
import glitchsat as g
from z3 import PbLe, sat, unsat
N = 6; KMAX = 6; TO = 120000
def weights(nl):
    pins = collections.Counter(); outp = collections.Counter()
    for o, (cn, t, con) in nl.drivers.items():
        for p, v in con.items():
            if p != 'Y' and isinstance(v[0], int): pins[v[0]] += 1
    for q, d in nl.dq.items():
        if isinstance(d, int): pins[d] += 1
    for p, v in nl.ports.items():
        if v['direction'] == 'output':
            for b in v['bits']:
                if isinstance(b, int): outp[b] += 1
    return pins, outp
def mincost(nl, wfun):
    s, F, inputs, info = g.build(nl, N)
    s.set('timeout', TO)
    items = [(f, max(1, wfun(b))) for (t, b), f in F.items()]
    t0 = time.time()
    for k in range(0, KMAX + 1):
        s.push(); s.add(PbLe(items, k)); r = s.check(); s.pop()
        if r == sat: return k, 'MEASURED', round(time.time() - t0, 2)
        if r != unsat: return None, 'UNKNOWN_TIMEOUT(k=%d)' % k, round(time.time() - t0, 2)
    return None, 'NOT_FOUND_UP_TO_%d' % KMAX, round(time.time() - t0, 2)
rows = []
for p in sorted(glob.glob('/tmp/work_rep/net/*.json')):
    name = os.path.basename(p)[:-5]; top = name.split('_')[0]
    nl = g.Netlist(p, top); pins, outp = weights(nl)
    r = dict(netlist=name, sha16=g.sha(p), gates=len(nl.drivers), flops=len(nl.dffs))
    for rule, wf in (('unit', lambda b: 1), ('fanout_pins', lambda b: pins[b] + outp[b]), ('fanout_gates', lambda b: pins[b])):
        k, st, rt = mincost(nl, wf); r[rule] = k if k is not None else st; r[rule + '_status'] = st; r[rule + '_s'] = rt
    rows.append(r); print(r, flush=True)
with open('/tmp/work_rep/rep_results.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
