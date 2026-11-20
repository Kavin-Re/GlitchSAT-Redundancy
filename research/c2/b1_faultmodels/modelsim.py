#!/usr/bin/env python3
"""INDEPENDENT checker for faultpack.py: plain gate-level simulator (own JSON reader, no z3,
no code shared with faultpack) + exhaustive enumeration of all fault-action sets up to cost k. Bit-parallel over all 256
`sig` values (python big-int lanes). Goal as in the engine: boot_word == 0x96 at some cycle < T while sig != 0xC3, sig constant.

Fault tuple (all single-cycle): (t,'n',net,eff) stem | (t,'g',gate_out,pin,eff) gate input pin | (t,'d',q,eff) flop D pin |
(t,'o',bit,eff) observed output-port bit | (t,'h',q) hold (flop keeps old Q at the edge ending cycle t). eff in flip/set/reset.
"""
import json, itertools, sys, collections
LANES = 256; ALL = (1 << LANES) - 1; KEY = 0xC3
SIGL = [sum(1 << s for s in range(LANES) if (s >> i) & 1) for i in range(8)]
BAD = ALL ^ (1 << KEY)


class Sim:
    def __init__(self, path, top):
        m = json.load(open(path))['modules'][top]
        self.sig = m['ports']['sig']['bits']; self.out = m['ports']['boot_word']['bits']
        self.gates = {}; self.flops = []   # flops: (d,q)
        for c in m['cells'].values():
            con = c['connections']
            if c['type'] == '$_DFF_P_': self.flops.append((con['D'][0], con['Q'][0]))
            else: self.gates[con['Y'][0]] = (c['type'], {p: v[0] for p, v in con.items() if p != 'Y'})
        init = {}
        for x in m['netnames'].values():
            iv = x['attributes'].get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)): init[x['bits'][i]] = ch == '1'
        self.init = {q: (ALL if init.get(q) else 0) for _, q in self.flops}
        # topological order of gates
        seen = set(self.init) | set(self.sig); order = []
        def vis(b):
            if not isinstance(b, int) or b in seen: return
            seen.add(b)
            for v in self.gates[b][1].values(): vis(v)
            order.append(b)
        for d, _ in self.flops: vis(d)
        for b in self.out: vis(b)
        self.order = order
        self.gate_all = list(self.gates)     # all gate outputs (even outside order) for site enumeration
        self.sidx = {b: i for i, b in enumerate(self.sig)}

    # ---- enumeration of sites (own code)
    def pin_list(self, inputs=False):
        res = []
        for y, (ty, p) in self.gates.items():
            for pn, src in p.items():
                if isinstance(src, int) and (inputs or src not in self.sidx): res.append(('g', y, pn, src))
        for d, q in self.flops:
            if isinstance(d, int) and (inputs or d not in self.sidx): res.append(('d', q, d))
        for i, b in enumerate(self.out):
            if isinstance(b, int) and (inputs or b not in self.sidx): res.append(('o', i, b))
        return res

    def sites(self, T, site, effects, inputs=False):
        """list of (fault_tuple, source_net)"""
        out = []
        for t in range(T):
            for eff in effects:
                if eff == 'hold':
                    if t <= T - 2:
                        for d, q in self.flops: out.append(((t, 'h', q), q))
                    continue
                if site in ('stem', 'both'):
                    for d, q in self.flops: out.append(((t, 'n', q, eff), q))
                    for y in self.gates: out.append(((t, 'n', y, eff), y))
                    if inputs:
                        for b in self.sig: out.append(((t, 'n', b, eff), b))
                if site in ('branch', 'both'):
                    for pn in self.pin_list(inputs):
                        if pn[0] == 'g': out.append(((t, 'g', pn[1], pn[2], eff), pn[3]))
                        elif pn[0] == 'd': out.append(((t, 'd', pn[1], eff), pn[2]))
                        else: out.append(((t, 'o', pn[1], eff), pn[2]))
        return out

    def hood_groups(self):
        """own re-implementation: for each gate output y: {y} + non-input nets feeding y + nets (gate/flop) fed by y"""
        fo = collections.defaultdict(set)
        for y, (ty, p) in self.gates.items():
            for src in p.values():
                if isinstance(src, int): fo[src].add(y)
        for d, q in self.flops:
            if isinstance(d, int): fo[d].add(q)
        gs = set()
        for y, (ty, p) in self.gates.items():
            s = {y} | {src for src in p.values() if isinstance(src, int) and src not in self.sidx} | fo[y]
            gs.add(frozenset(s))
        return list(gs)

    def cone_groups(self):
        """own re-implementation: {r} + gate outputs in the combinational fanout cone of r, r in gates|flop Qs|sig bits"""
        fo = collections.defaultdict(set)
        for y, (ty, p) in self.gates.items():
            for src in p.values():
                if isinstance(src, int): fo[src].add(y)
        gs = set()
        for r in list(self.gates) + [q for _, q in self.flops] + list(self.sig):
            cone, st = {r}, [r]
            while st:
                x = st.pop()
                for y in fo[x]:
                    if y not in cone: cone.add(y); st.append(y)
            gs.add(frozenset(cone))
        return list(gs)

    # ---- simulation
    def run(self, T, faults):
        by = collections.defaultdict(list)
        for f in faults: by[f[0]].append(f)
        st = dict(self.init); words = []
        def fx(v, eff):
            if eff == 'flip': return v ^ ALL
            if eff == 'set': return ALL
            return 0
        for t in range(T):
            stem = {}; pin = {}; dpin = {}; opin = {}; hold = set()
            for f in by[t]:
                k = f[1]
                if k == 'n': stem[f[2]] = f[3]
                elif k == 'g': pin[(f[2], f[3])] = f[4]
                elif k == 'd': dpin[f[2]] = f[3]
                elif k == 'o': opin[f[2]] = f[3]
                elif k == 'h': hold.add(f[2])
            v = {}
            for q in st: v[q] = fx(st[q], stem[q]) if q in stem else st[q]
            def g(b):
                if b == '0' or b == 'x': return 0
                if b == '1': return ALL
                if b in self.sidx:
                    x = SIGL[self.sidx[b]]
                    return fx(x, stem[b]) if b in stem else x
                return v[b]
            for b in self.order:
                ty, p = self.gates[b]
                a = {pn: (fx(g(src), pin[(b, pn)]) if (b, pn) in pin else g(src)) for pn, src in p.items()}
                if ty == '$_AND_': r = a['A'] & a['B']
                elif ty == '$_OR_': r = a['A'] | a['B']
                elif ty == '$_XOR_': r = a['A'] ^ a['B']
                elif ty == '$_NOT_': r = ALL ^ a['A']
                elif ty == '$_MUX_': S = a['S']; r = (a['B'] & S) | (a['A'] & (ALL ^ S))
                else: raise Exception(ty)
                if b in stem: r = fx(r, stem[b])
                v[b] = r
            words.append([fx(g(b), opin[i]) if i in opin else g(b) for i, b in enumerate(self.out)])
            nst = {}
            for d, q in self.flops:
                dv = g(d)
                if q in dpin: dv = fx(dv, dpin[q])
                nst[q] = st[q] if q in hold else dv
            st = nst
        return words


