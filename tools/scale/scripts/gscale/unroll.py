"""Time-unrolled circuit as one DAG, with the sound structural simplifications applied while it is built.

Dag        nodes in topological order. Node 0 / 1 are the hard constants FALSE / TRUE: values that no input and no
           modelled fault can change. Every other node has an operator, fan-in node ids, a `site` flag (its output
           may be flipped: value = function XOR flip) and a key (cycle, net) saying which net at which cycle it is.
unroll()   builds the Dag of a Problem:
             * only nets in the backward cone of the observed nets, and only while they can still reach an observed
               net before the horizon (cone of influence + timing);
             * hard-constant propagation: tied inputs, power-up values and everything they force through gates that
               are not fault sites are folded away, together with the edges they kill (AND with hard 0, ...).
               A fault site is never folded: its node keeps its own flip;
             * structural hashing of identical non-site nodes;
             * a final backward sweep from the observed nodes drops whatever cannot reach one.
           None of this changes the value of any observed node under any input and any set of flips, so it changes
           no verdict (README section 4.1).
"""
from .circuit import AND, OR, XOR, NOT, MUX, CircuitError

C0, C1, IN, BUF = 'C0', 'C1', 'IN', 'BUF'      # C0/C1 with site=True: constant XOR flip. BUF: fan-in XOR flip.
COMM = (AND, OR, XOR)


class Dag:
    def __init__(self):
        self.op = [C0, C1]; self.fi = [(), ()]; self.site = [False, False]; self.key = [None, None]
        self.obs = set()                   # observed node ids
        self._hash = {}

    def __len__(self):
        return len(self.op)

    def new(self, op, fi, site, key):
        self.op.append(op); self.fi.append(fi); self.site.append(site); self.key.append(key)
        return len(self.op) - 1

    def _fold(self, op, fi):
        """Simplify a fault-free gate over hard constants. Returns an existing node id, or (op, fi) to create."""
        op_, site_ = self.op, self.site
        if op == AND:
            a, b = fi
            if a == 0 or b == 0: return 0
            if a == 1: return b
            if b == 1 or a == b: return a
        elif op == OR:
            a, b = fi
            if a == 1 or b == 1: return 1
            if a == 0: return b
            if b == 0 or a == b: return a
        elif op == XOR:
            a, b = fi
            if a == b: return 0
            if a == 0: return b
            if b == 0: return a
            if a == 1: return self._fold(NOT, (b,))
            if b == 1: return self._fold(NOT, (a,))
        elif op == NOT:
            a = fi[0]
            if a == 0: return 1
            if a == 1: return 0
            if op_[a] == NOT and not site_[a]: return self.fi[a][0]
        elif op == MUX:
            s, b, a = fi
            if s == 1: return b
            if s == 0: return a
            if a == b: return a
            if b == 1 and a == 0: return s
            if b == 0 and a == 1: return self._fold(NOT, (s,))
            if b == 1: return self._fold(OR, (s, a))
            if a == 0: return self._fold(AND, (s, b))
        if op in COMM and fi[0] > fi[1]:
            fi = (fi[1], fi[0])
        return (op, fi)

    def gate(self, op, fi, site, key):
        r = self._fold(op, fi)
        if site:
            if r == 0 or r == 1: return self.new(C1 if r else C0, (), True, key)
            if isinstance(r, int): return self.new(BUF, (r,), True, key)
            return self.new(r[0], r[1], True, key)
        if isinstance(r, int):
            return r
        h = self._hash.get(r)
        if h is None:
            h = self._hash[r] = self.new(r[0], r[1], False, key)
        return h

    def readers(self):
        rd = [[] for _ in self.op]
        for i, fi in enumerate(self.fi):
            for f in set(fi):
                rd[f].append(i)
        return rd

    def downstream(self, roots, rd=None):
        rd = rd or self.readers()
        seen = set(roots); st = list(roots)
        while st:
            for r in rd[st.pop()]:
                if r not in seen:
                    seen.add(r); st.append(r)
        return seen

    def stats(self):
        return dict(nodes=len(self.op) - 2, sites=sum(self.site), observed=len(self.obs))


class Unrolled:
    """dag; hit[t] = list of (node, want) or None (goal impossible at cycle t); quiet[t] likewise; neq = (nodes, key)
    or None; at[t] = {net: node}; in_nodes = {(net, t or None): node}."""


