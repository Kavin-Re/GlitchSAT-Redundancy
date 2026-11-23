"""Fault-site reduction on the unrolled DAG. All steps are sound for every fault budget (README section 4.2).

The common notion is *toggle dominance*: site a is covered by site d (a <= d) when, for every input and every set
of other flips, flipping a changes the observed nodes either not at all or exactly as toggling d would. Then any
attack that uses a can be rewritten without a and without growing, so a needs no fault variable.

structural()   a <= d whenever d post-dominates a in the DAG (every path from a to an observed node goes through d).
               Proved by the graph alone. The fan-out-free rule of FIRMER (Tan et al., Theorem 2) and the fault
               collapsing of ext/fastsat are the special case "a has one reader".
functional()   among the remaining sites: candidates from random-simulation signatures (same observed effect in every
               sample, or no effect in any sample), each confirmed by a SAT miter that leaves every other site free
               (so it holds in every fault context); unconfirmed candidates are kept.
"""
import random, time
from .circuit import AND, OR, XOR, NOT, MUX
from .unroll import C0, C1, IN, BUF
from . import sim, fastsat


def post_dominators(d):
    """ipdom[i] for every node (sink = len(d)). Observed nodes have the sink as a successor."""
    n = len(d); sink = n
    rd = d.readers()
    ip = [sink] * (n + 1)
    for i in range(n - 1, 1, -1):
        cur = sink if i in d.obs else None
        for s in rd[i]:
            if cur is None: cur = s
            else:
                a, b = cur, s
                while a != b:
                    if a < b: a = ip[a]
                    else: b = ip[b]
                cur = a
                if cur == sink: break
        ip[i] = sink if cur is None else cur
    return ip, rd


def structural(d):
    """Returns (keep, cover): keep = set of site nodes that stay, cover[a] = kept site that covers a (for a not kept).
    Sites with no path to an observed node cannot occur in a compacted Dag."""
    ip, _ = post_dominators(d)
    n = len(d); sink = n
    above = [None] * (n + 1)              # nearest site strictly above in the post-dominator tree
    for i in range(n - 1, 1, -1):
        p = ip[i]
        above[i] = None if p == sink else (p if d.site[p] else above[p])
    keep = set(); cover = {}
    for i in range(n - 1, 1, -1):
        if not d.site[i]: continue
        if above[i] is None: keep.add(i)
        else:
            r = above[i]
            cover[i] = r if r in keep else cover[r]
    return keep, cover


def all_sites(d):
    return {i for i in range(2, len(d)) if d.site[i]}


# ---------------------------------------------------------------- functional (signatures + SAT confirmation)
def _sparse(rng, W, r):
    w = rng.getrandbits(W)
    for _ in range(r - 1):
        w &= rng.getrandbits(W)
    return w


