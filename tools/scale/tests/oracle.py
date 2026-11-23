"""Exhaustive reference for a gscale Problem, written without the unrolled DAG, the reductions, the encoder and a
solver: bit-parallel gate-level simulation over every value of every free input (run-constant and per-cycle), and
enumeration of every flip set over the allowed sites and cycles. Small problems only."""
import itertools


class Oracle:
    def __init__(self, P, max_vars=14):
        self.P = P; c = P.circ
        var = {}
        for b in sorted(c.inputs):
            m = P.mode(b)
            if m == 'const': var[(b, None)] = len(var)
            elif m == 'cycle':
                for t in range(P.N): var[(b, t)] = len(var)
        if len(var) > max_vars: raise ValueError('too many free input bits for the exhaustive reference')
        self.var = var
        L = 1 << len(var); self.ALL = (1 << L) - 1
        self.lane = {k: sum(1 << s for s in range(L) if (s >> p) & 1) for k, p in var.items()}
        self.order = c.topo(list(c.gates))
        self.pairs = [(t, b) for t in range(P.N) for b in sorted(P.sites)]
        ok = self.ALL
        if P.neq:
            eq = self.ALL
            for i, b in enumerate(P.neq[0]):
                l = self.inval(b, 0)
                eq &= l if (P.neq[1] >> i) & 1 else self.ALL ^ l
            ok = self.ALL ^ eq
        self.ok = ok

    def inval(self, b, t):
        if b == '0': return 0
        if b == '1': return self.ALL
        m = self.P.mode(b)
        if m == 'const': return self.lane[(b, None)]
        if m == 'cycle': return self.lane[(b, t)]
        return self.ALL if m else 0

    def run(self, faults, n=None):
        """Lanes in which the goal is hit (quiet condition intact) at a cycle < n."""
        P = self.P; c = P.circ; ALL = self.ALL
        by = {}
        for t, b in faults: by.setdefault(t, set()).add(b)
        st = {q: (ALL if i else 0) for q, (d, i) in c.flops.items()}
        hit = 0; quiet = ALL
        for t in range(P.N if n is None else n):
            f = by.get(t, ()); v = {}

            def g(b):
                if b in v: return v[b]
                return self.inval(b, t)
            for q in st: v[q] = st[q] ^ (ALL if q in f else 0)
            for b in self.order:
                op, fi = c.gates[b]
                if op == 'AND': r = g(fi[0]) & g(fi[1])
                elif op == 'OR': r = g(fi[0]) | g(fi[1])
                elif op == 'XOR': r = g(fi[0]) ^ g(fi[1])
                elif op == 'NOT': r = ALL ^ g(fi[0])
                else:
                    s = g(fi[0]); r = (s & g(fi[1])) | ((ALL ^ s) & g(fi[2]))
                v[b] = r ^ (ALL if b in f else 0)
            for b, w in P.quiet:
                x = g(b); quiet &= x if w else ALL ^ x
            m = quiet
            for b, w in P.goal:
                x = g(b); m &= x if w else ALL ^ x
            hit |= m
            st = {q: g(d) for q, (d, _) in c.flops.items()}
        return hit & self.ok

    def min_faults(self, kmax, n=None, limit=200000):
        tot = 0
        for j in range(kmax + 1):
            for cset in itertools.combinations(self.pairs, j):
                tot += 1
                if self.run(cset, n): return j
                if tot > limit: return 'limit'
        return None
