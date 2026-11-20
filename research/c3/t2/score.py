#!/usr/bin/env python3
"""usage: score.py res.jsonl  -> per-suite before/after mutation score + survivor list."""
import json, sys
sys.path.insert(0, '/home/user/project/research/c3/mt'); import mutate as m
rows = [json.loads(l) for l in open(sys.argv[1])]
alljobs = [(x[0], s) for x in m.M for s, _ in m.targets(x[1])]
done = {(r['id'], r['suite']): r for r in rows}
for suite in ('root', 'product'):
    jobs = [j for j in alljobs if j[1] == suite]; rs = [done[j] for j in jobs if j in done]
    notrun = [j[0] for j in jobs if j not in done]
    na = [r['id'] for r in rs if r['old'] == 'NOT_APPLIED']; rs = [r for r in rs if r['old'] != 'NOT_APPLIED']
    det = lambda s: s in ('KILLED', 'TIMEOUT')
    kb = sum(r['old'] == 'KILLED' for r in rs); tb = sum(r['old'] == 'TIMEOUT' for r in rs)
    ka = sum(r['old'] == 'KILLED' or (r['old'] != 'KILLED' and r['new'] == 'KILLED') for r in rs)
    ta = sum(1 for r in rs if r['old'] == 'TIMEOUT' and r['new'] != 'KILLED') ; kn = ka - kb
    n = len(rs)
    print(f"{suite}: run={n} not_run={len(notrun)} {notrun} not_applied={na}")
    print(f"  before: killed={kb} timeout(hang)={tb} survived={sum(r['old']=='SURVIVED' for r in rs)} -> killed/run={kb/n:.1%}, killed+hang/run={(kb+tb)/n:.1%}")
    surv_after = [r['id'] for r in rs if r['old'] in ('SURVIVED', 'TIMEOUT') and r['new'] != 'KILLED']
    ndet = sum(1 for r in rs if r['old'] == 'KILLED' or r['new'] == 'KILLED' or r['old'] == 'TIMEOUT' or r['new'] == 'TIMEOUT')
    print(f"  after:  killed={ka} (new tests add {kn}) killed+hang={sum(1 for r in rs if r['old']=='KILLED' or r['new']=='KILLED' or 'TIMEOUT' in (r['old'], r['new']))}/{n} = {ka/n:.1%} killed, {ndet/n:.1%} incl. hangs")
    print('  survivors after:', [(r['id'], r['old'], r['new']) for r in rs if r['old'] != 'KILLED' and r['new'] != 'KILLED'])
