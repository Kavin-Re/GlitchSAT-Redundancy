"""CNF of the unrolled DAG with a fault variable on each kept site.

One formula serves every fault budget j <= kmax (totalizer outputs as assumptions) and every horizon n <= N
(prefix literals: assuming prefix[n] means "the goal is hit at some cycle < n"). Clauses learned for one (j, n) stay
valid for all others, because budgets and horizons only enter through assumptions.
"""
from .circuit import AND, OR, XOR, NOT, MUX
from .unroll import C0, C1, IN, BUF
from . import fastsat


def gate_lit(e, op, x, f=None, relax=False):
    """Literal of one DAG node: operator over fan-in literals x, XOR the fault variable f when given."""
    if op == AND: return e.g_and(x[0], x[1], f, relax)
    if op == OR: return e.g_or(x[0], x[1], f, relax)
    if op == XOR: return e.g_xor(x[0], x[1], f, relax)
    if op == MUX: return e.g_mux(x[0], x[1], x[2], f, relax)
    if op == NOT: return -x[0] if f is None else e.g_xor(-x[0], f)
    if op == BUF: return x[0] if f is None else e.g_xor(x[0], f)
    if op == IN: return e.new_var()
    if op == C0: return -1 if f is None else f
    if op == C1: return 1 if f is None else -f
    raise ValueError(op)


def encode_nodes(e, d, keep, lit=None, nodes=None, relax=False, F=None):
    """Encode nodes (default: all, in order) into Encoding e. lit: preset literals (inputs, cut points).
    Returns (lit, F) with F = {node: fault variable} for the kept sites."""
    fs = fastsat()
    T_, F_ = fs.T_, fs.F_
    lit = {} if lit is None else lit
    lit[0] = F_; lit[1] = T_
    F = {} if F is None else F
    op_, fi_ = d.op, d.fi
    for i in (range(2, len(d)) if nodes is None else nodes):
        if i in lit: continue
        op = op_[i]
        f = None
        if i in keep:
            f = e.new_var(); F[i] = f
        v = gate_lit(e, op, [lit[j] for j in fi_[i]], f, relax)
        lit[i] = v
    return lit, F


def add_goal(e, U, lit):
    """Hit literals and horizon prefixes. Returns prefix: list, prefix[n] is a literal that implies "hit at a cycle
    < n" (prefix[0] is FALSE)."""
    fs = fastsat()
    T_, F_ = fs.T_, fs.F_
    N = len(U.hit)
    qok = T_                      # literal implying "quiet condition held at all cycles so far"
    prefix = [F_]
    for t in range(N):
        if U.quiet[t] is not None and U.quiet[t]:
            q = e.new_var()
            if qok != T_: e.add([-q, qok])
            for n, w in U.quiet[t]:
                e.add([-q, lit[n] if w else -lit[n]])
            qok = q
        if U.hit[t] is None:
            h = F_
        else:
            want = [lit[n] if w else -lit[n] for n, w in U.hit[t]]
            if qok != T_: want.append(qok)
            if F_ in want: h = F_
            else:
                want = [w for w in want if w != T_]
                if not want: h = T_
                elif len(want) == 1: h = want[0]
                else:
                    h = e.new_var()
                    for w in want: e.add([-h, w])
        prev = prefix[-1]
        if h == T_ or prev == T_: p = T_
        elif h == F_: p = prev
        elif prev == F_: p = h
        else:
            p = e.new_var(); e.add([-p, prev, h])
        prefix.append(p)
    if U.neq:
        nodes, key = U.neq
        e.add([-lit[n] if (key >> i) & 1 else lit[n] for i, n in enumerate(nodes)])
    return prefix


class Model:
    """Exact model of the (reduced) problem."""

    def __init__(self, U, keep, kmax, relax=False, card='totalizer'):
        fs = self.fs = fastsat()
        self.U, self.keep, self.kmax = U, keep, kmax
        e = self.e = fs.Encoding()
        self.lit, self.F = encode_nodes(e, U.dag, keep, relax=relax)
        self.prefix = add_goal(e, U, self.lit)
        self.relax = relax
        e.fault_order = [self.F[i] for i in sorted(self.F)]
        self.core = e.stats()
        fs.add_cardinality(e, kmax, card)
        self.size = e.stats()

    def assume(self, j, n=None):
        n = len(self.prefix) - 1 if n is None else n
        return [self.prefix[n]] + self.fs.atmost(self.e, j)

    def witness(self, m):
        """(inputs, faults) from a solver model. With the relaxed fault encoding the flips are normalised by the
        caller (replay decides)."""
        d = self.U.dag
        faults = sorted(d.key[i] for i, f in self.F.items() if m[f])
        return self.inputs(m), faults

    def inputs(self, m):
        ins = {}
        for (b, t), n in self.U.in_nodes.items():
            v = self.lit.get(n)
            if v is None: continue
            val = bool(m[v]) if v > 0 else not m[-v]
            ins[b if t is None else (t, b)] = val
        return ins
