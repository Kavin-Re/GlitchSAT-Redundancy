"""Exhaustive fault simulation on gate netlists (numpy, no solver).

Fault model (the project's, MODELLED not physical): a fault is a one-cycle bit flip of the output net of a gate or of
the Q net of a flip-flop. A Q flip is seen by the logic and the outputs in that cycle; the stored value is unchanged.
The attacker input is one value held constant over all cycles and must differ from the key. The goal is reached when,
in some cycle, the goal output (under that cycle's flips) equals the goal value on the bits the consumer checks.

Two independent methods, both exhaustive:

  min_flips()       layered shortest-path search. A node is (cycle, input value, flop state); an edge is one clock
                    cycle with a chosen set of j flipped sites and costs j. Every set of j sites in one cycle is
                    simulated for every node that can still afford it, so every multiset of flips over the cycles is
                    covered. cycles=N gives the project's bounded question ("within N cycles"); cycles=None iterates
                    to a fixpoint and so covers every number of cycles (explicit-state search; needs few flops).
  enumerate_sets()  the literal brute force: every set of exactly k (cycle, site) pairs is simulated over N cycles for
                    all inputs at once, as validation/k2.py does. Slow for k >= 3; used to cross-check min_flips().

`reduce=True` drops fault sites that are dominated: a site whose only reader is one gate. Flipping it either flips that
gate's output or does nothing, so any attack using it has an equally small attack using the reader instead. The minimum
is unchanged (tested); the NUMBER of attacking sets is not preserved, so enumerate_sets() never reduces.
"""
import itertools, time
import numpy as np

ALL = np.uint64(0xFFFFFFFFFFFFFFFF)
INF = 255
_AND, _OR, _XOR, _NOT, _MUX, _NAND, _NOR, _XNOR, _ANDNOT, _ORNOT, _BUF = range(11)
_TCODE = {'$_AND_': _AND, '$_OR_': _OR, '$_XOR_': _XOR, '$_NOT_': _NOT, '$_MUX_': _MUX, '$_NAND_': _NAND, '$_NOR_': _NOR,
          '$_XNOR_': _XNOR, '$_ANDNOT_': _ANDNOT, '$_ORNOT_': _ORNOT, '$_BUF_': _BUF}


def _gate_fn(t, A, B, S):
    """Yosys simple-cell semantics on lane words (numpy arrays or Python ints with ~ masked by the caller)."""
    if t == _AND: return A & B
    if t == _OR: return A | B
    if t == _XOR: return A ^ B
    if t == _NOT: return ~A
    if t == _MUX: return (B & S) | (A & ~S)
    if t == _NAND: return ~(A & B)
    if t == _NOR: return ~(A | B)
    if t == _XNOR: return ~(A ^ B)
    if t == _ANDNOT: return A & ~B
    if t == _ORNOT: return A | ~B
    return A


class Goal:
    """Goal: (port & mask) == (value & mask). Default: boot_word == 0x96 on all 8 bits."""

    def __init__(self, out='boot_word', value=0x96, mask=None):
        self.out, self.value, self.mask = out, value, mask

    def resolve(self, nl):
        if self.out not in nl.ports or nl.ports[self.out][0] != 'output':
            raise ValueError(f'goal output {self.out!r} is not an output port of {nl.top}')
        w = len(nl.ports[self.out][1])
        mask = (1 << w) - 1 if self.mask is None else self.mask & ((1 << w) - 1)
        return [(b, (self.value >> i) & 1) for i, b in enumerate(nl.ports[self.out][1]) if (mask >> i) & 1]

    def describe(self):
        m = '' if self.mask is None else f' on bits mask 0x{self.mask:X}'
        return f'{self.out} == 0x{self.value:X}{m}'


