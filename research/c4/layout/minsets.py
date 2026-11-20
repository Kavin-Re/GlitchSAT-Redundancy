#!/usr/bin/env python3
"""Enumerate ALL minimal cell sets that ONE dip event (cell-level subset, B3 'dip_subset' semantics,
T=6) needs for the goal, on the layout netlist. Uses b3cell.py (B3 engine + per-cell subset patch). Writes minsets_<d>.json with, per set,
the geometry (min enclosing circle of cell centres, bbox, rows, rails, others inside)."""
import sys, os, json, math, itertools, collections
sys.path.insert(0, '/tmp/work_layout'); sys.path.insert(0, '.')
import faultpack as fp, b3cell as bpc
from b3cell import Event
from z3 import PbLe, Or, Not, sat, is_true
from geom_report import mec
D = sys.argv[1]; MAXK = int(sys.argv[2]) if len(sys.argv) > 2 else 4
nl = fp.Netlist(f'/tmp/work_layout/nl/{D}_layout.json', D)
G = json.load(open(f'layout_geometry_{D}.json')); C = G['cells']
cg, cq = collections.defaultdict(set), collections.defaultdict(set)
NODES = os.environ.get('LAYOUT_NODES', 'out')
for y, (cn, t, con) in nl.drivers.items():
    c = cn.split('::')[0]; bpc.CELLOF[y] = c
    if NODES == 'all' or y in nl.names: cg[c].add(y)
for cn, d, q in nl.dffs: cq[cn].add(q); bpc.CELLOF[q] = cn
out = {}
for goal in ('word', 'ok'):
    kw = dict(goal_out='boot_word', goal_value=0x96) if goal == 'word' else dict(goal_out='boot_ok', goal_value=1)
    ev = [Event('dip', gates0=set().union(*cg.values()), d0=set().union(*cq.values()), subset=True)]
    s, A, cost, inp = bpc.build(nl, 6, ev, **kw); s.set('timeout', 60000)
    s.add(PbLe([(c, 1) for c in cost], 1))
    subs = {}
    for v in bpc.SUBS: subs[str(v)] = v           # name s_c_<t>_0_<cell>
    bycyc = collections.defaultdict(dict)
    for n, v in subs.items():
        _, _, t, ei, cell = n.split('_', 4); bycyc[int(t)][cell] = v
    found = []   # (t, frozenset cells)
    for k in range(1, MAXK + 1):
        s.push(); s.add(PbLe([(v, 1) for v in subs.values()], k))
        # distinct cell count per cycle <=k is implied since only one event cycle is active; cells shared by name across prims
        while s.check() == sat:
            m = s.model(); t_act = [t for (t, ei), a in A.items() if is_true(m.eval(a, model_completion=True))][0]
            cells = frozenset(c for c, v in bycyc[t_act].items() if is_true(m.eval(v, model_completion=True)))
            sig = m.eval(inp['sig'], model_completion=True).as_long()
            if not any(f[1] < cells or f[1] == cells and f[0] == t_act for f in found if f[0] == t_act):
                found.append((t_act, cells, sig))
            # block this cell set at this cycle (and supersets) -- require at least one selected cell outside the set or different cycle
            s.add(Or(Not(A[(t_act, 0)]), *[bycyc[t_act][c] == False if False else Not(bycyc[t_act][c]) for c in cells]) if False else
                  Or(Not(A[(t_act, 0)]), *[Not(bycyc[t_act][c]) for c in cells]))
            if len(found) > 400: break
        s.pop()
        if len(found) > 400: break
        # keep only minimal sets so far; further k only finds supersets of blocked ones, i.e. not-yet-seen incomparable sets
    # reduce to minimal sets over all cycles
    sets = {}
    for t, cs, sig in found:
        sets.setdefault(cs, []).append((t, sig))
    mins = [cs for cs in sets if not any(o < cs for o in sets)]
    res = []
    for cs in sorted(mins, key=lambda x: (len(x), sorted(x))):
        pts = [(C[c]['cx'], C[c]['cy']) for c in cs]; r, cen = mec(pts)
        bx = (min(C[c]['x'] for c in cs), min(C[c]['y'] for c in cs), max(C[c]['x'] + C[c]['w'] for c in cs), max(C[c]['y'] + C[c]['h'] for c in cs))
        ins = [k for k in C if math.hypot(C[k]['cx'] - cen[0], C[k]['cy'] - cen[1]) <= r + 1e-9 and k not in cs]
        res.append(dict(cells=sorted(cs), n=len(cs), cycles=sorted({t for t, _ in sets[cs]}), example_sig=sets[cs][0][1], r_um=round(r, 3), centre=[round(cen[0], 3), round(cen[1], 3)],
                        bbox_w_h=[round(bx[2] - bx[0], 3), round(bx[3] - bx[1], 3)], rows=sorted({C[c]['row'] for c in cs}),
                        vpwr_rails=sorted({C[c]['vpwr_y'] for c in cs}), others_in_circle=len(ins), flops_in_circle=sum(C[k]['kind'] == 'flop' for k in ins),
                        copy_members=sorted({c.split('/')[0] for c in cs if '/' in c})))
    out[goal] = res
    print(D, goal, 'minimal one-event cell sets (<=%d cells):' % MAXK, len(res), 'sizes', collections.Counter(r['n'] for r in res))
    for r in sorted(res, key=lambda r: r['r_um'])[:5]: print('   ', r['cells'], 'r', r['r_um'], 'rows', r['rows'], 'others', r['others_in_circle'], 'cycles', r['cycles'])
json.dump(dict(design=D, label='MEASURED geometry; set enumeration = z3 verdicts (SIMULATED fault model, T=6, one cell-level subset dip event); enumeration limited to <=%d cells and 400 sets' % MAXK, minimal_sets=out), open(f'minsets_{D}' + ('' if NODES == 'out' else '_allnodes') + '.json', 'w'), indent=1)
