#!/usr/bin/env python3
"""Measure runtime with reduction none / coi / full (UNSAT case: V2 spike netlist, k=2) at several horizons."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import glitchsat as g
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
nl = g.Netlist(os.path.join(ROOT, 'reference/spike_netlists/v2.json'), 'v2')
rows = []
for N in (4, 6, 8, 10):
    for red in ('none', 'coi', 'full'):
        t = time.time(); v, info, res = g.solve(nl, N, 2, timeout_ms=150000, reduce=red); dt = time.time() - t
        rows.append(dict(design='v2(spike netlist)', k=2, cycles=N, reduce=red, verdict=v, total_s=round(dt, 2),
                         fault_vars=info['sites_modelled'], fault_vars_unreduced=info['sites_total'], label='MEASURED'))
        print(rows[-1], flush=True)
json.dump(rows, open(os.path.join(ROOT, 'results', 'reduction_benchmark.json'), 'w'), indent=2)
