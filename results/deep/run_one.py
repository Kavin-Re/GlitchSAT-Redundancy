#!/usr/bin/env python3
"""run_one.py NETLIST.json TOP K CYCLES OUT.json  -- one glitchsat run (imports scripts/glitchsat.py unmodified)."""
import sys, json, time, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repository root
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g
nlp, top, k, N, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
t0 = time.time()
r = g.run_check(nlp, top, k, N, out, workdir=os.path.join(ROOT, 'results', 'deep', 'work'))
print(top, r['verdict'], 'min', r.get('min_faults'), 'wall', round(time.time()-t0, 2),
      [(f['net'], f['cycle']) for f in r.get('faults', [])], 'honest', r['honest_key_boots_fault_free'])
