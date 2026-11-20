"""Merges: T2 baseline (research/c3/t2/results_t2.jsonl) with T3 reruns on the counter engine (res_*.jsonl).
Rule: a (mutant,suite) rerun here replaces the T2 row. A T2 row that was SURVIVED/TIMEOUT-and-not-killed-by-new-tests is NOT rerun (it can
only stay a survivor or become killed, so it cannot lower the score) and is carried over unchanged. Prints score vs T2."""
import json, glob, sys
sys.path.insert(0, 'research/c4/t3'); import mt_override as m
t2 = {(r['id'], r['suite']): r for r in map(json.loads, open('research/c3/t2/results_t2.jsonl'))}
new = {}
for f in sorted(glob.glob('/tmp/work_t3/res_*.jsonl')):
    for l in open(f):
        try: r = json.loads(l)
        except ValueError: continue
        new[(r['id'], r['suite'])] = r
def killed(r): return r['old'] == 'KILLED' or r.get('new') == 'KILLED'
def hang(r): return not killed(r) and 'TIMEOUT' in (r['old'], r.get('new'))
for suite in ('root', 'product'):
    keys = [k for k in t2 if k[1] == suite and t2[k]['old'] != 'NOT_APPLIED' and not (k in new and new[k]['old'] == 'NOT_APPLIED')]   # NOT_APPLIED on the current tree product engine (PS4 changed that text; unrelated to T3): dropped from BOTH sides
    n = len(keys); kb = sum(killed(t2[k]) for k in keys)
    ka = 0; rerun = 0; lost = []; gained = []
    for k in keys:
        r = new.get(k)
        if r: rerun += 1
        use = r or t2[k]
        if r and r['old'] == 'NOT_APPLIED': print('NOT_APPLIED', k)
        ka += killed(use)
        if killed(t2[k]) and not killed(use): lost.append((k[0], use['old'], use.get('new')))
        if not killed(t2[k]) and killed(use): gained.append(k[0])
    kh = sum(killed(new.get(k) or t2[k]) or hang(new.get(k) or t2[k]) for k in keys); kh0 = sum(killed(t2[k]) or hang(t2[k]) for k in keys)
    print(f"  incl. hangs: T2 {kh0}/{n} ({kh0/n:.1%}) -> T3 {kh}/{n} ({kh/n:.1%})")
    print(f"{suite}: runs={n} rerun_on_counter={rerun} killed T2={kb} ({kb/n:.1%}) -> T3={ka} ({ka/n:.1%}); lost={lost}; gained={gained}")
