#!/usr/bin/env python3
"""Radius sweep through B3's engine (see run_domains.py). Disc centres: every logic-cell centre plus the
minimum-enclosing-circle centre of every one-cell-per-copy triple (geom_<d>.json). Cell is inside if its centre is within r.
Prints/writes sweep_<d>.json: for r, min events (cap 3, T=6) under allornothing and subset, goals word/ok, plus #distinct domains."""
import sys, os, json, math
sys.path.insert(0, '/tmp/work_layout')
import faultpack as fp, b3pack as bp, b3cell as bpc
from b3pack import Event
D = sys.argv[1]
T, CAP, TMO = 6, 3, 60000
NODES = os.environ.get('LAYOUT_NODES', 'out')
nl = fp.Netlist(f'/tmp/work_layout/nl/{D}_layout.json', D)
G = json.load(open(f'layout_geometry_{D}.json')); GE = json.load(open(f'geom_{D}.json')); C = G['cells']
cg, cq = {}, {}
for y, (cn, t, con) in nl.drivers.items():
    if NODES == 'all' or y in nl.names: cg.setdefault(cn.split('::')[0], set()).add(y)
for cn, d, q in nl.dffs: cq.setdefault(cn, set()).add(q); bpc.CELLOF[q] = cn
for y, (cn, t_, con) in nl.drivers.items(): bpc.CELLOF[y] = cn.split('::')[0]
centres = [(C[k]['cx'], C[k]['cy']) for k in C] + [tuple(t['centre']) for t in GE['triples']]
def ev(cells, subset):
    return Event('d', gates0=set().union(*[cg.get(c, set()) for c in cells]) if cells else set(), d0=set().union(*[cq.get(c, set()) for c in cells]) if cells else set(), subset=subset)
rs = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 15.0]
out = []
for r in rs:
    doms = {}
    for c in centres:
        S = frozenset(k for k in C if math.hypot(C[k]['cx']-c[0], C[k]['cy']-c[1]) <= r + 1e-9)
        doms.setdefault(S, c)
    row = dict(r_um=r, n_distinct_domains=len(doms), max_cells_in_domain=max(len(s) for s in doms))
    for mode in ('allornothing', 'subset'):
        evs = bp.dedup([ev(S, mode == 'subset') for S in doms])
        for goal in ('word', 'ok'):
            kw = dict(goal_out='boot_word', goal_value=0x96) if goal == 'word' else dict(goal_out='boot_ok', goal_value=1)
            row[f'{mode}_{goal}'] = bp.fmt((bpc if mode == 'subset' else bp).min_cost(nl, T, evs, CAP, TMO, **kw))
    out.append(row); print(D, row, flush=True)
json.dump(dict(design=D, T=T, cap=CAP, label='SIMULATED fault-model verdicts on MEASURED geometry; bounded T=6, <=3 events', sweep=out), open(f'sweep_{D}' + ('' if NODES == 'out' else '_allnodes') + '.json', 'w'), indent=1)
