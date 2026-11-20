#!/usr/bin/env python3
"""Unit test / training agreement of predictor.py on TRAINING netlists only.
Spike V0/V1/V2 vs research/c3/m1/m1_all_masks.csv (columns v0/v1/v2 spike ONLY); regenerated conda-0.38-plain V4b/V5/V6h
vs research/c3/v456/data/mask_*.jsonl. Held-out data is never read."""
import csv, json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from predictor import predict
P = ''
rows = list(csv.DictReader(open(P + 'research/c3/m1/m1_all_masks.csv')))
res = []   # (design, mask, truth, rec)
for d in ('v0', 'v1', 'v2'):
    for r in rows:
        m = int(r['mask_hex'], 16)
        res.append((d + '_spike', m, int(r[f'{d}_spike_min_flips']),
                    predict(P + f'reference/spike_netlists/{d}.json', d, mask=m)))
W = os.environ.get('PRE_NL', '/tmp/work_pre/nl')
for d, f in (('v4b', 'mask_v4b'), ('v5', 'mask_v5'), ('v6h', 'mask_v6h')):
    for l in open(P + f'research/c3/v456/data/{f}.jsonl'):
        j = json.loads(l)
        if j.get('status') != 'MEASURED': continue
        res.append((d, j['mask'], j['min'], predict(f'{W}/{d}_conda.json', d, mask=j['mask'])))
json.dump([(a, b, c, {k: v for k, v in r.items() if k in ('lb', 'est', 'ub_direct', 'pred', 'flag')}) for a, b, c, r in res],
          open('/tmp/work_pre/train_results.json', 'w'))
bad = 0
by = collections.defaultdict(list)
for d, m, t, r in res: by[d].append((m, t, r))
for d, L in by.items():
    n = len(L); ex = sum(r['pred'] == t for m, t, r in L); w1 = sum(abs(r['pred'] - t) <= 1 for m, t, r in L)
    lbviol = sum(r['lb'] > t for m, t, r in L)           # LB must never exceed truth
    ubviol = sum(r['est'] is not None and r['est'] < t for m, t, r in L)   # verified UB must never be below truth
    over3 = sum(r['pred'] >= 3 and t == 1 for m, t, r in L)
    unc = sum(r['flag'] == 'uncovered' for m, t, r in L)
    print(f'{d:10s} n={n} exact={ex} ({100*ex/n:.1f}%) within1={w1} ({100*w1/n:.1f}%) LB>truth={lbviol} EST<truth={ubviol} pred>=3&truth=1:{over3} uncovered={unc}')
    bad += lbviol + ubviol
print('SOUNDNESS VIOLATIONS (LB>truth or verified EST<truth):', bad)
sys.exit(1 if bad else 0)