def signatures(d, cand, W=512, seed=1, deadline=None):
    """sig[a] = observed effect of toggling a in W random samples (random inputs; the upper half of the samples also
    has a few random other flips). Returns {a: tuple} (only for candidates finished before the deadline)."""
    rng = random.Random(seed)
    mask = (1 << W) - 1
    half = ((1 << (W // 2)) - 1) << (W // 2)
    sites = [i for i in range(2, len(d)) if d.site[i]]
    r = max(3, (max(len(sites), 8) // 3).bit_length())
    inw = {i: rng.getrandbits(W) for i in range(2, len(d)) if d.op[i] == IN}
    flip = {}
    for s in sites:
        w = _sparse(rng, W, r) & half
        if w: flip[s] = w
    val = sim.dag_eval(d, inw, mask, flip)
    rd = d.readers()
    obs = d.obs
    sig = {}
    for k, a in enumerate(cand):
        if deadline is not None and (k & 15) == 0 and time.time() > deadline: break
        new = sim.toggle_effect(d, val, mask, a, rd, flip)
        sig[a] = tuple(sorted((o, new[o] ^ val[o]) for o in new if o in obs))
    return sig


class Miter:
    """SAT check of "toggling a is a no-op or equals toggling dnode, for all inputs and all other flips"."""

    def __init__(self, d, rd=None):
        self.d = d; self.rd = rd or d.readers(); self.fs = fastsat()
        import minicdcl
        self.cdcl = minicdcl

    def check(self, a, dn=None, conflict_limit=20000, deadline=None, max_cone=None):
        """True = proved, False = refuted (a counterexample exists), None = not decided."""
        d = self.d; fs = self.fs
        roots = [a] if dn is None else [a, dn]
        cone = d.downstream(roots, self.rd)
        if max_cone is not None and len(cone) > max_cone: return None
        e = fs.Encoding()
        free = {}

        def side(j):
            """Literal of a node outside the cone, shared by the copies: a site or an input is a free variable (its
            flip, or the input, can make it anything); other gates are encoded from their fan-ins."""
            if j == 0: return fs.F_
            if j == 1: return fs.T_
            v = free.get(j)
            if v is not None: return v
            st = [j]
            while st:
                x = st[-1]
                if x in free or x < 2: st.pop(); continue
                if d.site[x] or d.op[x] == IN:
                    free[x] = e.new_var(); st.pop(); continue
                pend = [f for f in d.fi[x] if f >= 2 and f not in free]
                if pend: st.extend(pend); continue
                free[x] = self._gate(e, d.op[x], [fs.F_ if f == 0 else fs.T_ if f == 1 else free[f] for f in d.fi[x]])
                st.pop()
            return free[j]
        order = sorted(cone)
        fv = {j: e.new_var() for j in order if d.site[j] and j != a}
        copies = []
        for c in range(2 if dn is None else 3):
            lit = {}
            for j in order:
                x = [lit[f] if f in lit else side(f) for f in d.fi[j]]
                v = self._gate(e, d.op[j], x)
                if j == a:
                    if c == 0: v = -v
                elif j in fv:
                    f = fv[j]
                    v = e.g_xor(v, -f if (c == 2 and j == dn) else f)
                lit[j] = v
            copies.append(lit)
        obs = [o for o in order if o in d.obs]
        for c in range(1, len(copies)):
            diffs = [e.g_xor(copies[0][o], copies[c][o]) for o in obs]
            if fs.T_ in diffs: continue
            diffs = [x for x in diffs if x != fs.F_]
            if not diffs: return True
            e.add(diffs)
        s = self.cdcl.Solver(e.nvars)
        for cl in e.clauses: s.add_clause(cl)
        r = s.solve((), deadline=deadline, conflict_limit=conflict_limit)
        return None if r is None else (not r)

    @staticmethod
    def _gate(e, op, x):
        if op == AND: return e.g_and(x[0], x[1])
        if op == OR: return e.g_or(x[0], x[1])
        if op == XOR: return e.g_xor(x[0], x[1])
        if op == NOT: return -x[0]
        if op == MUX: return e.g_mux(x[0], x[1], x[2])
        if op == BUF: return x[0]
        if op == C1: return 1
        if op == C0: return -1
        raise ValueError(op)


def functional(d, keep, time_s=20.0, W=512, conflict_limit=20000, max_cone=6000, seed=1):
    """Shrink `keep`. Returns (keep2, cover2, info). cover2[a] = kept site covering a, or None when toggling a was
    proved to be a no-op in every context."""
    t0 = time.time(); deadline = t0 + time_s
    cand = sorted(keep)
    sig = signatures(d, cand, W=W, seed=seed, deadline=t0 + 0.5 * time_s)
    info = dict(candidates_zero=0, candidates_equal=0, proved_noop=0, proved_equal=0, refuted=0, undecided=0,
                signatures=len(sig), complete=len(sig) == len(cand))
    m = Miter(d)
    keep2 = set(keep); cover = {}
    groups = {}
    for a in cand:
        if a not in sig: continue
        if not sig[a]:
            info['candidates_zero'] += 1
            r = m.check(a, None, conflict_limit, deadline, max_cone)
            if r is True:
                keep2.discard(a); cover[a] = None; info['proved_noop'] += 1
            elif r is False: info['refuted'] += 1
            else: info['undecided'] += 1
        else:
            groups.setdefault(sig[a], []).append(a)
    for g in groups.values():
        if len(g) < 2: continue
        reps = []
        for a in sorted(g, reverse=True):        # latest node first: it becomes the representative
            done = False
            for r in reps:
                info['candidates_equal'] += 1
                if time.time() > deadline:
                    info['undecided'] += 1; continue
                res = m.check(a, r, conflict_limit, deadline, max_cone)
                if res is True:
                    keep2.discard(a); cover[a] = r; info['proved_equal'] += 1; done = True; break
                if res is False: info['refuted'] += 1
                else: info['undecided'] += 1
            if not done: reps.append(a)
    info['time_s'] = round(time.time() - t0, 3)
    return keep2, cover, info


def reduce_sites(U, level='struct', time_s=20.0, **kw):
    """level: 'time' (every live site), 'struct' (post-dominator roots), 'full' (struct + functional).
    Returns (keep, info)."""
    d = U.dag
    info = dict(level=level, sites_live=sum(d.site))
    if level == 'time':
        keep = all_sites(d)
    else:
        keep, cover = structural(d)
        info['sites_struct'] = len(keep)
        if level == 'full':
            keep, cov2, fi = functional(d, keep, time_s=time_s, **kw)
            info['functional'] = fi
        elif level != 'struct':
            raise ValueError('reduce level must be time, struct or full')
    info['sites_kept'] = len(keep)
    return keep, info
