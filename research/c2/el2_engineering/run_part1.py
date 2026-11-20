#!/usr/bin/env python3
# Part 1: min-k table via scripts/glitchsat.py (copy in /tmp/work_el2). Usage: run_part1.py <label> <rtl.v|netlist.json> <top> [flow]
import sys, json, time
sys.path.insert(0, '/tmp/work_el2/scripts')
import glitchsat as g
label, src, top = sys.argv[1:4]
flow = sys.argv[4] if len(sys.argv) > 4 else 'plain'
out = {}
for k in (1, 2, 3):
    t = time.time()
    r = g.run_check(src, top, k, 6, workdir=f'/tmp/work_el2/work_{label}', flow=flow)
    out[k] = dict(verdict=r['verdict'], min_faults=r.get('min_faults'), faults=[(f['net'], f['cycle']) for f in r.get('faults', [])],
                  wall=round(time.time()-t, 2), netlist=r['netlist'], solve=r['runtime_s'])
print(json.dumps(dict(label=label, flow=flow, res=out)))
