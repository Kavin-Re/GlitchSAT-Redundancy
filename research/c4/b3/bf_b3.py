#!/usr/bin/env python3
"""INDEPENDENT brute-force checker for b3pack.py: B1's modelsim.Sim reader/topological order
(own JSON reader, no z3), NEW run2() adding rail-dip / early-capture, own re-derivation of the event groups (hierarchy units by
cell-name regex, cones by graph walk), exhaustive enumeration of all event sets of cost <= k, bit-parallel over 256 sig values."""
import json, re, itertools, collections, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modelsim as ms
ALL, KEY = ms.ALL, ms.KEY

class Sim2(ms.Sim):
    def __init__(self, path, top):
        super().__init__(path, top)
        m = json.load(open(path))['modules'][top]
        self.cellunit = {}
        for cn, c in m['cells'].items():
            con = c['connections']
            u = re.match(r'\$flatten\\(.+?)\.', cn); u = re.sub(r'\[\d+\]$', '', u.group(1)) if u else ''
            self.cellunit[con['Q'][0] if c['type'] == '$_DFF_P_' else con['Y'][0]] = u
    def run2(self, T, faults):
        """faults: tuples (t,'n',net,'flip'|'reset') (t,'d',q,'reset') (t,'e',q) early (t,'h',q) hold. Returns (words)."""
        by = collections.defaultdict(list)
        for f in faults: by[f[0]].append(f)
        st = dict(self.init); words = []
        for t in range(T):
            stem, dp, early, hold = {}, set(), set(), set()
            for f in by[t]:
                if f[1] == 'n': stem[f[2]] = f[3]
                elif f[1] == 'd': dp.add(f[2])
                elif f[1] == 'e': early.add(f[2])
                elif f[1] == 'h': hold.add(f[2])
            def one(state):
                v = {}
                def fx(x, eff): return x ^ ALL if eff == 'flip' else 0
                for q in state: v[q] = fx(state[q], stem[q]) if q in stem else state[q]
                def g(b):
                    if b in ('0', 'x'): return 0
                    if b == '1': return ALL
                    if b in self.sidx: return ms.SIGL[self.sidx[b]]
                    return v[b]
                for b in self.order:
                    ty, p = self.gates[b]; a = {pn: g(src) for pn, src in p.items()}
                    if ty == '$_AND_': r = a['A'] & a['B']
                    elif ty == '$_OR_': r = a['A'] | a['B']
                    elif ty == '$_XOR_': r = a['A'] ^ a['B']
                    elif ty == '$_NOT_': r = ALL ^ a['A']
                    elif ty == '$_MUX_': S = a['S']; r = (a['B'] & S) | (a['A'] & (ALL ^ S))
                    else: raise Exception(ty)
                    if b in stem: r = fx(r, stem[b])
                    v[b] = r
                dv = {q: (0 if q in dp else 1) & g(d) if q in dp else g(d) for d, q in self.flops}
                return g, dv
            g, dv = one(st)
            if early:
                st2 = {q: (dv[q] if q in early else st[q]) for q in st}
                g, dv = one(st2)
            words.append([g(b) for b in self.out])
            st = {q: (st[q] if q in hold else dv[q]) for _, q in self.flops}
        return words

def groups(sim, family):
    gates = set(sim.gates); qs = {q for _, q in sim.flops}
    U = collections.defaultdict(lambda: (set(), set()))
    for b, u in sim.cellunit.items():
        (U[u][1] if b in qs else U[u][0]).add(b)
    out = []
    if family == 'all': out.append((gates, qs))
    elif family in ('unions', 'half'):
        names = sorted(U)
        for r in range(1, len(names) + 1):
            for sub in itertools.combinations(names, r):
                g = set().union(*[U[n][0] for n in sub]); f = set().union(*[U[n][1] for n in sub])
                if family == 'half' and 2 * len(g) > len(gates): continue
                out.append((g, f))
    elif family == 'cone':
        fo = collections.defaultdict(set)
        for y, (ty, p) in sim.gates.items():
            for s in p.values():
                if isinstance(s, int): fo[s].add(y)
        for r in list(sim.gates) + list(qs):
            cone, st = set(), [r]
            while st:
                x = st.pop()
                for y in fo[x]:
                    if y not in cone: cone.add(y); st.append(y)
            if cone: out.append((cone, set()))
    return out

def actions(sim, T, model):
    """list of actions; action = tuple of fault tuples."""
    qs = [q for _, q in sim.flops]; acts = []
    for t in range(T):
        if model == 'stem_flip':
            acts += [((t, 'n', b, 'flip'),) for b in qs + list(sim.gates)]
        elif model.startswith('rail_'):
            fam = {'rail_all': 'all', 'rail_half': 'half', 'rail_unions': 'unions', 'rail_cone': 'cone'}[model]
            for g, f in groups(sim, fam):
                acts.append(tuple([(t, 'n', y, 'reset') for y in g] + [(t, 'd', q) + ('reset',) for q in f]))
        elif model == 'reset_one': acts += [((t, 'n', y, 'reset'),) for y in sim.gates]
        elif model == 'dip_subset':
            sites = [(t, 'n', y, 'reset') for y in sim.gates] + [(t, 'd', q, 'reset') for q in qs]
            for r in range(1, len(sites) + 1):
                for sub in itertools.combinations(sites, r): acts.append(tuple(sub))
        elif model == 'early_one': acts += [((t, 'e', q),) for q in qs]
        elif model == 'early_all': acts.append(tuple((t, 'e', q) for q in qs))
        elif model == 'early_subset':
            for r in range(1, len(qs) + 1):
                for sub in itertools.combinations(qs, r): acts.append(tuple((t, 'e', q) for q in sub))
        elif model == 'hold_one':
            if t <= T - 2: acts += [((t, 'h', q),) for q in qs]
        elif model == 'hold_subset':
            if t <= T - 2:
                for r in range(1, len(qs) + 1):
                    for sub in itertools.combinations(qs, r): acts.append(tuple((t, 'h', q) for q in sub))
    u = {}
    for a in acts: u[frozenset(a)] = a
    return list(u.values())

def hit(sim, T, flt, goal):
    w = sim.run2(T, flt)
    if goal == 'word': return ms.hit_lanes(w)
    m = 0
    for x in w: m |= x[sim.out.index(sim.okbit)] if hasattr(sim, 'okbit') else 0
    return m & ms.BAD

def min_cost(sim, T, model, kmax):
    acts = actions(sim, T, model); tried = 0
    for k in range(kmax + 1):
        for combo in itertools.combinations(acts, k):
            fl = list(dict.fromkeys(f for a in combo for f in a))
            flips = [f[2] for f in fl if f[1] == 'n' and f[3] == 'flip']
            if len(set(flips)) != len(flips): continue
            tried += 1
            if ms.hit_lanes(sim.run2(T, fl)): return k, fl, tried
    return None, None, tried
