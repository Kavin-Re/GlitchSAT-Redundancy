#!/usr/bin/env python3
"""Hand-sized example for PROJECT_DOSSIER.md section 5.
3 gates: g1 = a&b, g2 = a&b (two 'copies' of the check), g3 = g1&g2 (shared decision wire).
Key is a=1,b=1. Attack goal: boot=g3 is 1 while (a,b) != (1,1). Fault = flip of a gate output.
Part 1: brute force over inputs and flip sets. Part 2: same question as SAT (z3), with a fault budget k.
Part 3: coding-theory-style note not here (see test_hamming.py)."""
import itertools
from z3 import Bools, Solver, And, Xor, Not, Or, PbLe, sat

def run(a, b, f1, f2, f3):
    g1 = (a & b) ^ f1
    g2 = (a & b) ^ f2
    g3 = (g1 & g2) ^ f3
    return g3

print("== brute force ==")
best = {}
for a, b in itertools.product([0, 1], repeat=2):
    if (a, b) == (1, 1):
        continue
    for fl in itertools.product([0, 1], repeat=3):
        if run(a, b, *fl):
            best.setdefault(sum(fl), []).append(((a, b), fl))
for k in sorted(best):
    print("flips =", k, "-> attacks:", best[k])
print("min flips (brute force) =", min(best))

print("== SAT with z3 ==")
def solve(k):
    a, b, f1, f2, f3 = Bools("a b f1 f2 f3")
    s = Solver()
    g1 = Xor(And(a, b), f1); g2 = Xor(And(a, b), f2); g3 = Xor(And(g1, g2), f3)
    s.add(g3)                      # attacker wants boot = 1
    s.add(Not(And(a, b)))          # but the input is not the key
    s.add(PbLe([(f1, 1), (f2, 1), (f3, 1)], k))   # at most k flips
    if s.check() == sat:
        m = s.model()
        return {str(x): bool(m[x]) for x in (a, b, f1, f2, f3)}
    return None
for k in range(0, 3):
    print("k =", k, "->", solve(k))
