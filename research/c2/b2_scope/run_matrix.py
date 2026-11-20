#!/usr/bin/env python3
"""Scope-sensitivity matrix. Uses gs.py (extended COPY of scripts/glitchsat.py). Min cost = smallest #flips (k<=KMAX), cycles N."""
import sys, json, itertools, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs
from gs import Netlist, solve
N = 6; KMAX = 3
NLDIR = sys.argv[1] if len(sys.argv) > 1 else '/tmp/work_b2/nl'
designs = sys.argv[2].split(',') if len(sys.argv) > 2 else ['v0', 'v1', 'v2']
nets = sys.argv[3].split(',') if len(sys.argv) > 3 else ['spike', 'apt033_plain', 'apt033_opt', 'conda038_plain', 'conda038_opt']
out = sys.argv[4] if len(sys.argv) > 4 else 'matrix.jsonl'
f = open(out, 'a')
for d in designs:
  for n in nets:
    nl = Netlist(f'{NLDIR}/{d}_{n}.json', d)
    for goal, gv in (('boot_word', 0x96), ('boot_ok', 1)):
      for isites in (False, True):
        for init in ('known', 'free_nongoal', 'free'):
          for fin in (False, True):
            t0 = time.time()
            v, info, res = solve(nl, N, KMAX, goal_out=goal, goal_value=gv, input_sites=isites, init_mode=init, free_in=fin, timeout_ms=120000)
            row = dict(design=d, netlist=n, goal=goal, input_sites=isites, init=init, free_input=fin, N=N,
                       verdict=v, min_cost=(len(res['faults']) if res else None), cost_gt=(KMAX if v == 'NO_ATTACK_UP_TO_BOUND' else None),
                       faults=[(nl.names.get(b, str(b)), t) for t, b in res['faults']] if res else [], secs=round(time.time()-t0, 1), label='MEASURED')
            f.write(json.dumps(row) + '\n'); f.flush(); print(row, flush=True)
