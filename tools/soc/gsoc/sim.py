"""Whole-chip simulators (no solver, no unrolling; they share no code with the search).

reset_state()  three-valued (0 / 1 / unknown) simulation of the reset sequence. Tells which flops have a known
               value when reset is released and which keep an unknown one.
Compiled       two-valued, bit-parallel simulator: the netlist is turned into straight-line Python code once;
               every net carries an arbitrary-width integer whose bit i is the value in scenario i ("lane").
               Used to replay solver witnesses on the WHOLE chip and for sampled fault campaigns.
"""
from . import gscale

G = gscale()
C = G.circuit
AND, OR, XOR, NOT, MUX = C.AND, C.OR, C.XOR, C.NOT, C.MUX


def topo_all(circ):
    """All gates, fan-ins first (Kahn). Raises on a combinational loop."""
    indeg = {}
    readers = {}
    gates = circ.gates
    for b, (op, fi) in gates.items():
        n = 0
        for f in fi:
            if f in gates:
                n += 1
                readers.setdefault(f, []).append(b)
        indeg[b] = n
    order = [b for b, n in indeg.items() if n == 0]
    i = 0
    while i < len(order):
        b = order[i]; i += 1
        for r in readers.get(b, ()):
            indeg[r] -= 1
            if indeg[r] == 0:
                order.append(r)
    if len(order) != len(gates):
        bad = [circ.name(b) for b, n in indeg.items() if n > 0][:5]
        raise C.CircuitError('combinational loop through %s' % ', '.join(bad))
    return order


# ------------------------------------------------------------------------------------------ three-valued reset
def _t_and(a, b):
    if a is False or b is False: return False
    if a is True and b is True: return True
    return None


def _t_or(a, b):
    if a is True or b is True: return True
    if a is False and b is False: return False
    return None


def _tern_step(circ, order, state, held):
    v = dict(state)

    def g(b):
        if b == '0': return False
        if b == '1': return True
        if b in v: return v[b]
        return held.get(b)            # inputs: held value or unknown
    for b in order:
        op, fi = circ.gates[b]
        if op == AND: r = _t_and(g(fi[0]), g(fi[1]))
        elif op == OR: r = _t_or(g(fi[0]), g(fi[1]))
        elif op == NOT:
            a = g(fi[0]); r = None if a is None else (not a)
        elif op == XOR:
            a, c = g(fi[0]), g(fi[1]); r = None if a is None or c is None else (a != c)
        else:
            s, x, y = g(fi[0]), g(fi[1]), g(fi[2])
            if s is True: r = x
            elif s is False: r = y
            else: r = x if (x is not None and x == y) else None
        v[b] = r
    return {q: g(d) for q, (d, _) in circ.flops.items()}, v


def reset_state(chip, held, cycles=16, max_widen=64, order=None):
    """State of every flop when reset is released, for ANY reset that lasts at least `cycles` clock cycles.

    held: {net: bool} inputs with a known value during reset (the reset pin at its active level, straps).
    Every other input, every black-box output and every flop without a Verilog initial value is unknown.
    After `cycles` steps the state is widened (s := join(s, next(s))) until it no longer changes, so the result
    covers every longer reset as well. Returns ({flop q: True / False / None}, info)."""
    circ = chip.circ
    order = order or topo_all(circ)
    s = {q: chip.init_attr.get(q) for q in circ.flops}
    for _ in range(cycles):
        s, _v = _tern_step(circ, order, s, held)
    widen = 0
    while widen < max_widen:
        n, _v = _tern_step(circ, order, s, held)
        j = {q: (s[q] if s[q] == n[q] else None) for q in s}
        widen += 1
        if j == s:
            break
        s = j
    else:
        raise C.CircuitError('reset state did not settle after %d widening steps' % max_widen)
    known = sum(1 for x in s.values() if x is not None)
    return s, dict(reset_cycles=cycles, widening_steps=widen, flops_known=known, flops_unknown=len(s) - known)


# ------------------------------------------------------------------------------------------ compiled two-valued
class Compiled:
    CHUNK = 1500

    def __init__(self, circ, order=None):
        self.circ = circ
        order = order or topo_all(circ)
        self.idx = {}
        for b in circ.inputs: self.idx[b] = len(self.idx) + 2
        for q in circ.flops: self.idx[q] = len(self.idx) + 2
        for b in order: self.idx[b] = len(self.idx) + 2
        self.n = len(self.idx) + 2
        ix = self.idx

        def r(f):
            if f == '0': return 'v[0]'
            if f == '1': return 'v[1]'
            return 'v[%d]' % ix[f]
        lines = []
        for b in order:
            op, fi = circ.gates[b]
            i = ix[b]
            if op == AND: e = '%s&%s' % (r(fi[0]), r(fi[1]))
            elif op == OR: e = '%s|%s' % (r(fi[0]), r(fi[1]))
            elif op == XOR: e = '%s^%s' % (r(fi[0]), r(fi[1]))
            elif op == NOT: e = '%s^M' % r(fi[0])
            else: e = '(%s&%s)|((%s^M)&%s)' % (r(fi[0]), r(fi[1]), r(fi[0]), r(fi[2]))
            lines.append(' v[%d]=(%s)^f[%d]' % (i, e, i))
        self.chunks = []
        for k in range(0, len(lines), self.CHUNK):
            src = 'def _c(v,f,M):\n' + '\n'.join(lines[k:k + self.CHUNK]) + '\n'
            ns = {}
            exec(compile(src, '<gsoc-sim>', 'exec'), ns)
            self.chunks.append(ns['_c'])
        self.flop_pairs = [(ix[q], (ix[d] if isinstance(d, int) else (1 if d == '1' else 0))) for q, (d, _) in circ.flops.items()]
        self.flop_ix = [ix[q] for q in circ.flops]
        self.input_ix = [ix[b] for b in circ.inputs]

    def run(self, lanes, cycles, state, inputs, flips, watch, on_cycle=None):
        """state: {flop net: lane word}. inputs(t) -> {net: lane word} (missing = 0). flips(t) -> {net: lane word}.
        watch: nets whose lane words are returned per cycle. Returns list over cycles of {net: word}."""
        M = (1 << lanes) - 1
        ix = self.idx
        v = [0] * self.n
        v[1] = M
        st = [state.get(q, 0) & M for q in self.circ.flops]
        out = []
        zero = [0] * self.n
        for t in range(cycles):
            f = zero
            fl = flips(t) if flips else None
            if fl:
                f = [0] * self.n
                for b, w in fl.items(): f[ix[b]] = w & M
            for i, w in zip(self.flop_ix, st): v[i] = w ^ f[i]
            for i in self.input_ix: v[i] = 0
            for b, w in (inputs(t) if inputs else {}).items():
                if b in ix: v[ix[b]] = w & M
            for c in self.chunks: c(v, f, M)
            out.append({b: v[ix[b]] for b in watch})
            if on_cycle: on_cycle(t, v, ix)
            st = [v[d] for _, d in self.flop_pairs]
        return out
