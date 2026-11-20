#!/usr/bin/env python3
"""Compares regenerated minsets/sweep JSON (WORKDIR/<var>/) with the committed research/c4/l2/data/ files.
usage: check_l2_table.py WORKDIR [VAR ...]. Prints per variant: min MEC radius of a sufficient set, set, first SUB-cost-1 radius, and equality."""
import json, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); REF = os.path.join(HERE, '..', 'l2', 'data')
W = sys.argv[1]; V = sys.argv[2:] or ['base', 'v8', 's8', 'v15', 'rr']
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k not in ('secs', 'solve_s', 'build_s', 'time', 'elapsed')}
    if isinstance(o, list): return [strip(x) for x in o]
    return o
bad = 0
for v in V:
    for kind in ('minsets', 'sweep'):
        a = f'{W}/{v}/{kind}_v2.json'; b = f'{REF}/{kind}_{v}.json'
        try: A = strip(json.load(open(a))); B = strip(json.load(open(b)))
        except Exception as e: print(v, kind, 'MISSING', e); bad += 1; continue
        same = A == B; bad += (not same)
        print(v, kind, 'IDENTICAL' if same else 'DIFFERENT')
        if not same:
            ka = set(A) ^ set(B)
            print('   differing top-level keys:', sorted(ka)[:5], [k for k in A if k in B and A[k] != B[k]][:6])
print('DIFFERENT files:', bad)
sys.exit(1 if bad else 0)
