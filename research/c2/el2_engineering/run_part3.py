#!/usr/bin/env python3
# Part 3: cell-output-flip verdicts on sky130-mapped netlists. usage: run_part3.py label netlist.v top
import sys, json, time
sys.path.insert(0, 'research/c2/el2_engineering')
import mapped_adapter as A
label, vp, top = sys.argv[1:4]
lib = A.load_lib('/tmp/work_el2/lib/sky130_fd_sc_hd__tt_025C_1v80.lib')
init = {'boot_word': 0xF0} if top != 'v0' else {}
N = A.build_netlist(vp, top, lib, init)
if top == 'v0':   # RTL: st 2-bit reg init 0, flops named st[...] ; all zero
    pass
res = {}
for k in (1, 2, 3):
    t = time.time(); v, r, dt = A.solve(N, 6, k)
    res[k] = dict(verdict=v, min=len(r['faults']) if r else None,
                  faults=[(N.names.get(b, b), c) if False else (c, N.names.get(b, str(b)) ) for c, b in r['faults']] if r else [], wall=round(dt, 2))
print(json.dumps(dict(label=label, cells=len(N.cellinfo), flops=len(N.dffs), honest=A.honest(N, 6), res=res)))