def hit_lanes(words, word=0x96):
    hit = 0
    for w in words:
        m = ALL
        for i, x in enumerate(w): m &= x if (word >> i) & 1 else ALL ^ x
        hit |= m
    return hit & BAD


def actions(sim, T, model, groups=None, m=1, singletons=True, exact=False):
    """Enumerate cost-1 actions as tuples of fault tuples. model: dict(site=, effects=)."""
    sites = sim.sites(T, model['site'], model['effects'], model.get('inputs', False))
    acts = []
    if singletons or not groups:
        acts += [(f,) for f, _ in sites]
    if groups and exact:   # whole group at once (all member sites, one effect), one event
        for gs in groups:
            for t in range(T):
                inn = tuple(f for f, src in sites if f[0] == t and src in gs)
                if len(inn) > 1: acts.append(inn)
    elif groups:
        for gs in groups:
            for t in range(T):
                inn = [f for f, src in sites if f[0] == t and src in gs]
                for r in range(2 if not singletons else 2, min(m, len(inn)) + 1):
                    for sub in itertools.combinations(inn, r):
                        # reject two effects on the same site
                        keys = [s[:-1] if s[1] != 'h' else s for s in sub]
                        if len(set(keys)) == len(keys): acts.append(sub)
                if not singletons:
                    for sub in itertools.combinations(inn, 1): acts.append(sub)
    uniq = {}
    for a in acts: uniq[frozenset(a)] = a
    return list(uniq.values())


def min_cost_exhaustive(sim, T, model, kmax, groups=None, m=1, singletons=True, procs=1, exact=False):
    """Smallest cost k<=kmax with an attacking action set (all combos of k actions tried), else None. Returns (k, witness|None, n_sets_tried)"""
    acts = actions(sim, T, model, groups, m, singletons, exact)
    tried = 0
    for k in range(0, kmax + 1):
        for combo in itertools.combinations(acts, k):
            fl = list(dict.fromkeys(f for a in combo for f in a))
            keys = [f[:-1] if f[1] != 'h' else f for f in fl]
            if len(set(keys)) != len(keys): continue
            tried += 1
            if hit_lanes(sim.run(T, fl)): return k, fl, tried
    return None, None, tried


# ---- parallel k=2 helper (fork-based; module globals carry the work)
_G = {}
def _chunk(i):
    sim, T, acts = _G['sim'], _G['T'], _G['acts']
    tried = 0
    a = acts[i]
    for j in range(i + 1, len(acts)):
        fl = list(dict.fromkeys(list(a) + list(acts[j])))
        keys = [f[:-1] if f[1] != 'h' else f for f in fl]
        if len(set(keys)) != len(keys): continue
        tried += 1
        if hit_lanes(sim.run(T, fl)): return tried, fl
    return tried, None


def min_cost_exhaustive_par(sim, T, model, kmax, groups=None, m=1, singletons=True, procs=4, exact=False):
    """as min_cost_exhaustive but k=2 is spread over processes (kmax<=2)."""
    assert kmax <= 2
    k, w, tried = min_cost_exhaustive(sim, T, model, min(kmax, 1), groups, m, singletons, 1, exact)
    if k is not None or kmax < 2: return k, w, tried
    import multiprocessing as mp
    acts = actions(sim, T, model, groups, m, singletons, exact)
    _G.update(sim=sim, T=T, acts=acts)
    with mp.get_context('fork').Pool(procs) as pool:
        for n, fl in pool.imap_unordered(_chunk, range(len(acts)), chunksize=8):
            tried += n
            if fl: pool.terminate(); return 2, fl, tried
    return None, None, tried
