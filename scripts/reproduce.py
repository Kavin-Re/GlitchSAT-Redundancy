#!/usr/bin/env python3
"""Reproduce V0/V1/V2 results (MEASURED) into results/. Sweeps k=0..3 at N=6 cycles on two netlists per design:
 (a) synthesized from rtl/ by scripts/synth.sh (flow 'plain' and 'opt'); (b) the spike's original netlists."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import glitchsat as g
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
N = int(os.environ.get('CYCLES', 6)); KS = (0, 1, 2, 3)
rows = []
for src, flow in (('rtl', 'plain'), ('rtl', 'opt'), ('spike', 'given-netlist')):
    for d in ('v0', 'v1', 'v2'):
        for k in KS:
            path = f'rtl/{d}.v' if src == 'rtl' else f'reference/spike_netlists/{d}.json'
            path = os.path.join(os.path.dirname(R), path)
            out = os.path.join(R, 'reproduce', f'{d}_{src}_{flow}_k{k}.json')
            r = g.run_check(path, d, k, N, out, flow=flow if src == 'rtl' else 'plain')
            rows.append(dict(design=d, netlist=f'{src}/{flow}', k=k, cycles=N, verdict=r['verdict'], min_faults=r.get('min_faults'),
                             faults=[(f['net'], f['cycle']) for f in r.get('faults', [])], runtime_s=r['runtime_s']['solve_and_minimize'],
                             honest_key_boots=r['honest_key_boots_fault_free'], label='MEASURED'))
            print(rows[-1], flush=True)
json.dump(dict(label='MEASURED', cycles=N, note=g.NOTE.format(k='<=3', n=N), rows=rows), open(os.path.join(R, 'reproduce_summary.json'), 'w'), indent=2)
