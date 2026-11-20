#!/usr/bin/env python3
"""Feeds layout-derived domains (domains_<d>.json, cell-name groups) into B3's engine
(b3pack.min_cost; B3 code copied unchanged to /tmp/work_layout, not edited) on the sky130 placed-netlist decomposition
(nl/<d>_layout.json from layout_extract.py). T=6, cap=3 events, z3 timeout TMO ms, goals word (boot_word==0x96) and ok (boot_ok==1).
Per family two models:
  allornothing : each domain is one event that forces EVERY primitive output of every cell in the domain to 0 and every flop
                 in it to capture D&0 (B3 'rail' semantics); min over up to 3 such events of the family.
  subset       : each domain is ONE event that may force ANY subset of the domain's primitives/flops to 0 (B3 'dip_subset'
                 restricted to the domain; primitive granularity, finer than a cell: conservative upper bound for the attacker).
Also: explicit cell-level 'copy_triples' (one cell from each compare copy, all-or-nothing, one event).
Usage: cd /tmp/work_layout; python3 run_domains.py v2 out.jsonl
"""
import sys, os, json, time, re, math, itertools
sys.path.insert(0, '/tmp/work_layout')
import faultpack as fp, b3pack as bp, b3cell as bpc
from b3pack import Event

D = sys.argv[1]; OUTF = sys.argv[2]
NODES = os.environ.get('LAYOUT_NODES', 'out')   # 'out' (default): a cell dip forces the cell OUTPUT net to 0; 'all': also its internal primitive nodes
T = int(os.environ.get('T', 6)); CAP = int(os.environ.get('CAP', 3)); TMO = int(os.environ.get('TMO', 60000))
HERE = os.path.dirname(os.path.abspath(__file__))
nl = fp.Netlist(f'/tmp/work_layout/nl/{D}_layout.json', D)
dom = json.load(open(f'research/c4/layout/domains_{D}.json'))
geo = json.load(open(f'research/c4/layout/layout_geometry_{D}.json'))

cell_gates, cell_qs = {}, {}
for y, (cn, t, con) in nl.drivers.items(): (cell_gates.setdefault(cn.split('::')[0], set()).add(y) if (NODES == 'all' or y in nl.names) else None); bpc.CELLOF[y] = cn.split('::')[0]
for cn, d, q in nl.dffs: cell_qs.setdefault(cn, set()).add(q); bpc.CELLOF[q] = cn

def ev(name, cells, subset=False):
    g = set().union(*[cell_gates.get(c, set()) for c in cells]) if cells else set()
    q = set().union(*[cell_qs.get(c, set()) for c in cells]) if cells else set()
    return Event(name, gates0=g, d0=q, subset=subset)

def run(fam, mode, events, goal):
    kw = dict(goal_out='boot_word', goal_value=0x96) if goal == 'word' else dict(goal_out='boot_ok', goal_value=1)
    t0 = time.time()
    r = (bpc if mode == 'subset' else bp).min_cost(nl, T, events, CAP, TMO, **kw)
    row = dict(design=D, family=fam, mode=mode, goal=goal, T=T, cap=CAP, min=bp.fmt(r), status=r['status'], n_domains=len(events),
               events=r.get('events'), sig=r.get('sig'), secs=round(time.time() - t0, 1), z3_timeout_ms=TMO)
    open(OUTF, 'a').write(json.dumps(row) + '\n'); print(fam, mode, goal, row['min'], row['secs'], flush=True)

def families():
    for f, groups in dom['families'].items():
        if f == 'rail_all': continue
        yield f, groups

done = set()
if os.path.exists(OUTF):
    for l in open(OUTF): r = json.loads(l); done.add((r['family'], r['mode'], r['goal']))
only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
# baseline: whole design
for goal in ('word', 'ok'):
    if ('rail_all', 'allornothing', goal) not in done: run('rail_all', 'allornothing', [ev('all', dom['families']['rail_all']['all'])], goal)
    if ('rail_all', 'subset', goal) not in done: run('rail_all', 'subset', [ev('all', dom['families']['rail_all']['all'], True)], goal)
for f, groups in families():
    if only and f not in only: continue
    for mode in ('allornothing', 'subset'):
        evs = [ev(f'{f}:{g}', cs, subset=(mode == 'subset')) for g, cs in groups.items()]
        evs = bp.dedup(evs)
        for goal in ('word', 'ok'):
            if (f, mode, goal) in done: continue
            run(f, mode, evs, goal)
# explicit cell-level triples: one cell from each compare copy (or each copy of V1), one event, all-or-nothing, per triple
copies = geo['copies']
if copies and not only or (only and 'copy_triples' in only):
    names = sorted(copies)
    for goal in ('word', 'ok'):
        if ('copy_triples', 'cell_level', goal) in done: continue
        res = {}
        for combo in itertools.product(*[copies[c] for c in names]):
            e = ev('trip:' + '+'.join(combo), combo)
            kw = dict(goal_out='boot_word', goal_value=0x96) if goal == 'word' else dict(goal_out='boot_ok', goal_value=1)
            r = bp.min_cost(nl, T, [e], 1, TMO, **kw)
            res['+'.join(combo)] = dict(min=bp.fmt(r), sig=r.get('sig'), events=r.get('events'))
        open(OUTF, 'a').write(json.dumps(dict(design=D, family='copy_triples', mode='cell_level', goal=goal, T=T, cap=1, results=res)) + '\n')
        print('copy_triples', goal, sum(1 for v in res.values() if v['min'] == '1'), 'of', len(res), 'attack with 1 event', flush=True)
