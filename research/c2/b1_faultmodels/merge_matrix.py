#!/usr/bin/env python3
"""Merge the partial matrix json files into matrix_T6.json/.md. usage: merge_matrix.py out_prefix in1.json ..."""
import json, sys
out = sys.argv[1]; rows = {}
for f in sys.argv[2:]:
    for r in json.load(open(f))['rows']: rows[(r['model'], r['netlist'], r['design'])] = r
models = []; 
for k in rows:
    if k[0] not in models: models.append(k[0])
cols = [(n, d) for n in ['spike', 'apt033', 'conda038'] for d in ['v0', 'v1', 'v2']]
L = ['| model | ' + ' | '.join(f'{n}:{d}' for n, d in cols) + ' |', '|---|' + '---|' * 9]
for m in models:
    L.append(f'| {m} | ' + ' | '.join(rows[(m, n, d)]['min'] if (m, n, d) in rows else 'not run' for n, d in cols) + ' |')
json.dump(dict(label='MEASURED', T=6, rows=list(rows.values())), open(out + '.json', 'w'), indent=1)
open(out + '.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
