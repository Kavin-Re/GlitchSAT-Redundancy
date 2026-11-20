#!/usr/bin/env python3
# Part 4: locality experiment. usage: run_part4.py tag top
# One glitch (at cycle t) = disc of radius r um around a cell centre; flips every cell output (and flop Q) whose cell centre is inside.
# Overlapping discs at the same cycle combine by XOR. Placement = OpenROAD DEF from /tmp/work_el2/lay/out (SIMULATED/modelling choice).
import sys, json, math, itertools
sys.path.insert(0, '/home/user/project/research/c2/el2_engineering')
import mapped_adapter as A
tag, top = sys.argv[1:3]
lib = A.load_lib('/tmp/work_el2/lib/sky130_fd_sc_hd__tt_025C_1v80.lib')
N = A.build_netlist(f'/tmp/work_el2/lay/out/{tag}_net.v', top, lib, {'boot_word': 0xF0} if top != 'v0' else {})
pos = A.read_def(f'/tmp/work_el2/lay/out/{tag}.def', lib, N.cellinfo)
missing = [c for c in N.cellinfo if c not in pos]
res = dict(tag=tag, missing_in_def=missing, rows=[])
# geometry of compare copies
geo = {}
for c in ('c0', 'c1', 'c2'):
    pts = [pos[n][:2] for n in pos if n.startswith(c + '/')]
    if pts: geo[c] = (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts), max(math.hypot(a[0]-b[0], a[1]-b[1]) for a in pts for b in pts))
res['copy_centroids_um'] = {k: (round(v[0], 2), round(v[1], 2), round(v[2], 2)) for k, v in geo.items()}
res['copy_centroid_dist_um'] = {f'{a}-{b}': round(math.hypot(geo[a][0]-geo[b][0], geo[a][1]-geo[b][1]), 2) for a, b in itertools.combinations(geo, 2)}
dd = sorted(pos[n][:2] for n in N.cellinfo if n in pos)
res['logic_bbox_um'] = (round(min(p[0] for p in dd), 1), round(min(p[1] for p in dd), 1), round(max(p[0] for p in dd), 1), round(max(p[1] for p in dd), 1))
for inc in (True, False):
    for r in (0, 1.5, 2.5, 3.5, 5, 7, 10, 15, 25):
        cover, nglitch = A.cover_by_radius(N, pos, r, include_seq=inc)
        cover = dict(cover)
        v, rr, dt = A.solve(N, 6, 3, cover=cover)
        row = dict(radius_um=r, flops_flippable=inc, distinct_glitch_discs=nglitch, verdict=v, min_events=len(rr['faults']) if rr else None,
                   events=[(t, g) for t, g in rr['faults']] if rr else [], wall=round(dt, 2))
        res['rows'].append(row); print(tag, 'seq' if inc else 'comb', r, nglitch, v[:9], row['min_events'], row['events'])
json.dump(res, open(f'/home/user/project/research/c2/el2_engineering/data_part4_{tag}.json', 'w'), indent=1)
