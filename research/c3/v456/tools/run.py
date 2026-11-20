#!/usr/bin/env python3
# min #flips (k<=3), T=6, per-solver-call timeout. Engine: gs.py = B2's extended copy of scripts/glitchsat.py + goal_mask.
import sys, json, time, itertools
sys.path.insert(0, '/tmp/work_v456')
import gs
from multiprocessing import Pool
T = 6
GOALS = {'word': ('boot_word', 0x96), 'ok': ('boot_ok', 1), 'word16': ('boot_word16', 0x9669)}
def cell(a):
    d, net, goal, isites, init, tmo = a
    path = f'/tmp/work_v456/nl/{d}_{net}.json'
    nl = gs.Netlist(path, d); t0 = time.time()
    go, gv = GOALS[goal]
    row = dict(design=d, netlist=net, goal=goal, input_sites=isites, init=init, T=T)
    # honest sanity
    row['honest_boots'] = gs.honest_boots(nl, T, goal_out=go, goal_value=gv, init_mode='known')
    for k in range(0, 4):
        v, info, res = gs.solve(nl, T, k, goal_out=go, goal_value=gv, input_sites=isites, init_mode=init, minimize=False, timeout_ms=tmo)
        if v == 'ATTACK_FOUND':
            row.update(min=k, status='MEASURED', faults=[(nl.names.get(b, str(b)), t) for t, b in res['faults']]); break
        if v != 'NO_ATTACK_UP_TO_BOUND':
            row.update(min=None, status=f'UNKNOWN(timeout k={k}; >={k})'); break
    else:
        row.update(min=4, status='MEASURED(>3)')
    row['s'] = round(time.time() - t0, 1)
    return row
if __name__ == '__main__':
    out, designs, nets = sys.argv[1], sys.argv[2].split(','), sys.argv[3].split(',')
    tmo = int(sys.argv[4]) if len(sys.argv) > 4 else 90000
    cells = []
    for init in ('known', 'free_nongoal'):
      for isites in (False, True):
        for d in designs:
          for n in nets:
            for g in ('word', 'ok') + (('word16',) if d in ('v4', 'v4b') else ()):
                cells.append((d, n, g, isites, init, tmo))
    with Pool(4) as p, open(out, 'a') as f:
        for r in p.imap_unordered(cell, cells):
            f.write(json.dumps(r) + '\n'); f.flush()
