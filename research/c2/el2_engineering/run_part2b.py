#!/usr/bin/env python3
# Part 2b: 'overclock-style' correlated model. One event at cycle t = flip ALL cell outputs with worst setup
# slack <= theta simultaneously (theta chosen by the attacker per event; at most one event per cycle).  usage: run_part2b.py tag top
import sys, json
sys.path.insert(0, '/home/user/project/research/c2/el2_engineering')
import mapped_adapter as A
tag, top = sys.argv[1:3]
d = json.load(open(f'/home/user/project/research/c2/el2_engineering/data_part2_{tag}.json'))
lib = A.load_lib('/tmp/work_el2/lib/sky130_fd_sc_hd__tt_025C_1v80.lib')
N = A.build_netlist(f'/tmp/work_el2/lay/out/{tag}_net.v', top, lib, {'boot_word': 0xF0} if top != 'v0' else {})
cs = d['cell_slacks']
order = sorted((c for c in cs if c in N.cellinfo), key=lambda c: cs[c])
cover = {}
thetas = []
for n in range(1, len(order) + 1):
    if n < len(order) and abs(cs[order[n]] - cs[order[n-1]]) < 1e-9: continue
    gid = f'th{cs[order[n-1]]:.3f}'; thetas.append((gid, n))
    for c in order[:n]: cover.setdefault(N.cellinfo[c]['out'], []).append(gid)
res = {}
for k in (1, 2, 3):
    v, r, dt = A.solve(N, 6, k, cover=cover, amo=True)
    res[k] = dict(verdict=v, min_events=len(r['faults']) if r else None, events=[(t, g) for t, g in r['faults']] if r else [], wall=round(dt, 2))
    print(tag, 'k<=', k, v, res[k]['min_events'], res[k]['events'])
json.dump(dict(n_thresholds=len(thetas), res=res), open(f'/home/user/project/research/c2/el2_engineering/data_part2b_{tag}.json', 'w'), indent=1)
