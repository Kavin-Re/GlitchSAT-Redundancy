"""Symmetry breaking for structurally identical copies, used only where it is proved to be sound.

find()          looks for permutations s of the unrolled DAG nodes that map the problem onto itself: same operator,
                same fan-ins (as a multiset for AND/OR/XOR, pin by pin for MUX), same site flag, same membership in
                the kept fault sites, same role in the goal and quiet conditions at every cycle, inputs and constants
                fixed. Candidates come from colour refinement; a candidate is used only if the full check passes.
add_breaking()  for every such s adds "the chosen flip set F is not lexicographically larger than s(F)" over the
                fault variables in node order.

Why this is sound (README section 4.5): s maps every attack to an attack of the same size with the same inputs, so
the attacks come in orbits; the lexicographically smallest member of an orbit satisfies every added constraint.
Satisfiability and the minimum for every budget and every horizon are unchanged. When no such permutation exists
(for example when the goal reads only one of two copies) nothing is added.
"""
import time
from .circuit import AND, OR, XOR, NOT, MUX
from .unroll import IN

COMM = (AND, OR, XOR)


def _roles(U):
    role = {}
    for tag, lists in (('h', U.hit), ('q', U.quiet)):
        for t, lst in enumerate(lists):
            for n, w in (lst or ()):
                role.setdefault(n, set()).add((tag, t, w))
    return {n: frozenset(r) for n, r in role.items()}


def _colours(U, keep, rounds=10):
    d = U.dag; n = len(d)
    role = _roles(U)
    rd = d.readers()
    col = [hash((d.op[i], d.site[i], i in keep, role.get(i), i if (d.op[i] == IN or i < 2) else -1)) for i in range(n)]
    last = len(set(col))
    for _ in range(rounds):
        new = [0] * n
        for i in range(n):
            fi = d.fi[i]
            fc = tuple(col[f] for f in fi) if d.op[i] == MUX else tuple(sorted(col[f] for f in fi))
            rc = tuple(sorted((col[r], d.fi[r].index(i) if d.op[r] == MUX else -1) for r in rd[i]))
            new[i] = hash((col[i], fc, rc))
        col = new
        cur = len(set(col))
        if cur == last: break
        last = cur
    return col, rd, role


def verify(U, keep, s):
    """Full check that the node map s (dict, identity elsewhere) is an automorphism of the encoded problem."""
    d = U.dag
    g = lambda i: s.get(i, i)
    if len(set(s.values())) != len(s) or set(s.values()) != set(s): return False
    for i, j in s.items():
        if i < 2 or j < 2 or d.op[i] == IN or d.op[j] == IN: return False
        if d.op[i] != d.op[j] or d.site[i] != d.site[j] or ((i in keep) != (j in keep)): return False
    moved = set(s)
    for i in range(2, len(d)):
        if i not in moved and not any(f in moved for f in d.fi[i]): continue
        a = tuple(g(f) for f in d.fi[i]); b = d.fi[g(i)]
        if d.op[i] == MUX:
            if a != b: return False
        elif sorted(a) != sorted(b): return False
    for lists in (U.hit, U.quiet):
        for lst in lists:
            if lst and {(g(n), w) for n, w in lst} != set(lst): return False
    return True


def _grow(d, col, rd, a, b):
    s = {}
    st = [(a, b)]

    def pair(u, v):
        if u == v: return u not in s
        if col[u] != col[v]: return False
        if u in s or v in s:
            return s.get(u) == v and s.get(v) == u
        s[u] = v; s[v] = u; st.append((u, v))
        return True
    if col[a] != col[b]: return None
    s[a] = b; s[b] = a
    while st:
        u, v = st.pop()
        fu, fv = d.fi[u], d.fi[v]
        if d.op[u] == MUX or len(fu) == 1:
            for x, y in zip(fu, fv):
                if not pair(x, y): return None
        elif len(fu) == 2:
            straight = col[fu[0]] == col[fv[0]] and col[fu[1]] == col[fv[1]]
            cross = col[fu[0]] == col[fv[1]] and col[fu[1]] == col[fv[0]]
            if straight and cross:
                cross = s.get(fu[0]) == fv[1] or s.get(fu[1]) == fv[0] or (fu[0] == fv[1] and fu[0] not in s and fu[1] != fv[1])
                straight = not cross
            if straight: ok = pair(fu[0], fv[0]) and pair(fu[1], fv[1])
            elif cross: ok = pair(fu[0], fv[1]) and pair(fu[1], fv[0])
            else: ok = False
            if not ok: return None
        by = {}
        for r in rd[u]: by.setdefault(col[r], [[], []])[0].append(r)
        for r in rd[v]: by.setdefault(col[r], [[], []])[1].append(r)
        for c_, (ru, rv) in by.items():
            if len(ru) != len(rv): return None
            if len(ru) == 1 and not pair(ru[0], rv[0]): return None
    return s


def find(U, keep, max_found=4, time_s=10.0):
    """Verified automorphisms (list of dicts node -> node, involutions)."""
    t0 = time.time()
    d = U.dag
    col, rd, role = _colours(U, keep)
    classes = {}
    for i in sorted(keep):
        classes.setdefault(col[i], []).append(i)
    out = []; seen = set()
    for c_, mem in sorted(classes.items(), key=lambda kv: kv[1][0]):
        if len(mem) < 2: continue
        a = mem[0]
        if a in seen: continue
        for b in mem[1:6]:
            if time.time() - t0 > time_s or len(out) >= max_found: return out
            s = _grow(d, col, rd, a, b)
            if s and verify(U, keep, s):
                out.append(s); seen.update(s)
                break
    return out


def add_breaking(M, syms, max_len=64):
    """Lex-leader clauses on the fault variables of Model M. Returns the number of clauses added."""
    e = M.e; n0 = len(e.clauses)
    for s in syms:
        pairs = [(M.F[i], M.F[s[i]]) for i in sorted(M.F) if s.get(i, i) != i][:max_len]
        prev = None                                  # literal: all earlier pairs were equal (None = TRUE)
        for k, (x, y) in enumerate(pairs):
            e.add(([-prev] if prev else []) + [-x, y])          # equal so far -> x <= y
            if k + 1 < len(pairs):
                nx = e.new_var()
                e.add(([-prev] if prev else []) + [x, y, nx])   # equal so far and x = y = 0 -> still equal
                e.add(([-prev] if prev else []) + [-x, -y, nx])
                prev = nx
    return len(e.clauses) - n0
