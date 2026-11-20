#!/usr/bin/env python3
"""Applies each named mutant to a fresh copy and runs ONLY test_mt_targeted.py (and, separately, ONLY test_mt_oracle.py)."""
import sys, os, shutil, subprocess
sys.path.insert(0, '/home/user/project/research/c3/mt'); sys.path.insert(0, '/home/user/project/research/c3/t2')
import mutate as m, mutate_t2 as t
for mid in sys.argv[1].split(','):
    x = next(y for y in m.M if y[0] == mid)
    for suite, _ in m.targets(x[1]):
        for f in ('test_mt_targeted.py', 'test_mt_oracle.py'):
            d = f'/tmp/work_t2/k/{mid}__{suite}'; shutil.rmtree(d, ignore_errors=True); shutil.copytree(t.LITE, d)
            m.apply(os.path.join(d, dict(m.targets(x[1]))[suite]), x[2], x[3])
            if suite == 'root': cwd = d; env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            else: cwd = d + '/product'; env = dict(os.environ, PYTHONPATH=d + '/product/src', PYTHONDONTWRITEBYTECODE='1')
            print(mid, suite, f, t.pyt(['tests/' + f], cwd, env)[0], flush=True); shutil.rmtree(d, ignore_errors=True)
