#!/usr/bin/env python3
"""Coding-theory check for PROJECT_DOSSIER.md section 11.
Question: the FSM state code {F0,CC,96,69} has minimum Hamming distance d. If an attacker may flip ONLY the 8
state flops' Q nets (st[0..7]), is the minimum number of flips to make boot_word==0x96 at least d (=4)?
Compare with the unrestricted fault set (all gate outputs + flop Q), same solver, same netlist.
Usage: python3 test_hamming.py <repo_copy_dir> <netlist.json> <top> [cycles]
Run on a COPY of the repo (it imports scripts/glitchsat.py)."""
import sys, itertools
repo, path, top = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 6
sys.path.insert(0, repo + '/scripts')
import glitchsat as g
from z3 import PbLe, sat, Not
code = [0xF0, 0xCC, 0x96, 0x69]
print("code words:", [hex(c) for c in code])
print("pairwise Hamming distances:", {(hex(a), hex(b)): bin(a ^ b).count('1') for a, b in itertools.combinations(code, 2)})
print("min distance of code:", min(bin(a ^ b).count('1') for a, b in itertools.combinations(code, 2)))
nl = g.Netlist(path, top)
s, F, inputs, info = g.build(nl, N)
stq = set(nl.qs)   # in V1/V2 the 8 state flops are named boot_word[0..7] after synthesis (st == boot_word)
print("netlist", nl.stats(), "state-flop Q nets:", sorted(nl.names[b] for b in stq))
print('NOTE: V0 has only 2 state flops (different encoding), so the 4-bit-distance argument does not apply to V0.')
def mink(sites_filter, label, kmax=8):
    for k in range(0, kmax + 1):
        s2, F2, _, _ = g.build(nl, N)
        s2.push()
        for (t, b), f in F2.items():
            if not sites_filter(b):
                s2.add(Not(f))
        s2.add(PbLe([(f, 1) for (t, b), f in F2.items() if sites_filter(b)], k))
        if s2.check() == sat:
            print(f"{label}: min flips = {k}"); return k
    print(f"{label}: no attack up to k={kmax}")
mink(lambda b: b in stq, "state-flop-Q only")
mink(lambda b: True, "all sites (gate outputs + all flop Q)")
mink(lambda b: b not in nl.qs, "gate outputs only")
