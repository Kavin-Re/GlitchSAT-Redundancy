#!/usr/bin/env python3
"""design x netlist x fault model -> min cost at T=6 (z3, faultpack). Writes matrix_T6.json/.md.
usage: python3 run_matrix.py [--cap 4] [--timeout-ms 600000] [--models a,b] [--out matrix_T6]"""
import sys, os, json, time, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import faultpack as fp
ROOT = os.environ.get('PROJ', '/home/user/project')
NETLISTS = {'spike': lambda d: os.path.join(ROOT, 'reference', 'spike_netlists', f'{d}.json'),
            'apt033': lambda d: os.path.join(HERE, 'netlists', f'{d}_apt033.json'),
            'conda038': lambda d: os.path.join(HERE, 'netlists', f'{d}_conda038.json')}
ap = argparse.ArgumentParser(); ap.add_argument('--cap', type=int, default=4); ap.add_argument('--timeout-ms', type=int, default=600000)
ap.add_argument('--cycles', type=int, default=6)
ap.add_argument('--models', default=','.join(fp.MODELS)); ap.add_argument('--out', default=os.path.join(HERE, 'matrix_T6'))
a = ap.parse_args()
rows = []
if os.path.exists(a.out + '.json'): rows = json.load(open(a.out + '.json'))['rows']
done = {(r['model'], r['netlist'], r['design']) for r in rows}
for model in a.models.split(','):
    for nlname, pf in NETLISTS.items():
        for d in ['v0', 'v1', 'v2']:
            if (model, nlname, d) in done: continue
            nl = fp.Netlist(pf(d), d); t0 = time.time()
            r = fp.min_cost(nl, a.cycles, fp.MODELS[model], a.cap, a.timeout_ms)
            row = dict(design=d, netlist=nlname, model=model, T=a.cycles, min=fp.fmt(r), status=r['status'], cap=a.cap,
                       secs=round(time.time() - t0, 1), stats=nl.stats(),
                       faults=[(t, fp.describe(nl, s), e) for t, s, e in r.get('faults', [])], attacker_sig=r.get('inputs', {}).get('sig'))
            rows.append(row); print(model, nlname, d, row['min'], row['secs'], flush=True)
            json.dump(dict(label='MEASURED', rows=rows), open(a.out + '.json', 'w'), indent=1)
# markdown table
models = a.models.split(',')
L = ['| model | ' + ' | '.join(f'{n}:{d}' for n in NETLISTS for d in ['v0', 'v1', 'v2']) + ' |', '|---|' + '---|' * 9]
for m in models:
    cells = []
    for n in NETLISTS:
        for d in ['v0', 'v1', 'v2']:
            r = [x for x in rows if x['model'] == m and x['netlist'] == n and x['design'] == d][0]
            cells.append(r['min'])
    L.append(f'| {m} | ' + ' | '.join(cells) + ' |')
open(a.out + '.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
