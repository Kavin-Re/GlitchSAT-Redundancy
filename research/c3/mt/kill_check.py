"""For each SURVIVED mutant in results.json, apply it to a fresh copy and run research/c3/mt/new_tests.
usage: kill_check.py results.json  -> /tmp/work_mt/kill_new.json"""
import sys, os, json, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mutate as m
NT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'new_tests')
res = []
for r in json.load(open(sys.argv[1])):
    if r['status'] != 'SURVIVED': continue
    spec = next(x for x in m.M if x[0] == r['id'])
    d = f"/tmp/work_mt/k/{r['id']}__{r['suite']}"
    shutil.rmtree(d, ignore_errors=True); shutil.copytree(m.LITE, d)
    m.apply(os.path.join(d, r['file']), spec[2], spec[3])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', MT_ENGINE=r['suite'], MT_ROOT=d)
    if r['suite'] == 'product': env['PYTHONPATH'] = d + '/product/src'
    cwd = d if r['suite'] == 'root' else d + '/product'
    p = subprocess.run(['timeout', '120', m.PY, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', NT], cwd=cwd, env=env, capture_output=True, text=True)
    st = {0: 'STILL_SURVIVES', 1: 'KILLED_BY_NEW', 124: 'TIMEOUT'}.get(p.returncode, f'ERR{p.returncode}')
    fl = [l for l in p.stdout.splitlines() if l.startswith('FAILED')][:1]
    print(r['id'], r['suite'], st, fl, flush=True)
    res.append(dict(id=r['id'], suite=r['suite'], new=st, failed=fl))
    shutil.rmtree(d, ignore_errors=True)
json.dump(res, open('/tmp/work_mt/kill_new.json', 'w'), indent=1)