class Compiled:
    def __init__(self, nl, goal, attack_input='sig', reduce=False):
        self.nl = nl
        self.inbits = list(nl.ports[attack_input][1])
        other = [b for b in nl.input_bits() if b not in self.inbits]
        if other:
            raise ValueError('inputs other than clk and the attacker input are not supported: ' + ', '.join(nl.name(b) for b in other))
        self.nin = len(self.inbits)
        if self.nin > 16:
            raise ValueError('attacker input wider than 16 bits: exhaustive input enumeration is not practical')
        self.flops = list(nl.flops)
        self.nf = len(self.flops)
        order = nl.topo()
        idx = {'0': 0, 'x': 0, '1': 1}
        for b in self.inbits:
            idx[b] = len(idx) - 1
        self.q_idx = []
        for d, q, _ in self.flops:
            idx[q] = len(idx) - 1
            self.q_idx.append(idx[q])
        self.g0 = len(idx) - 1
        for y in order:
            idx[y] = len(idx) - 1
        self.idx = idx
        self.nnodes = len(idx) - 1
        self.bit_of = {v: k for k, v in idx.items() if isinstance(k, int)}
        self.gt = [(idx[y], _TCODE[nl.gates[y][0]], idx[nl.gates[y][1]],
                    idx[nl.gates[y][2]] if nl.gates[y][2] is not None else 0,
                    idx[nl.gates[y][3]] if nl.gates[y][3] is not None else 0) for y in order]
        for d, q, _ in self.flops:
            if d not in idx:
                raise ValueError(f'flop D net {nl.name(d)} has no driver')
        self.d_idx = [idx[d] for d, _, _ in self.flops]
        self.goal = goal
        self.goal_bits = [(idx[b], v) for b, v in goal.resolve(nl)]
        self.init_state = sum(int(init) << i for i, (_, _, init) in enumerate(self.flops))
        all_sites = self.q_idx + [g[0] for g in self.gt]
        self.all_sites = all_sites
        dropped = set()
        if reduce:
            rd = nl.readers()
            for s in all_sites:
                r = rd.get(self.bit_of[s], [])
                if len(r) == 1 and r[0][0] == 'gate':
                    dropped.add(s)
        self.sites = np.array([s for s in all_sites if s not in dropped], dtype=np.int32)
        self.reduced = reduce
        self.sets_simulated = 0
        self.evals = 0

    def site_name(self, s):
        return self.nl.name(self.bit_of[int(s)])

    # ------------------------------------------------------------------------------------------------
    def eval(self, sigw, stw, fsets):
        """One clock cycle for F fault sets x W*64 lanes.
        sigw: (nin, W) uint64 lane words of the input bits; stw: (nf, W) of the flop state bits;
        fsets: (F, j) int array of site node indices (j may be 0, then F must be 1).
        Returns V: list of arrays (1 or F, W) per node (after flips)."""
        F, j = fsets.shape
        W = sigw.shape[1]
        V = [None] * self.nnodes
        V[0] = np.zeros((1, W), np.uint64)
        V[1] = np.full((1, W), ALL)
        for i in range(self.nin):
            V[2 + i] = sigw[i][None, :]
        rows_of = {}
        if j:
            flat = fsets.ravel()
            order = np.argsort(flat, kind='stable')
            fs = flat[order]
            rows = order // j
            cut = np.flatnonzero(np.diff(fs)) + 1
            starts = np.concatenate(([0], cut))
            ends = np.concatenate((cut, [len(fs)]))
            for a, b in zip(starts, ends):
                rows_of[int(fs[a])] = rows[a:b]
        for k, qi in enumerate(self.q_idx):
            v = stw[k][None, :]
            r = rows_of.get(qi)
            if r is not None:
                v = np.repeat(v, F, axis=0)
                v[r] ^= ALL
            V[qi] = v
        for y, t, a, b, s in self.gt:
            v = _gate_fn(t, V[a], V[b], V[s])
            r = rows_of.get(y)
            if r is not None:
                if v.shape[0] != F:
                    v = np.repeat(v, F, axis=0)
                v[r] ^= ALL
            V[y] = v
        self.sets_simulated += F
        self.evals += 1
        return V

    def goal_words(self, V):
        g = None
        for i, val in self.goal_bits:
            x = V[i] if val else ~V[i]
            g = x if g is None else (g & x)
        if g is None:
            raise ValueError('goal checks no bits')
        return g

    def next_state(self, V, L):
        """(1 or F, L) array of next-state integers."""
        nxt = None
        for k, di in enumerate(self.d_idx):
            bits = _unpack(V[di], L)
            term = bits.astype(np.uint32) << np.uint32(k)
            nxt = term if nxt is None else (nxt | term) if nxt.shape == term.shape else (nxt + 0) | term
        if nxt is None:
            nxt = np.zeros((1, L), np.uint32)
        return nxt


