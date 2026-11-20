#!/usr/bin/env python3
"""Re-runs B3 matrix cells (z3, T=6, cap 3) from the stored netlists and compares with ../b3/matrix_T6.jsonl.
usage: check_b3_matrix.py [--designs v2,v2_apt033,...] [--models rail_all,...] [--procs 4]    (default: ALL 182 cells, ~2-3 min on 4 cores)
Netlists: v0/v1/v2 = ../../../reference/spike_netlists/<d>.json ; v?_apt033, v5_apt033 = ./nl/<d>.json. Needs python3 + z3-solver."""
import sys, os, json, argparse
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); B3 = os.path.join(HERE, '..', 'b3'); sys.path.insert(0, B3)
def path(d): return os.path.join(HERE, '..', '..', '..', 'reference', 'spike_netlists', d + '.json') if d in ('v0', 'v1', 'v2') else os.path.join(HERE, 'nl', d + '.json')
def cell(a):
    d, m, g, T, cap, tmo = a
    import faultpack as fp, b3pack as bp
    nl = fp.Netlist(path(d), d.split('_')[0]); ev = bp.models(nl)[m]
    kw = dict(goal_out='boot_word', goal_value=0x96) if g == 'word' else dict(goal_out='boot_ok', goal_value=1)
    return bp.fmt(bp.min_cost(nl, T, ev, cap, tmo, **kw))
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--designs'); ap.add_argument('--models'); ap.add_argument('--procs', type=int, default=4)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(B3, 'matrix_T6.jsonl'))]
    if a.designs: rows = [r for r in rows if r['design'] in a.designs.split(',')]
    if a.models: rows = [r for r in rows if r['model'] in a.models.split(',')]
    jobs = [(r['design'], r['model'], r['goal'], r['T'], r['cap'], r['z3_timeout_ms']) for r in rows]
    with ProcessPoolExecutor(a.procs) as ex: got = list(ex.map(cell, jobs))
    bad = [(r['design'], r['model'], r['goal'], r['min'], g) for r, g in zip(rows, got) if r['min'] != g]
    print('cells', len(rows), 'agree', len(rows) - len(bad), 'DIFFER', len(bad))
    for b in bad: print('  DIFFER (design, model, goal, committed, rerun):', b)
    sys.exit(1 if bad else 0)
