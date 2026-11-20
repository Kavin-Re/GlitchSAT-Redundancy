#!/usr/bin/env python3
"""Runs the MT mutant list (research/c3/mt/mutate.py, imported unchanged) on a copy under /tmp/work_t2.
For each (mutant, suite): OLD status = tests excluding the two new files (-x); if not KILLED, NEW status = the two new test files alone.
usage: mutate_t2.py [--only ID,ID] [--old results_partial.json] -> /tmp/work_t2/res_<tag>.json (appended per run, serial)"""
import os, sys, json, shutil, subprocess, time
sys.path.insert(0, 'research/c3/mt')
import mutate as m
LITE = '/tmp/work_t2/lite'; WORK = '/tmp/work_t2/m'; PY = '/tmp/work_t2/venv/bin/python'
NEW = ('test_mt_oracle.py', 'test_mt_targeted.py')
def pyt(args, cwd, env):
    p = subprocess.run(['timeout', '120', PY, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider'] + args, cwd=cwd, env=env, capture_output=True, text=True)
    return {0: 'SURVIVED', 1: 'KILLED', 124: 'TIMEOUT'}.get(p.returncode, f'ERROR_rc{p.returncode}'), [l for l in p.stdout.splitlines() if l.startswith('FAILED')][:2]
def run_one(mid, scope, old, new, suite, skip_old):
    if skip_old == 'KILLED': return dict(id=mid, suite=suite, old='KILLED', old_from_MT=True, new=None)
    tgt = dict(m.targets(scope))[suite]
    d = f'{WORK}/{mid}__{suite}'
    shutil.rmtree(d, ignore_errors=True); shutil.copytree(LITE, d)
    line, n = m.apply(os.path.join(d, tgt), old, new)
    if line is None: return dict(id=mid, suite=suite, old='NOT_APPLIED', new=None)
    if suite == 'root': cwd = d; env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1'); td = 'tests'
    else: cwd = d + '/product'; env = dict(os.environ, PYTHONPATH=d + '/product/src', PYTHONDONTWRITEBYTECODE='1'); td = 'tests'
    ign = [a for f in NEW for a in ('--ignore=%s/%s' % (td, f),)]
    t0 = time.time()
    ost, of = (skip_old, []) if skip_old else pyt([td] + ign, cwd, env)
    t1 = time.time(); nst = nf = None
    if ost != 'KILLED': nst, nf = pyt(['%s/%s' % (td, f) for f in NEW], cwd, env)
    shutil.rmtree(d, ignore_errors=True)
    return dict(id=mid, suite=suite, old=ost, old_failed=of, old_secs=round(t1 - t0, 1), new=nst, new_failed=nf, old_from_MT=bool(skip_old))
if __name__ == '__main__':
    only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
    prev = {}
    if '--old' in sys.argv:
        for r in json.load(open(sys.argv[sys.argv.index('--old') + 1])): prev[(r['id'], r['suite'])] = r['status']
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else '/tmp/work_t2/res.jsonl'
    os.makedirs(WORK, exist_ok=True)
    for mid, scope, old, new in [x[:4] for x in m.M]:
        if only and mid not in only: continue
        for suite, _ in m.targets(scope):
            r = run_one(mid, scope, old, new, suite, prev.get((mid, suite)))
            print(json.dumps(r), flush=True); open(out, 'a').write(json.dumps(r) + '\n')