def _unpack(words, L):
    w = np.ascontiguousarray(words)
    return np.unpackbits(w.view(np.uint8), axis=1, bitorder='little')[:, :L]


def _pack_lanes(values, nbits):
    """values: (L,) ints -> (nbits, W) uint64 lane words (lane l carries bit i of values[l])."""
    L = len(values)
    W = (L + 63) // 64
    out = np.zeros((nbits, W), np.uint64)
    v = np.zeros(W * 64, np.uint64)
    v[:L] = values
    for i in range(nbits):
        bits = ((v >> np.uint64(i)) & np.uint64(1)).astype(np.uint8)
        out[i] = np.packbits(bits, bitorder='little').view(np.uint64)
    return out


def _lane_mask(L):
    W = (L + 63) // 64
    m = np.full(W, ALL)
    if L % 64:
        m[-1] = np.uint64((1 << (L % 64)) - 1)
    return m


def _site_sets(sites, j, chunk):
    """Yield (F, j) arrays covering every j-subset of sites."""
    n = len(sites)
    if j == 0:
        yield np.zeros((1, 0), np.int32)
        return
    if j == 1:
        for a in range(0, n, chunk):
            yield sites[a:a + chunk].reshape(-1, 1)
        return
    it = itertools.combinations(range(n), j)
    while True:
        blk = np.fromiter(itertools.chain.from_iterable(itertools.islice(it, chunk)), dtype=np.int32)
        if blk.size == 0:
            return
        yield sites[blk.reshape(-1, j)]


class Result:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def as_dict(self):
        return dict(self.__dict__)


def fault_free(nl, cycles, goal=None, attack_input='sig', watch=None):
    """Fault-free run for every input value. Returns dict port -> (cycles, 2**nin) ints, plus 'goal' (cycles, 2**nin) bool."""
    goal = goal or Goal()
    C = Compiled(nl, goal, attack_input)
    n = 1 << C.nin
    sig = np.arange(n, dtype=np.uint64)
    sigw = _pack_lanes(sig, C.nin)
    st = np.full(n, C.init_state, np.uint64)
    out = {p: np.zeros((cycles, n), np.int64) for p, (d, _) in nl.ports.items() if d == 'output'}
    out['goal'] = np.zeros((cycles, n), bool)
    out['state'] = np.zeros((cycles, n), np.int64)
    none = np.zeros((1, 0), np.int32)
    for t in range(cycles):
        out['state'][t] = st
        V = C.eval(sigw, _pack_lanes(st, C.nf), none)
        for p, (d, bits) in nl.ports.items():
            if d == 'output':
                acc = np.zeros(n, np.int64)
                for i, b in enumerate(bits):
                    acc |= _unpack(V[C.idx[b]], n)[0].astype(np.int64) << i
                out[p][t] = acc
        out['goal'][t] = _unpack(C.goal_words(V), n)[0].astype(bool)
        st = C.next_state(V, n)[0].astype(np.uint64)
    return out


