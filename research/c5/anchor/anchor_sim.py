#!/usr/bin/env python3
"""z3-FREE, shares NO code with b3pack/faultpack/modelsim/bf_b3/glitchsat.
Bit-parallel gate simulator over all 256 values of the free constant input `sig` (python big ints as 256-bit lanes),
plus exhaustive enumeration of all event sets of size <= K (DFS over cycles with state sharing, multiprocessing).
Goal: boot_word == 0x96 observed at some cycle t < T on a lane whose sig != 0xC3. Init: netnames 'init' attr, else 0.
Events (one event = cost 1):
  flip   (t, net)            : net value xor 1 (gate output or flop Q) in cycle t; seen by all fanout and by the output port
  action (t, gates, flops)   : RAIL DIP: every gate output in `gates` forced to 0 in cycle t; flop captures at end of cycle t
                               for flops in `flops` capture 0 (D AND 0). Several events in one cycle = union of their sets.
usage: anchor_sim.py NETLIST TOP MODEL T K [--procs N]    MODEL in stem_flip|rail_all|rail_half|rail_cone|rail_unions
"""
import json, re, sys, itertools, collections, time, multiprocessing as mp
LANES = 256; ALL = (1 << LANES) - 1; KEY = 0xC3
SIG = [sum(1 << s for s in range(LANES) if (s >> i) & 1) for i in range(8)]
VALID = ALL ^ (1 << KEY)

class Net:
    def __init__(self, path, top):
        m = json.load(open(path))['modules'][top]
        self.sigbits = m['ports']['sig']['bits']; self.word = m['ports']['boot_word']['bits']
        self.okbit = m['ports']['boot_ok']['bits'][0]
        self.gates = {}; self.gunit = {}; self.flops = []; self.funit = {}
        for cn, c in m['cells'].items():
            cn_ = c['connections']
            u = re.match(r'\$flatten\\(.+?)\.', cn); u = re.sub(r'\[\d+\]$', '', u.group(1)) if u else ''
            if c['type'] == '$_DFF_P_':
                self.flops.append((cn_['D'][0], cn_['Q'][0])); self.funit[cn_['Q'][0]] = u
            else:
                self.gates[cn_['Y'][0]] = (c['type'], tuple((p, v[0]) for p, v in cn_.items() if p != 'Y')); self.gunit[cn_['Y'][0]] = u
        init = {}
        for x in m['netnames'].values():
            iv = x['attributes'].get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)): init[x['bits'][i]] = ch == '1'
        self.init = {q: (ALL if init.get(q) else 0) for _, q in self.flops}
        self.names = {}
        for n, x in m['netnames'].items():
            for i, b in enumerate(x['bits']):
                if isinstance(b, int) and (b not in self.names or (self.names[b].startswith('$') and not n.startswith('$'))):
                    self.names[b] = n if len(x['bits']) == 1 else '%s[%d]' % (n, i)
        # topological order by DFS from flop D pins and outputs
        seen = set(self.init) | set(self.sigbits); order = []
        def vis(b):
            if not isinstance(b, int) or b in seen: return
            seen.add(b)
            for _, s in self.gates[b][1]: vis(s)
            order.append(b)
        for d, _ in self.flops: vis(d)
        for b in self.word + [self.okbit]: vis(b)
        self.order = order
        self.sidx = {b: i for i, b in enumerate(self.sigbits)}
        self.fanout = collections.defaultdict(set)
        for y, (_, pins) in self.gates.items():
            for _, s in pins:
                if isinstance(s, int): self.fanout[s].add(y)

    def cycle(self, st, flip=(), gz=(), fz=()):
        """one cycle. returns (word_match_mask, ok_lanes, next_state)."""
        v = {}
        for q, val in st.items(): v[q] = (val ^ ALL) if q in flip else val
        def get(b):
            if b == '1': return ALL
            if isinstance(b, str): return 0
            i = self.sidx.get(b)
            return SIG[i] if i is not None else v[b]
        for b in self.order:
            ty, pins = self.gates[b]; a = [get(s) for _, s in pins]
            d = dict(zip((p for p, _ in pins), a))
            if ty == '$_AND_': r = d['A'] & d['B']
            elif ty == '$_OR_': r = d['A'] | d['B']
            elif ty == '$_XOR_': r = d['A'] ^ d['B']
            elif ty == '$_NOT_': r = ALL ^ d['A']
            elif ty == '$_MUX_': r = (d['B'] & d['S']) | (d['A'] & (ALL ^ d['S']))
            else: raise Exception('cell ' + ty)
            if b in flip: r ^= ALL
            if b in gz: r = 0
            v[b] = r
        m = ALL
        for i, b in enumerate(self.word): m &= get(b) if (0x96 >> i) & 1 else ALL ^ get(b)
        ok = get(self.okbit)
        nxt = {q: (0 if q in fz else get(d)) for d, q in self.flops}
        return m & VALID, ok & VALID, nxt

    def sites_flip(self):
        return [('f', y) for y in list(self.gates) + [q for _, q in self.flops]]

    def actions(self, model):
        """list of (name, gates frozenset, flops frozenset); rail dips"""
        gates = set(self.gates); qs = {q for _, q in self.flops}; A = []
        if model == 'rail_all': A.append(('rail_all', frozenset(gates), frozenset(qs)))
        elif model in ('rail_half', 'rail_unions'):
            U = collections.defaultdict(lambda: (set(), set()))
            for y, u in self.gunit.items(): U[u][0].add(y)
            for q, u in self.funit.items(): U[u][1].add(q)
            names = sorted(U)
            for r in range(1, len(names) + 1):
                for sub in itertools.combinations(names, r):
                    g = set().union(*[U[n][0] for n in sub]); f = set().union(*[U[n][1] for n in sub])
                    if model == 'rail_half' and 2 * len(g) > len(gates): continue
                    if g or f: A.append(('+'.join(n or 'top' for n in sub), frozenset(g), frozenset(f)))
        elif model == 'rail_cone':
            for r in list(gates) + list(qs):
                cone, stack = set(), [r]
                while stack:
                    x = stack.pop()
                    for y in self.fanout[x]:
                        if y not in cone: cone.add(y); stack.append(y)
                if cone: A.append(('cone_' + self.names.get(r, str(r)), frozenset(cone), frozenset()))
        else: raise ValueError(model)
        u = {}
        for a in A: u[(a[1], a[2])] = a
        return list(u.values())

