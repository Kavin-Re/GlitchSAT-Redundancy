#!/usr/bin/env python3
"""ext/unbounded's SAT methods (k-induction with simple-path constraints, IC3) on netlists with more than
20 flip-flops.

ext/unbounded's command line always builds its explicit-state oracle, which refuses designs with more than
20 flops or 16 input bits, even when only the SAT methods are asked for. This script uses the same library
functions (unbounded.Problem, unbounded.analyse) with the oracle left out; nothing in ext/unbounded is
changed. Without the oracle there is no explicit cross-check, and an attack trace cannot be replayed on the
oracle's simulator (attack answers are then reported as 'attack (not replayed here)'; the bounded engines
give replayed attacks).

usage: unbounded_sat.py NETLIST TOP K GOAL_VALUE KEY OUT.json [TIMEOUT_S]
"""
import json
import os
import sys
import time

EXT = os.environ.get('GLITCHSAT_EXT') or (lambda _d: _d if os.path.isdir(os.path.join(_d, 'fastsat')) else os.path.join(_d, 'ext'))(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, os.path.join(EXT, 'unbounded', 'src'))
import unbounded as ub  # noqa: E402


class SatOnlyProblem(ub.Problem):
    def __init__(self, path, top, **kw):
        self.path, self.top = path, top
        self.kw = dict(goal_out='gout', goal_mask=None, attack_in='sig', input_sites=False)
        self.kw.update(kw)
        self.gs = ub.tsmod.load_engine()
        self.nl = self.gs.Netlist(path, top)
        self.onet = None
        self.oracle = None
        self._blocked = None


def main(argv):
    net, top, k, gv, key, out = argv[1], argv[2], int(argv[3]), int(argv[4], 0), int(argv[5], 0), argv[6]
    tmo = float(argv[7]) if len(argv) > 7 else 500
    t0 = time.time()
    P = SatOnlyProblem(net, top, goal_value=gv, key=key)
    res = {}
    for m in ('kind', 'ic3'):
        try:
            r = ub.analyse(P, k, 'known', methods=(m,), backend='auto', timeout_s=tmo / 2)
            res[m] = dict(verdict=r['verdict'], seconds=r.get('seconds'),
                          detail={kk: (vv if len(str(vv)) < 400 else str(vv)[:400])
                                  for kk, vv in list(r['methods'].values())[0].items()})
        except Exception as e:  # attack replay needs the oracle; report and go on
            res[m] = dict(verdict='error', reason='%s: %s' % (type(e).__name__, e))
    vs = {v['verdict'] for v in res.values()}
    if 'PROVED_UNBOUNDED' in vs and 'ATTACK_FOUND' in vs:
        verdict = 'INCONSISTENT'
    elif 'PROVED_UNBOUNDED' in vs:
        verdict = 'PROVED_UNBOUNDED'
    elif 'ATTACK_FOUND' in vs:
        verdict = 'ATTACK_FOUND'
    else:
        verdict = 'UNKNOWN'
    doc = dict(tool='scripts/unbounded_sat.py (ext/unbounded library, SAT methods only, no oracle)',
               netlist=net, top=top, k=k, init='known', verdict=verdict, methods=res,
               seconds=round(time.time() - t0, 3),
               scope='any number of clock cycles, at most %d single-cycle flips of gate outputs / flop Q nets, '
                     'attacker input held constant and != key; this netlist only; modelled faults' % k)
    json.dump(doc, open(out, 'w'), indent=1)
    print('%s: %s (k <= %d, any number of cycles)  %s' % (top, verdict, k,
          '  '.join('%s=%s/%ss' % (m, v['verdict'], v.get('seconds')) for m, v in res.items())))
    return 0 if verdict in ('PROVED_UNBOUNDED', 'ATTACK_FOUND') else 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
