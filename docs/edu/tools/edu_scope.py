#!/usr/bin/env python3
"""Classroom helper: minimum number of modelled flips for a CONSUMER MASK and/or a COUNTING RULE.

Research-script wrapper (NOT part of product/): it imports research/c3/m1/gs_mask.py (the project solver plus a goal-mask argument)
and, for rule=fanout, re-implements the weighted-cost idea of research/c3/rep/scripts/rep_measure.py.
Usage: python3 edu_scope.py NETLIST.json TOP [--mask 0x0F] [--rule unit|fanout] [--cycles 6] [--kmax 6]
Prints: min cost, the attack (net@cycle), netlist sha256.  Model only: modelled bit flips, nothing physical.
Goal: boot_word bits inside the mask equal 0x96 on those bits at some cycle while sig != 0xC3 (constant input, known start state).
"""
import sys, os, argparse, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("EDU_REPO") or os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "research", "c3", "m1"))
import gs_mask as g
from z3 import PbLe, sat, unsat, is_true

def weights(nl):
    pins = collections.Counter(); outp = collections.Counter()
    for o, (cn, t, con) in nl.drivers.items():
        for p, v in con.items():
            if p != 'Y' and isinstance(v[0], int): pins[v[0]] += 1
    for q, d in nl.dq.items():
        if isinstance(d, int): pins[d] += 1
    for p, v in nl.ports.items():
        if v['direction'] == 'output':
            for b in v['bits']:
                if isinstance(b, int): outp[b] += 1
    return pins, outp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist"); ap.add_argument("top")
    ap.add_argument("--mask", type=lambda x: int(x, 0), default=0xFF)
    ap.add_argument("--rule", choices=["unit", "fanout"], default="unit")
    ap.add_argument("--cycles", type=int, default=6); ap.add_argument("--kmax", type=int, default=6)
    a = ap.parse_args()
    nl = g.Netlist(a.netlist, a.top)
    s, F, inputs, info = g.build(nl, a.cycles, goal_mask=a.mask)
    s.set("timeout", 300000)
    pins, outp = weights(nl)
    w = (lambda b: 1) if a.rule == "unit" else (lambda b: max(1, pins[b] + outp[b]))
    items = [(f, w(b)) for (t, b), f in F.items()]
    names = {f: (t, b) for (t, b), f in F.items()}
    best = None
    for k in range(0, a.kmax + 1):
        s.push(); s.add(PbLe(items, k)); r = s.check()
        if r == sat:
            m = s.model(); best = (k, [(t, b) for (t, b), f in F.items() if is_true(m.eval(f, model_completion=True))]); s.pop(); break
        s.pop()
        if r != unsat: print("UNKNOWN at k=%d" % k); return 4
    sha = hashlib.sha256(open(a.netlist, "rb").read()).hexdigest()
    print("netlist_sha256:", sha)
    print("mask: 0x%02X  rule: %s  cycles: %d" % (a.mask, a.rule, a.cycles))
    if best is None: print("min_cost: >%d (none found up to kmax)" % a.kmax); return 0
    print("min_cost:", best[0])
    print("flips:", ", ".join("%s@%d" % (b, t) for t, b in sorted(best[1])))
    print("flip net ids and their fanout cost (sink pins incl. output-port bits): " + ", ".join("%s:%d" % (b, pins[b] + outp[b]) for t, b in sorted(best[1])))
    return 0
sys.exit(main())