# ---------------- enumeration
G = {}
def setup(path, top, model, T, K):
    N = Net(path, top); G.update(N=N, T=T, K=K, model=model)
    if model == 'stem_flip':
        G['ev'] = [[(('f', y), frozenset([y]), frozenset(), frozenset()) for y in N.sites_flip_ids()] for _ in range(T)] if hasattr(N, 'sites_flip_ids') else None
    return N

def event_lists(N, model, T):
    if model == 'stem_flip':
        ids = list(N.gates) + [q for _, q in N.flops]
        return [[(y, frozenset([y]), frozenset(), frozenset()) for y in ids] for _ in range(T)]
    A = N.actions(model)
    return [[(n, frozenset(), g, f) for (n, g, f) in A] for _ in range(T)]

def merge(sub):
    fl = set(); gz = set(); fz = set()
    for _, a, b, c in sub: fl |= a; gz |= b; fz |= c
    return fl, gz, fz

def init_worker(path, top, model, T, K):
    N = Net(path, top); G.update(N=N, T=T, K=K, model=model, ev=event_lists(N, model, T))

def rec(t, st, left, used, hit, okh, chosen, out):
    N = G['N']; T = G['T']
    if t == T:
        out['count'][used] += 1
        if hit: out['hit'][used] += 1
        if okh: out['okhit'][used] += 1
        if hit and len(out['wit']) < 3 and (not out['wit'] or len(out['wit'][-1][0]) != len(chosen) or True):
            if used not in out['wit_sizes']: out['wit_sizes'].add(used); out['wit'].append((list(chosen), hit))
        return
    ev = G['ev'][t]
    for j in range(0, left + 1):
        for sub in itertools.combinations(ev, j):
            fl, gz, fz = merge(sub)
            if j and len(fl) != sum(len(s[1]) for s in sub): continue   # same net flipped twice in one cycle is not a valid set
            h, ok, nx = N.cycle(st, fl, gz, fz)
            rec(t + 1, nx, left - j, used + j, hit | h, okh | ok, chosen + [(t, N.names.get(s[0], s[0]) if isinstance(s[0], int) else s[0]) for s in sub], out)

def work(first):
    """first = tuple of event indices chosen at cycle 0"""
    N = G['N']; ev0 = G['ev'][0]; sub = [ev0[i] for i in first]
    out = dict(count=collections.Counter(), hit=collections.Counter(), okhit=collections.Counter(), wit=[], wit_sizes=set())
    fl, gz, fz = merge(sub)
    if len(first) and len(fl) != sum(len(s[1]) for s in sub): return out
    h, ok, nx = N.cycle(N.init, fl, gz, fz)
    rec(1, nx, G['K'] - len(first), len(first), h, ok, [(0, N.names.get(s[0], s[0]) if isinstance(s[0], int) else s[0]) for s in sub], out)
    return out

def run(path, top, model, T, K, procs=4):
    init_worker(path, top, model, T, K)
    n0 = len(G['ev'][0]); firsts = [()]
    for j in range(1, K + 1): firsts += list(itertools.combinations(range(n0), j))
    tot = dict(count=collections.Counter(), hit=collections.Counter(), okhit=collections.Counter(), wit=[], wit_sizes=set())
    t0 = time.time()
    with mp.Pool(procs, initializer=init_worker, initargs=(path, top, model, T, K)) as p:
        for o in p.imap_unordered(work, firsts, chunksize=16):
            for k in ('count', 'hit', 'okhit'): tot[k].update(o[k])
            for w in o['wit']:
                if len(w[0]) not in tot['wit_sizes'] and len(tot['wit']) < 12: tot['wit_sizes'].add(len(w[0])); tot['wit'].append(w)
    res = dict(netlist=path, model=model, T=T, K=K, n_events_per_cycle=n0, combos_total=sum(tot['count'].values()),
               attacking_by_size={k: tot['hit'][k] for k in range(K + 1)}, combos_by_size={k: tot['count'][k] for k in range(K + 1)},
               min_cost=next((k for k in range(K + 1) if tot['hit'][k]), None), secs=round(time.time() - t0, 1),
               ok_attacking_by_size={k: tot['okhit'][k] for k in range(K + 1)},
               witness=[(w[0], 'lanes=%d first_sig=0x%02X' % (bin(w[1]).count('1'), (w[1] & -w[1]).bit_length() - 1)) for w in tot['wit']])
    return res

if __name__ == '__main__':
    a = sys.argv[1:]
    procs = int(a[a.index('--procs') + 1]) if '--procs' in a else 4
    r = run(a[0], a[1], a[2], int(a[3]), int(a[4]), procs)
    print(json.dumps(r))
