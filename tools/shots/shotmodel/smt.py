"""Emit the shot problem as an SMT-LIB 2 file for z3 (z3 is not needed to write the file).

  z3 file.smt2      ->  "sat"   : an attack with at most k shots exists within T cycles (model lists the x_t_i shots)
                        "unsat" : none exists for this k, T, radius, rule, effect and goal

The file uses z3's ((_ at-most k) ...) cardinality constraint (a z3 extension of SMT-LIB).
Variables: s0..s7 = sig bits; x_<t>_<i> = shot i (see the header comment for its cells and aim point) fired in cycle t.
Every net value is a 0-ary define-fun, so the file reads like the netlist unrolled over T cycles.
tests/test_smt_and_results.py evaluates the emitted formulas on known witnesses with a small interpreter; no solver has been run
on these files in this repository.
"""
import re
from . import cells
from .design import KEY, GOOD, INIT


def _id(net):
    return "|" + net + "|"


def _expr(master, pinmap):
    """cell expression -> s-expression over net identifiers"""
    src = cells.COMB[cells.base(master)][1]
    tok = re.findall(r"[A-Z][A-Z0-9_]*|[()&|]", src)
    pos = 0

    def atom():
        nonlocal pos
        t = tok[pos]
        if t == "N":
            pos += 2
            e = orx()
            pos += 1
            return "(not %s)" % e
        if t == "(":
            pos += 1
            e = orx()
            pos += 1
            return e
        pos += 1
        return pinmap[t]

    def andx():
        nonlocal pos
        xs = [atom()]
        while pos < len(tok) and tok[pos] == "&":
            pos += 1
            xs.append(atom())
        return xs[0] if len(xs) == 1 else "(and %s)" % " ".join(xs)

    def orx():
        nonlocal pos
        xs = [andx()]
        while pos < len(tok) and tok[pos] == "|":
            pos += 1
            xs.append(andx())
        return xs[0] if len(xs) == 1 else "(or %s)" % " ".join(xs)

    e = orx()
    if pos != len(tok):
        raise ValueError("cannot parse cell expression %r" % src)
    return e


def emit(design, table, T, k, effect="flip", goal="word"):
    masks = [int(m) for m in table["masks"]]
    L = ["; GlitchSAT shot model, %s, r=%s um, rule=%s, aim=%s, targets=%s, effect=%s, goal=%s, T=%d, k<=%d"
         % (design.id, table["r"], table["rule"], table["aim"], table["targets"], effect, goal, T, k),
         "; sat = attack exists within the bound; unsat = none within the bound (bounded, modelled, not physical)"]
    for i, (m, p) in enumerate(zip(masks, table["points"])):
        L.append("; shot %d at (%.3f, %.3f): %s" % (i, p[0], p[1], " ".join(design.names(m))))
    L.append("(set-logic ALL)")
    for i in range(8):
        L.append("(declare-const s%d Bool)" % i)
    L.append("(assert (not (and %s)))" % " ".join(("s%d" % i) if (KEY >> i) & 1 else "(not s%d)" % i for i in range(8)))
    xs = []
    for t in range(T):
        for i in range(len(masks)):
            L.append("(declare-const x_%d_%d Bool)" % (t, i))
            xs.append("x_%d_%d" % (t, i))

    def dist(val, h):
        if effect == "flip":
            return "(xor %s %s)" % (val, h)
        if effect == "set0":
            return "(and %s (not %s))" % (val, h)
        return "(or %s %s)" % (val, h)

    f = cells.FLOP["dfxtp"]
    goals = []
    for t in range(T):
        hit = {}
        for c in design.logic:
            cov = ["x_%d_%d" % (t, i) for i, m in enumerate(masks) if (m >> c.idx) & 1]
            h = "false" if not cov else cov[0] if len(cov) == 1 else "(or %s)" % " ".join(cov)
            hit[c.idx] = "h_%d_%d" % (t, c.idx)
            L.append("(define-fun %s () Bool %s)" % (hit[c.idx], h))
        nm = lambda n: ("s%d" % design.sig_nets.index(n)) if n in design.sig_nets else _id("%s@%d" % (n, t))
        for i, c in enumerate(design.flops):
            st = ("true" if (INIT >> i) & 1 else "false") if t == 0 else _id("%s@%d" % (design.flops[i].pins[f["d"]], t - 1))
            L.append("(define-fun %s () Bool %s)" % (nm(c.out), dist(st, hit[c.idx])))
        for c in design.comb:
            e = _expr(c.master, {p: nm(c.pins[p]) for p in cells.input_pins(c.master)})
            L.append("(define-fun %s () Bool %s)" % (nm(c.out), dist(e, hit[c.idx])))
        if goal == "ok":
            g = nm(design.ok_net)
        else:
            g = "(and %s)" % " ".join(nm(n) if (GOOD >> i) & 1 else "(not %s)" % nm(n)
                                      for i, n in enumerate(design.word_nets))
            if goal == "word_clean" and masks:
                g = "(and %s (not (or %s)))" % (g, " ".join("x_%d_%d" % (t, i) for i in range(len(masks))))
        L.append("(define-fun goal_%d () Bool %s)" % (t, g))
        goals.append("goal_%d" % t)
    L.append("(assert (or %s))" % " ".join(goals))
    if xs:
        L.append("(assert ((_ at-most %d) %s))" % (k, " ".join(xs)))
    L += ["(check-sat)", "(get-model)"]
    return "\n".join(L) + "\n"
