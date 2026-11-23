"""Simulators. replay() is the referee for every reported attack: a plain scalar gate-level simulation of the
Circuit, written without the unrolled DAG, the reductions and the encoder. dag_eval() is the bit-parallel evaluator
of a Dag used for signatures and module summaries."""
import heapq
from .circuit import AND, OR, XOR, NOT, MUX
from .unroll import C0, C1, IN, BUF


def replay(P, inputs, faults):
    """inputs: {net: bool} for run-constant inputs and {(t, net): bool} for per-cycle inputs (missing = 0).
    faults: iterable of (cycle, net). Returns dict(hit=first cycle at which the goal holds with the quiet condition
    intact, or None; neq_ok; sites_ok; trace=[goal bits per cycle])."""
    c = P.circ
    fset = set(faults)
    sites_ok = all(b in P.sites and 0 <= t < P.N for t, b in fset) and len(fset) == len(list(faults) if not isinstance(faults, (set, frozenset)) else faults)
    order = c.topo(list(c.gates))
    state = {q: bool(i) for q, (d, i) in c.flops.items()}
    hit = None; quiet_ok = True; trace = []
    for t in range(P.N):
        v = {}

        def g(b):
            if b == '0': return False
            if b == '1': return True
            if b in v: return v[b]
            m = P.mode(b)
            if m == 'const': return bool(inputs.get(b, False))
            if m == 'cycle': return bool(inputs.get((t, b), False))
            return bool(m)
        for q in c.flops:
            v[q] = state[q] ^ ((t, q) in fset)
        for b in order:
            op, fi = c.gates[b]
            if op == AND: r = g(fi[0]) and g(fi[1])
            elif op == OR: r = g(fi[0]) or g(fi[1])
            elif op == XOR: r = g(fi[0]) != g(fi[1])
            elif op == NOT: r = not g(fi[0])
            else: r = g(fi[1]) if g(fi[0]) else g(fi[2])
            v[b] = bool(r) ^ ((t, b) in fset)
        quiet_ok = quiet_ok and all(g(b) == w for b, w in P.quiet)
        gv = [g(b) for b, _ in P.goal]
        trace.append(gv)
        if hit is None and quiet_ok and all(x == w for x, (_, w) in zip(gv, P.goal)):
            hit = t
        state = {q: g(d) for q, (d, _) in c.flops.items()}
    neq_ok = True
    if P.neq:
        val = sum(1 << i for i, b in enumerate(P.neq[0]) if g(b))
        neq_ok = val != P.neq[1]
    return dict(hit=hit, neq_ok=neq_ok, sites_ok=sites_ok, trace=trace)


def is_attack(P, inputs, faults, within=None):
    r = replay(P, inputs, faults)
    return r['hit'] is not None and r['neq_ok'] and r['sites_ok'] and (within is None or r['hit'] < within)


def dag_eval(d, inw, mask, flip=None):
    """Bit-parallel evaluation. inw: {input node: word}. flip: {node: word} XORed onto site outputs. Returns val."""
    n = len(d)
    val = [0] * n
    val[1] = mask
    op_, fi_ = d.op, d.fi
    flip = flip or {}
    for i in range(2, n):
        op = op_[i]; fi = fi_[i]
        if op == AND: r = val[fi[0]] & val[fi[1]]
        elif op == OR: r = val[fi[0]] | val[fi[1]]
        elif op == XOR: r = val[fi[0]] ^ val[fi[1]]
        elif op == NOT: r = val[fi[0]] ^ mask
        elif op == MUX:
            s = val[fi[0]]; r = (s & val[fi[1]]) | ((s ^ mask) & val[fi[2]])
        elif op == BUF: r = val[fi[0]]
        elif op == IN: r = inw.get(i, 0)
        elif op == C1: r = mask
        else: r = 0
        f = flip.get(i)
        val[i] = r ^ f if f else r
    return val


def toggle_effect(d, val, mask, a, rd, flip=None, word=None):
    """Values that change when node a is toggled (in the samples of `word`, default all) on top of the base evaluation
    `val` (which already contains the context flips `flip`). Event driven. Returns {node: new value} of changed nodes."""
    new = {a: val[a] ^ (mask if word is None else word)}
    heap = list(rd[a]); heapq.heapify(heap); done = set()
    op_, fi_ = d.op, d.fi
    flip = flip or {}
    while heap:
        i = heapq.heappop(heap)
        if i in done: continue
        done.add(i)
        op = op_[i]; fi = fi_[i]
        x = [new.get(f, val[f]) for f in fi]
        if op == AND: r = x[0] & x[1]
        elif op == OR: r = x[0] | x[1]
        elif op == XOR: r = x[0] ^ x[1]
        elif op == NOT: r = x[0] ^ mask
        elif op == MUX: r = (x[0] & x[1]) | ((x[0] ^ mask) & x[2])
        else: r = x[0]
        f = flip.get(i)
        if f: r ^= f
        if r != val[i]:
            new[i] = r
            for q in rd[i]:
                if q not in done: heapq.heappush(heap, q)
    return new
