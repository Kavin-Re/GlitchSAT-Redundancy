#!/usr/bin/env python3
"""Sweep driver: 4 parallel chains; each (design,route,k) chain walks cycles ascending, 600 s hard timeout per run;
after a TIMEOUT the larger cycles of that chain are recorded as NOT_RUN (not measured)."""
import subprocess, json, time, os, sys
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__)); TO = 600   # results/deep of this checkout
ROOT = os.path.dirname(os.path.dirname(D))                  # repository root: runs use repo-relative paths, so logs and JSON hold no machine path
R = os.path.relpath(D, ROOT)
def run(design, route, k, N):
    tag = f'{design}_{route}_k{k}_c{N}'
    out = f'{R}/json/{tag}.json'; log = f'{D}/logs/{tag}.log'
    cmd = ['python3', '-I', f'{R}/run_one.py', f'{R}/work/nl/{design}_{route}.json', design, str(k), str(N), out]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TO, cwd=ROOT)
        wall = time.time() - t0; txt = p.stdout + p.stderr
        status = 'DONE' if p.returncode == 0 else 'ERROR'
    except subprocess.TimeoutExpired as e:
        wall = time.time() - t0; txt = 'TIMEOUT after %d s\n' % TO; status = 'TIMEOUT'
    open(log, 'w').write('CMD: ' + ' '.join(cmd) + '\n' + txt + f'\nwall_s={wall:.2f}\n')
    row = dict(design=design, route=route, k=k, cycles=N, status=status, wall_s=round(wall, 2))
    if status == 'DONE':
        j = json.load(open(os.path.join(ROOT, out)))
        row.update(verdict=j['verdict'], min_faults=j.get('min_faults'), solve_s=j['runtime_s']['solve_and_minimize'],
                   faults=[(f['net'], f['cycle']) for f in j.get('faults', [])], honest=j['honest_key_boots_fault_free'])
    print(row, flush=True); return row
def chain(design, route, k, cycles):
    rows = []; dead = False
    for N in cycles:
        if dead:
            rows.append(dict(design=design, route=route, k=k, cycles=N, status='NOT_RUN', note='smaller bound already timed out')); continue
        r = run(design, route, k, N); rows.append(r)
        if r['status'] != 'DONE': dead = True
    return rows
if __name__ == '__main__':
    part = sys.argv[1]
    if part == 'main':
        chains = [(d, r, k, [8, 10, 12, 16, 20]) for d in ('v2', 'v1', 'v0') for r in ('spike', 'rtl') for k in (3, 2, 1)]
    else:
        chains = [('v2', 'spike', k, [4, 6]) for k in (4, 5)]
    with ThreadPoolExecutor(4) as ex:
        res = [r for c in ex.map(lambda a: chain(*a), chains) for r in c]
    json.dump(res, open(f'{D}/sweep_{part}.json', 'w'), indent=1)
