#!/usr/bin/env python3
"""What-if placement for V2: exchange locations of cells with IDENTICAL master (same footprint) so the
cells of the minimal attack sets (minsets_v2.json) end up as far apart as the existing slots allow. Brute force over permutations inside
each master group {nand4bb_1, nand2_1, inv_1}; objective = maximise the smallest min-enclosing-circle radius over the minimal sets.
HYPOTHETICAL: routing, timing, DRC and LVS are NOT redone; only geometry-derived domain verdicts are recomputed by the same engine."""
import json, itertools, math, subprocess, sys, os
sys.path.insert(0, '.')
from geom_report import mec
import layout_extract as LE
G = json.load(open('layout_geometry_v2.json')); C = G['cells']
M = json.load(open('minsets_v2.json'))['minimal_sets']
sets = {tuple(s['cells']) for g in M.values() for s in g}
groups = {}
for k, c in C.items():
    if c['master'].endswith(('nand4bb_1', 'nand2_1', 'inv_1')): groups.setdefault(c['master'], []).append(k)
pos = {k: (C[k]['cx'], C[k]['cy']) for k in C}
def score(P):
    return min(mec([P[c] for c in s])[0] for s in sets)
best = None
gl = list(groups.values())
for perms in itertools.product(*[list(itertools.permutations(g)) for g in gl]):
    P = dict(pos)
    for g, pm in zip(gl, perms):
        for slot, cell in zip(g, pm): P[cell] = pos[slot]       # cell goes to the slot originally held by `slot`
    sc = score(P)
    if best is None or sc > best[0] + 1e-9: best = (sc, perms)
print('baseline min radius over minimal sets', round(score(pos), 3), 'best what-if', round(best[0], 3))
swaps = []
for g, pm in zip(gl, best[1]):
    # express as a sequence of pairwise swaps (cycle decomposition), cell at slot gets pm[i]
    cur = {s: s for s in g}      # slot -> cell currently there
    for slot, cell in zip(g, pm):
        if cur[slot] != cell:
            other = [s for s in g if cur[s] == cell][0]
            swaps.append((cur[slot], cell)); cur[other], cur[slot] = cur[slot], cell
print('swaps', swaps)
json.dump(dict(swaps=swaps, baseline_min_r_um=round(score(pos), 3), whatif_min_r_um=round(best[0], 3)), open('whatif_v2_swaps.json', 'w'), indent=1)
LE.analyse('v2', swaps, '_wi')
