#!/usr/bin/env python3
"""Computes pre-registered criteria from cells_*.csv; writes cells_all.csv and analysis.txt"""
import csv, collections, sys
R = []
for g in ('e2', 'r20', 'm1'):
    R += list(csv.DictReader(open(f'research/c4/test/cells_{g}.csv')))
def I(x): return None if x in ('', 'None') else int(x)
for r in R:
    r['s'] = min(int(r['solver_min']), 4); r['lb_'] = I(r['lb']); r['est_'] = I(r['est']); r['p'] = I(r['pred']); r['nc'] = int(r['n_configs'])
w = csv.DictWriter(open('research/c4/test/cells_all.csv', 'w', newline=''), fieldnames=list(R[0])[:-5] if False else [k for k in R[0] if k not in ('s','lb_','est_','p','nc')])
w.writeheader(); [w.writerow({k: v for k, v in r.items() if k not in ('s','lb_','est_','p','nc')}) for r in R]
out = []
def P(*a): out.append(' '.join(str(x) for x in a))
def crit(S, name, weight=False):
    wt = (lambda r: r['nc']) if weight else (lambda r: 1)
    n = sum(wt(r) for r in S)
    if not n: return
    lbv = [r for r in S if r['lb_'] > r['s']]
    ubv = [r for r in S if r['est_'] is not None and r['est_'] < r['s']]
    ex = sum(wt(r) for r in S if r['p'] == r['s']); w1 = sum(wt(r) for r in S if abs(r['p'] - r['s']) <= 1)
    c4 = [r for r in S if r['p'] >= 3 and r['s'] == 1]; c4b = [r for r in S if r['p'] >= 3 and r['s'] <= 2]
    c5 = [r for r in S if r['p'] == 1 and r['s'] >= 2]
    br = [r for r in S if r['s'] <= 2 and r['s'] >= 1]
    rec = sum(wt(r) for r in br if r['p'] <= 2)
    P(f'## {name} (n={n}{" config-weighted" if weight else " cells"})')
    P(f' C1 lb>solver: {sum(wt(r) for r in lbv)}; est<solver: {sum(wt(r) for r in ubv)}')
    P(f' C2 exact: {ex}/{n} = {100*ex/n:.2f}%   C3 within1: {w1}/{n} = {100*w1/n:.2f}%')
    P(f' C4 pred>=3 & solver==1: {sum(wt(r) for r in c4)}  (pred>=3 & solver<=2: {sum(wt(r) for r in c4b)})')
    P(f' C5 pred==1 & solver>=2: {sum(wt(r) for r in c5)}')
    nb = sum(wt(r) for r in br)
    P(f' C6 breakable (solver 1..2) recall pred<=2: {rec}/{nb}' + (f' = {100*rec/nb:.2f}%' if nb else ' (none)'))
    P(f' flags: {dict(collections.Counter(r["flag"] for r in S))}')
    return dict(lbv=lbv, ubv=ubv, n=n, ex=ex, w1=w1, c4=c4, c5=c5, rec=rec, nb=nb)
groups = collections.defaultdict(list)
for r in R: groups[r['group']].append(r)
tot = crit(R, 'POOLED (all unique cells)')
crit(R, 'POOLED, E2 weighted by #configs', True)
for g, S in groups.items(): crit(S, g)
# E2 per design/build/flow
e2 = groups['E2']
def cfgkey(r):
    t = r['example_cfg'].split('__'); return t
# per-design for E2 (design from top)
for d in ('v0', 'v1', 'v2'): crit([r for r in e2 if r['top'] == d], 'E2 ' + d)
# confusion matrix
def conf(S, name):
    P(f'### confusion {name}: rows solver, cols pred')
    ps = sorted({r['p'] for r in S}); ss = sorted({r['s'] for r in S})
    P('solver\\pred ' + ' '.join(f'{p:>5}' for p in ps))
    for s in ss: P(f'{s:>11} ' + ' '.join(f'{sum(1 for r in S if r["s"]==s and r["p"]==p):>5}' for p in ps))
conf(R, 'POOLED')
for g, S in groups.items(): conf(S, g)
# failures
P('## FAILURES (pred != solver)')
fails = [r for r in R if r['p'] != r['s']]
P('count', len(fails))
cause = collections.Counter()
for r in fails:
    c = ('over: est>solver, flag=' + r['flag']) if r['p'] > r['s'] else ('under: pred<solver flag=' + r['flag'])
    cause[(r['group'], c, r['s'], r['p'])] += 1
for k, v in sorted(cause.items()): P(k, v)
P('## failure details')
for r in fails: P(r['group'], r['cell'], r['mask'], 'T', r['T'], 'solver', r['s'], 'lb', r['lb'], 'est', r['est'], 'pred', r['p'], r['flag'], 'cfg', r['example_cfg'])
P('## E2 failures by flow/abc/order/merge')
c2 = collections.Counter()
for r in e2:
    if r['p'] != r['s']:
        t = r['example_cfg'].split('__'); c2[(t[1], t[0], t[2], t[3], t[4], t[5], t[6], 'solver', r['s'], 'pred', r['p'])] += r['nc']
for k, v in sorted(c2.items()): P(k, v)
# timing
tp = sum(float(r['pred_s']) for r in R); P('## predictor time (summed per-cell wall, single process each): total', round(tp, 1), 's; by group', {g: round(sum(float(r['pred_s']) for r in S), 1) for g, S in groups.items()})
open('research/c4/test/analysis.txt', 'w').write('\n'.join(out))
print('\n'.join(out))