def unroll(P):
    c = P.circ
    dist = c.dist(P.observed_nets())
    order = [b for b in c.topo(list(P.observed_nets()) + [c.flops[q][0] for q in c.flops if q in dist])
             if b in dist]
    qs = [q for q in c.flops if q in dist]
    d = Dag(); U = Unrolled(); U.dag = d; U.P = P
    N = P.N
    U.at = []; U.in_nodes = {}
    sites = P.sites

    def in_node(b, t):
        m = P.mode(b)
        if m == 0 or m == 1 or m is False or m is True: return 1 if m else 0
        k = (b, None if m == 'const' else t)
        n = U.in_nodes.get(k)
        if n is None:
            n = U.in_nodes[k] = d.new(IN, (), False, ('in', b, k[1]))
        return n
    prev = {}
    for t in range(N):
        slack = N - 1 - t
        cur = {}

        def ref(b):
            if b == '0': return 0
            if b == '1': return 1
            n = cur.get(b)
            if n is not None: return n
            if b in c.inputs:
                n = cur[b] = in_node(b, t)
                return n
            raise CircuitError('internal: net %s read before it was built at cycle %d' % (c.name(b), t))
        for q in qs:
            if dist[q] > slack: continue
            pre = (1 if c.flops[q][1] else 0) if t == 0 else prev[q]
            if q in sites:
                cur[q] = d.new(C1 if pre == 1 else C0, (), True, (t, q)) if pre in (0, 1) else d.new(BUF, (pre,), True, (t, q))
            else:
                cur[q] = pre
        for b in order:
            if dist[b] > slack: continue
            op, fi = c.gates[b]
            cur[b] = d.gate(op, tuple(ref(f) for f in fi), b in sites, (t, b))
        if t + 1 < N:
            prev = {q: ref(c.flops[q][0]) for q in qs if dist[q] <= slack - 1}
        for b in list(P.observed_nets()) + (list(P.neq[0]) if P.neq else []):
            if isinstance(b, int) and b not in cur and b in c.inputs: ref(b)
        U.at.append(cur)

    def cond(lst, t):
        """[(node, want)] with hard constants removed; None when a hard constant contradicts it."""
        out = []
        for b, want in lst:
            n = 0 if b == '0' else 1 if b == '1' else U.at[t][b]
            if n in (0, 1):
                if bool(n) != want: return None
                continue
            out.append((n, want))
        return out
    U.hit = []; U.quiet = []
    dead = False
    for t in range(N):
        q = cond(P.quiet, t)
        if q is None: dead = True
        U.quiet.append(None if dead else q)
        U.hit.append(None if dead else cond(P.goal, t))
    last = max([t for t in range(N) if U.hit[t] is not None], default=-1)
    for t in range(N):
        if t > last: U.quiet[t] = None
    U.neq = None
    if P.neq:
        nodes = []
        for b in P.neq[0]:
            if b in ('0', '1'): nodes.append(int(b))
            else:
                m = P.mode(b)
                nodes.append((1 if m else 0) if m in (0, 1, True, False) else in_node(b, None))
        U.neq = (nodes, P.neq[1])
    _compact(U)
    return U


def _compact(U):
    d = U.dag
    obs = set()
    for t in range(len(U.hit)):
        for lst in (U.hit[t], U.quiet[t]):
            if lst: obs.update(n for n, _ in lst)
    live = set(obs); st = list(obs)
    while st:
        for f in d.fi[st.pop()]:
            if f not in live:
                live.add(f); st.append(f)
    keepin = set(U.neq[0]) if U.neq else set()
    remap = {0: 0, 1: 1}
    nd = Dag()
    for i in range(2, len(d)):
        if i in live or i in keepin:
            remap[i] = nd.new(d.op[i], tuple(remap[f] for f in d.fi[i]), d.site[i], d.key[i])
    nd.obs = {remap[n] for n in obs}
    U.dropped_dead = len(d) - len(nd)
    U.dag = nd
    U.hit = [None if h is None else [(remap[n], w) for n, w in h] for h in U.hit]
    U.quiet = [None if h is None else [(remap[n], w) for n, w in h] for h in U.quiet]
    if U.neq: U.neq = ([remap[n] for n in U.neq[0]], U.neq[1])
    U.at = [{b: remap[n] for b, n in cur.items() if n in remap} for cur in U.at]
    U.in_nodes = {k: remap[n] for k, n in U.in_nodes.items() if n in remap}