def min_flips(nl, goal=None, kmax=3, cycles=6, key=0xC3, attack_input='sig', reduce=True, target_words=1 << 15,
              max_flops=14, time_limit=None):
    """Smallest number of modelled flips that reaches the goal with a wrong input, searching up to kmax flips.

    Returns Result(min_flips = int or None (none with <= kmax), exhaustive_up_to = kmax, cycles, witness, honest_ok,
    fault_free_wrong_accept, sets_simulated, sites, sites_total, runtime_s, method).
    witness = dict(input, flips=[(cycle, net name)]) and is re-checked with replay() before it is returned."""
    t0 = time.time()
    goal = goal or Goal()
    C = Compiled(nl, goal, attack_input, reduce=reduce)
    if C.nf > max_flops:
        raise ValueError(f'{C.nf} flops: explicit-state search is limited to {max_flops}; use enumerate_sets() (bounded) instead')
    NS, NI = 1 << C.nf, 1 << C.nin
    Tn = cycles if cycles else 1
    bounded = bool(cycles)
    cost = np.full((Tn, NI * NS), INF, np.uint8)
    kcap = max(kmax, 1)
    pstate = np.zeros((Tn, NI * NS), np.uint32)
    psites = np.full((Tn, NI * NS, kcap), -1, np.int32)
    sigs = np.array([s for s in range(NI) if s != key], dtype=np.int64)
    cost[0, sigs * NS + C.init_state] = 0
    done = np.zeros((Tn, NI * NS), bool)
    best, hit, limit = None, None, kmax
    timed_out = False

    def expand(t, nodes, c):
        nonlocal best, hit, limit
        lsig, lst = nodes // NS, nodes % NS
        L = len(nodes)
        W = (L + 63) // 64
        sigw, stw, lm = _pack_lanes(lsig.astype(np.uint64), C.nin), _pack_lanes(lst.astype(np.uint64), C.nf), _lane_mask(L)
        tn = (t + 1) if bounded else 0
        last = bounded and t == Tn - 1
        chunk = max(1, target_words // W)
        for j in range(0, kmax - c + 1):
            if c + j > limit:
                break
            for fs in _site_sets(C.sites, j, chunk):
                V = C.eval(sigw, stw, fs)
                g = C.goal_words(V) & lm
                if g.any():
                    r, w = np.nonzero(g)
                    r, w = int(r[0]), int(w[0])
                    word = int(g[r, w])
                    lane = w * 64 + (word & -word).bit_length() - 1
                    best, limit = c + j, c + j - 1
                    hit = (t, int(nodes[lane]), [int(x) for x in (fs[r] if j else [])])
                    break
                if last:
                    continue
                nxt = C.next_state(V, L)
                flat = lsig[None, :] * NS + nxt
                cur = cost[tn][flat]
                sel = cur > c + j
                if sel.any():
                    rr, ll = np.nonzero(sel)
                    f = flat[rr, ll]
                    f, first = np.unique(f, return_index=True)
                    rr, ll = rr[first], ll[first]
                    cost[tn][f] = c + j
                    pstate[tn][f] = lst[ll]
                    psites[tn][f] = -1
                    if j:
                        psites[tn][f, :j] = fs[rr]
                if time_limit and time.time() - t0 > time_limit:
                    return False
            if best is not None and c + j >= best:
                break
        return True

    c = 0
    while c <= limit and not timed_out:
        if bounded:
            for t in range(Tn):
                if c > limit:
                    break
                nodes = np.flatnonzero((cost[t] == c) & ~done[t])
                if len(nodes):
                    done[t][nodes] = True
                    if not expand(t, nodes, c):
                        timed_out = True
                        break
        else:
            while c <= limit:
                nodes = np.flatnonzero((cost[0] == c) & ~done[0])
                if not len(nodes):
                    break
                done[0][nodes] = True
                if not expand(0, nodes, c):
                    timed_out = True
                    break
        c += 1

    witness = None
    if hit is not None:
        t, node, last_sites = hit
        sig, state = node // NS, node % NS
        steps = [last_sites]
        tt = t
        guard = 0
        while not (state == C.init_state and int(cost[tt if bounded else 0][sig * NS + state]) == 0 and (tt == 0 if bounded else True)):
            layer = tt if bounded else 0
            f = sig * NS + state
            ps = [int(x) for x in psites[layer][f] if x >= 0]
            steps.append(ps)
            state = int(pstate[layer][f])
            tt -= 1
            guard += 1
            if guard > 100000:
                raise RuntimeError('witness reconstruction did not terminate')
        steps.reverse()
        flips = [(cyc, C.site_name(s)) for cyc, ss in enumerate(steps) for s in ss]
        witness = dict(input=int(sig), flips=flips, cycles_used=len(steps),
                       flip_bits=[(cyc, C.bit_of[s]) for cyc, ss in enumerate(steps) for s in ss])
        ok = replay(nl, goal, witness['input'], [(cyc, C.bit_of[s]) for cyc, ss in enumerate(steps) for s in ss], len(steps), attack_input)
        if not ok:
            raise RuntimeError('internal error: witness does not replay')
        witness['replayed'] = True
    ff = fault_free(nl, cycles or 8, goal, attack_input)
    reach = ff['goal'].any(axis=0)
    honest_ok = bool(key is not None and key < NI and reach[key])
    wrong = [int(s) for s in np.flatnonzero(reach) if s != key]
    return Result(min_flips=best, exhaustive_up_to=(kmax if not timed_out else None), timed_out=timed_out,
                  cycles=cycles if cycles else 'all', witness=witness, honest_ok=honest_ok, fault_free_wrong_accept=wrong[:8],
                  sets_simulated=int(C.sets_simulated), sites=int(len(C.sites)), sites_total=int(len(C.all_sites)),
                  states_touched=int((cost < INF).sum()), runtime_s=round(time.time() - t0, 3),
                  method='layered explicit-state search over all per-cycle flip sets' + (' (dominated sites dropped)' if reduce else ''),
                  goal=goal.describe())


def replay(nl, goal, sig, flips, cycles, attack_input='sig'):
    """Plain-Python single-run re-simulation (independent of the numpy code). flips = [(cycle, net id)].
    Returns True when the goal is reached in some cycle < cycles."""
    gb = goal.resolve(nl)
    inb = {b: (sig >> i) & 1 for i, b in enumerate(nl.ports[attack_input][1])}
    st = {q: int(init) for _, q, init in nl.flops}
    for t in range(cycles):
        f = {b for tt, b in flips if tt == t}
        val = {}

        def g(b):
            if b in ('0', 'x'): return 0
            if b == '1': return 1
            if b in inb: return inb[b]
            if b in st: return st[b] ^ (b in f)
            if b in val: return val[b]
            ty, a, bb, s = nl.gates[b]
            A = g(a)
            B = g(bb) if bb is not None else 0
            S = g(s) if s is not None else 0
            v = {'$_AND_': A & B, '$_OR_': A | B, '$_XOR_': A ^ B, '$_NOT_': 1 - A, '$_MUX_': B if S else A,
                 '$_NAND_': 1 - (A & B), '$_NOR_': 1 - (A | B), '$_XNOR_': 1 - (A ^ B), '$_ANDNOT_': A & (1 - B),
                 '$_ORNOT_': A | (1 - B), '$_BUF_': A}[ty]
            v ^= (b in f)
            val[b] = v
            return v
        if all(g(b) == v for b, v in gb):
            return True
        st = {q: g(d) for d, q, _ in nl.flops}
    return False


def enumerate_sets(nl, goal=None, k=2, cycles=6, key=0xC3, attack_input='sig', chunk=8192, max_sets=None):
    """Brute force: simulate EVERY set of exactly k (cycle, site) pairs over `cycles` cycles, all wrong inputs at once.
    Returns Result(sets, attacking_sets, examples, runtime_s). Sites = every gate output and flop Q (no reduction)."""
    t0 = time.time()
    goal = goal or Goal()
    C = Compiled(nl, goal, attack_input, reduce=False)
    NI = 1 << C.nin
    sigs = np.array([s for s in range(NI) if s != key], dtype=np.uint64)
    L = len(sigs)
    sigw, lm = _pack_lanes(sigs, C.nin), _lane_mask(L)
    W = sigw.shape[1]
    S = len(C.sites)
    npairs = S * cycles
    init = _pack_lanes(np.full(L, C.init_state, np.uint64), C.nf)
    total = attacking = 0
    examples = []
    it = itertools.combinations(range(npairs), k) if k else iter([()])
    while True:
        blk = np.fromiter(itertools.chain.from_iterable(itertools.islice(it, chunk)), dtype=np.int32) if k else np.zeros(0, np.int32)
        if k and blk.size == 0:
            break
        combos = blk.reshape(-1, k) if k else np.zeros((1, 0), np.int32)
        F = combos.shape[0]
        cyc, site = combos // S, C.sites[combos % S] if k else combos
        st = [np.repeat(init[i][None, :], F, axis=0) for i in range(C.nf)]
        hit = np.zeros((F, W), np.uint64)
        for t in range(cycles):
            # per-cycle fault sets have different sizes per row: pad with -1 (matches no node)
            fs = np.where(cyc == t, site, -1) if k else combos
            V = _eval_rows(C, sigw, st, fs)
            hit |= C.goal_words(V)
            if t + 1 < cycles:
                st = [np.broadcast_to(V[d], (F, W)) for d in C.d_idx]
        hit &= lm
        ok = hit.any(axis=1)
        total += F
        attacking += int(ok.sum())
        for r in np.flatnonzero(ok)[:max(0, 5 - len(examples))]:
            lanes = _unpack(hit[r:r + 1], L)[0]
            examples.append(dict(flips=[(int(cyc[r, i]), C.site_name(site[r, i])) for i in range(k)], inputs=int(lanes.sum()),
                                 example_input=int(sigs[int(np.flatnonzero(lanes)[0])])))
        if not k or (max_sets and total >= max_sets):
            break
    return Result(k=k, cycles=cycles, sets=total, attacking_sets=attacking, examples=examples, sites_per_cycle=S,
                  runtime_s=round(time.time() - t0, 3), method='brute force over every set of (cycle, site) pairs', goal=goal.describe())


def _eval_rows(C, sigw, st, fs):
    """Like Compiled.eval but the state is per row (list of (F, W)) and fs may contain -1 padding."""
    F = fs.shape[0]
    W = sigw.shape[1]
    V = [None] * C.nnodes
    V[0] = np.zeros((1, W), np.uint64)
    V[1] = np.full((1, W), ALL)
    for i in range(C.nin):
        V[2 + i] = sigw[i][None, :]
    rows_of = {}
    if fs.shape[1]:
        r, c = np.nonzero(fs >= 0)
        vals = fs[r, c]
        order = np.argsort(vals, kind='stable')
        vs, rs = vals[order], r[order]
        if len(vs):
            cut = np.flatnonzero(np.diff(vs)) + 1
            for a, b in zip(np.concatenate(([0], cut)), np.concatenate((cut, [len(vs)]))):
                rows_of[int(vs[a])] = rs[a:b]
    for k, qi in enumerate(C.q_idx):
        v = st[k]
        r = rows_of.get(qi)
        if r is not None:
            v = np.array(np.broadcast_to(v, (F, W)))
            v[r] ^= ALL
        V[qi] = v
    for y, t, a, b, s in C.gt:
        v = _gate_fn(t, V[a], V[b], V[s])
        r = rows_of.get(y)
        if r is not None:
            if v.shape[0] != F:
                v = np.repeat(v, F, axis=0)
            v[r] ^= ALL
        V[y] = v
    C.sets_simulated += F
    return V
