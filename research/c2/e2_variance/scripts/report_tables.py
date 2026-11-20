#!/usr/bin/env python3
"""Joins synth_all.json + solve_by_canon_sha.json -> matrix.csv, determinism, summary tables (markdown on stdout)."""
import json, csv, sys, collections
O = sys.argv[1]
S = json.load(open(f'{O}/synth_all.json')); SOL = json.load(open(f'{O}/solve_by_canon_sha.json'))
by = collections.defaultdict(list)
for s in S: by[s['tag']].append(s)
rows = []
for tag, reps in sorted(by.items()):
    b, d, f, o, a, m, k = tag.split('__')
    r1 = reps[0]
    row = dict(build=b, design=d, flow=f, order=o, abc=a, merge=m, keep=k)
    if not all(r['ok'] for r in reps): row.update(status='SYNTH_FAILED'); rows.append(row); continue
    row['sha256_raw'] = r1['sha256']; row['sha256_canon'] = r1['canon_sha256']
    row['deterministic_3x_raw'] = len({r['sha256'] for r in reps}) == 1
    row['deterministic_3x_canon'] = len({r['canon_sha256'] for r in reps}) == 1
    x = SOL.get(f"{r1['canon_sha256']}|{d}", {})
    if 'min_k' in x or 'verdict_k3' in x:
        row.update(status='SOLVED', gates=x['gates'], flops=x['flops'], hist=json.dumps(x['hist'], sort_keys=True),
                   min_flips=(x['min_k'] if x['min_k'] is not None else '>3'), honest_boots=x.get('honest_boots'),
                   distinct_match_nets=x['struct']['distinct_match_nets'], shared_gates_between_match_cones=x['struct']['gates_shared_between_match_cones'])
    else:
        row.update(status='ENGINE_UNSUPPORTED', note=str(x.get('solver') or x.get('error'))[:80], gates_total_cells=x.get('gates_total_cells'))
    rows.append(row)
keys = ['build','design','flow','order','abc','merge','keep','status','gates','flops','hist','min_flips','honest_boots','distinct_match_nets','shared_gates_between_match_cones','sha256_raw','sha256_canon','deterministic_3x_raw','deterministic_3x_canon','note','gates_total_cells']
with open(f'{O}/matrix.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, keys, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
json.dump(rows, open(f'{O}/matrix.json', 'w'), indent=1)
def dist(sel):
    c = collections.Counter(str(r.get('min_flips', r['status'])) for r in rows if sel(r)); return dict(sorted(c.items()))
print('## Determinism'); n = len(by)
print('configs', n, 'raw-identical x3:', sum(all(r['deterministic_3x_raw'] for r in [x]) for x in rows if 'deterministic_3x_raw' in x), 'canon-identical x3:', sum(x['deterministic_3x_canon'] for x in rows if 'deterministic_3x_canon' in x))
print('\n## min flips distribution by design x build')
for d in ('v0','v1','v2'):
    for b in ('apt0.33','conda-formal0.38','conda-eda0.38'): print(d, b, dist(lambda r: r['design']==d and r['build']==b))
print('\n## V2 min flips by factor value (all builds)')
for fac in ('build','flow','order','abc','merge','keep'):
    for v in sorted({r[fac] for r in rows}): print('V2', fac, v, dist(lambda r: r['design']=='v2' and r[fac]==v))
print('\n## V1')
for fac in ('build','flow','order','abc','merge','keep'):
    for v in sorted({r[fac] for r in rows}): print('V1', fac, v, dist(lambda r: r['design']=='v1' and r[fac]==v))
print('\n## cross-build disagreements (same flow/order/abc/merge/keep, different min_flips or canon sha)')
g = collections.defaultdict(dict)
for r in rows: g[(r['design'],r['flow'],r['order'],r['abc'],r['merge'],r['keep'])][r['build']] = r
nd = ns = 0
for k, v in sorted(g.items()):
    mins = {b: x.get('min_flips', x['status']) for b, x in v.items()}; shas = {x.get('sha256_canon') for x in v.values()}
    if len(set(map(str, mins.values()))) > 1: nd += 1; print('VERDICT-DIFF', k, mins)
    if len(shas) > 1: ns += 1
print('groups', len(g), 'with differing min_flips', nd, 'with differing canonical netlist', ns)
