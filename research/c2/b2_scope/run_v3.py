#!/usr/bin/env python3
"""Same matrix for V3 (rst platform-driven 1,1,1,0,0,0; boot_ok is an 8-bit code, goal 0xFF)."""
import sys, json, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gs import Netlist, solve
N = 6; KMAX = int(os.environ.get('KMAX', 3)); CTRL = {'rst': [1, 1, 1, 0, 0, 0]}
out = sys.argv[1]; nets = sys.argv[2].split(',')
f = open(out, 'a')
for n in nets:
    nl = Netlist(f'/tmp/work_b2/nl/v3_{n}.json', 'v3')
    for goal, gv in (('boot_word', 0x96), ('boot_ok', 0xFF)):
        v, _, r = solve(nl, N, 0, minimize=False, bad_only=False, fixed_in=0xC3, goal_out=goal, goal_value=gv, ctrl=CTRL, goal_from=3)
        print(n, goal, 'honest key boots fault-free:', v, flush=True)
        f.write(json.dumps(dict(design='v3', netlist=n, goal=goal, honest_boots=(v == 'ATTACK_FOUND'))) + '\n')
        for isites in (False, True):
          for init in ('known', 'free_nongoal', 'free'):
            for fin in (False, True):
                t0 = time.time()
                v, info, res = solve(nl, N, KMAX, goal_out=goal, goal_value=gv, input_sites=isites, init_mode=init, free_in=fin, ctrl=CTRL, goal_from=3, timeout_ms=300000)
                row = dict(design='v3', netlist=n, goal=goal, input_sites=isites, init=init, free_input=fin, N=N, verdict=v,
                           min_cost=(len(res['faults']) if res else None), cost_gt=(KMAX if v == 'NO_ATTACK_UP_TO_BOUND' else None),
                           faults=[(nl.names.get(b, str(b)), t) for t, b in res['faults']] if res else [], secs=round(time.time()-t0, 1), label='MEASURED')
                f.write(json.dumps(row) + '\n'); f.flush(); print({k: row[k] for k in ('netlist','goal','input_sites','init','free_input','verdict','min_cost','cost_gt','secs')}, row['faults'][:4], flush=True)
