#!/usr/bin/env python3
"""predictor.py -- structural min-flip predictor.  NO SAT/SMT solver is called.

Fault model (same as scripts/glitchsat.py): a fault = single-cycle XOR on one net (gate output or flop Q); a stem
is ONE fault however many fanouts it has.  Goal: at some cycle t* in 0..T-1 the consumer-checked bits of the output
port equal the accept value on the masked bits.  Attacker input = constant value != key; other inputs held at 0;
input nets are not fault sites; power-up state = netlist init values (default 0).

What it computes (all polynomial; pure Python; see PREREG.md for the exact definition):
  1. Fault-free bit-parallel simulation over all wrong attacker values (<=1024 values; sampled if more).
     For each (t*, sig): D = masked output bits that differ from the accept value.   D empty -> cost 0 ('collision').
  2. LB  (structural, no sensitisation): site (t,n) "covers" bit b of D at t* iff a directed path exists in the
     time-unrolled graph from net n at cycle t to output bit b at cycle t* (gates same cycle, flop D->Q one cycle).
     Every bit of D must be covered by some fault, so  LB = min over (t*,sig) of the minimum SET COVER of D by
     structural cones.  This is a necessary-condition bound (reachability is necessary, not sufficient).
  3. EST (sensitised cover, 'effective cones'): for each site (t,n) the single flip is event-propagated through the
     fault-free trace; E(t,n,t*,sig) = set of masked bits that toggle at t*.  A site is USABLE for (t*,sig) if it
     toggles >=1 bit of D and NO masked bit outside D.  EST = min over (t*,sig) of the minimum SET COVER of D by
     usable sites.  (Sites with disjoint effects are assumed to combine independently; interactions such as two
     flips cancelling on a shared bit, or a flip that only becomes effective after another one, are NOT modelled.
     So EST is an estimate, an upper bound only when the chosen flips do not interact.)
     If no cover exists EST = None and the predicted value is LB+1 (flag 'uncovered').
  4. UB_DIRECT = min over (t*,sig) of |D| distinct output nets (flip each differing output-bit net at t*).
Output: dict(lb, est, ub_direct, pred, flag, witness).   pred = est if est is not None else lb+1.
Cost note: sig values are the attacker's constant input; cost reported is min over them (attacker chooses).
"""
import json, sys, heapq, random, itertools, argparse

NOTE = ("STRUCTURAL ESTIMATE (no solver): T-cycle bounded, single-cycle XOR faults on gate outputs/flop Q, stem=1 fault. "
        "Not a security statement; toy designs; see PREREG.md for limits.")

# ------------------------------------------------------------------ netlist
_GATES = {
    '$_AND_': ('A', 'B'), '$_OR_': ('A', 'B'), '$_XOR_': ('A', 'B'), '$_NOT_': ('A',), '$_MUX_': ('A', 'B', 'S'),
    '$_NAND_': ('A', 'B'), '$_NOR_': ('A', 'B'), '$_XNOR_': ('A', 'B'), '$_ANDNOT_': ('A', 'B'), '$_ORNOT_': ('A', 'B'),
    '$_BUF_': ('A',),
}


def _eval(ty, a, FULL):
    if ty == '$_AND_': return a[0] & a[1]
    if ty == '$_OR_': return a[0] | a[1]
    if ty == '$_XOR_': return a[0] ^ a[1]
    if ty == '$_NOT_': return a[0] ^ FULL
    if ty == '$_MUX_': return (a[0] & (a[2] ^ FULL)) | (a[1] & a[2])
    if ty == '$_NAND_': return (a[0] & a[1]) ^ FULL
    if ty == '$_NOR_': return (a[0] | a[1]) ^ FULL
    if ty == '$_XNOR_': return (a[0] ^ a[1]) ^ FULL
    if ty == '$_ANDNOT_': return a[0] & (a[1] ^ FULL)
    if ty == '$_ORNOT_': return a[0] | (a[1] ^ FULL)
    if ty == '$_BUF_': return a[0]
    raise ValueError(ty)


class Net:
    def __init__(self, path, top):
        doc = json.load(open(path))
        m = doc['modules'][top]
        self.ports = m['ports']
        self.gates = {}      # out net -> (type, [in nets])
        self.flops = {}      # Q net -> D net
        for cn, c in m['cells'].items():
            t, con = c['type'], c['connections']
            if t == '$_DFF_P_':
                self.flops[con['Q'][0]] = con['D'][0]
            elif t in _GATES:
                self.gates[con['Y'][0]] = (t, [con[p][0] for p in _GATES[t]])
            else:
                raise ValueError(f'unsupported cell {t} ({cn})')
        self.init = {}
        for n, x in m['netnames'].items():
            iv = x['attributes'].get('init')
            if iv:
                for i, b in enumerate(reversed(iv)):
                    if b in '01' and isinstance(x['bits'][i], int):
                        self.init[x['bits'][i]] = (b == '1')
        self.names = {}
        for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.names.setdefault(b, f"{n}[{i}]" if len(x['bits']) > 1 else n)
        # topological order of gates (flop Q / inputs / constants are roots)
        self.topo = []
        seen = set()
        for root in self.gates:
            if root in seen: continue
            st = [(root, iter(self.gates[root][1]))]
            seen.add(root)
            while st:
                b, it = st[-1]
                for f in it:
                    if f in self.gates and f not in seen:
                        seen.add(f); st.append((f, iter(self.gates[f][1]))); break
                else:
                    self.topo.append(b); st.pop()
        self.tidx = {b: i for i, b in enumerate(self.topo)}
        self.fanout = {}
        for g, (t, ins) in self.gates.items():
            for f in ins:
                if isinstance(f, int): self.fanout.setdefault(f, []).append(g)
        self.dfan = {}   # net -> flops (Q) it feeds as D
        for q, d in self.flops.items():
            if isinstance(d, int): self.dfan.setdefault(d, []).append(q)


# ------------------------------------------------------------------ min set cover (exact, tiny universes)
def min_cover(universe, sets, cap=8):
    """universe: bitmask; sets: iterable of bitmasks (already restricted to universe). Returns (size, chosen) or (None,None)."""
    sets = list({s for s in sets if s})
    # drop dominated sets
    sets.sort(key=lambda s: -bin(s).count('1'))
    keep = []
    for s in sets:
        if not any((s | k) == k for k in keep): keep.append(s)
    best = {0: []}
    frontier = [0]
    for size in range(1, cap + 1):
        nxt = {}
        for st in frontier:
            for s in keep:
                ns = st | s
                if ns not in best and ns not in nxt:
                    nxt[ns] = best[st] + [s]
        for k, v in nxt.items(): best[k] = v
        if universe in nxt: return size, nxt[universe]
        frontier = list(nxt)
        if not frontier: break
    return None, None



def inval_scalar(inval, s):
    return {b: (x >> s) & 1 for b, x in inval.items()}


def simulate_faults(nl, inv, faults, T):
    """Scalar joint simulation with a set of (t, net) XOR faults; returns list of net-value dicts per cycle."""
    state = {q: int(nl.init.get(q, False)) for q in nl.flops}
    res = []
    fs = set(faults)
    for t in range(T):
        val = dict(inv); val.update(state)
        for q in nl.flops:
            if (t, q) in fs: val[q] ^= 1
        for g in nl.topo:
            ty, ins = nl.gates[g]
            v = _eval(ty, [(0 if f == '0' else 1 if f == '1' else val[f]) for f in ins], 1)
            if (t, g) in fs: v ^= 1
            val[g] = v
        res.append(val)
        state = {q: (0 if d == '0' else 1 if d == '1' else val[d]) for q, d in nl.flops.items()}
    return res


def verified_cover(nl, ss, D, cap, gbits, mbits, accept, sigval, inv, T, ts, max_try=3000):
    """Smallest fault set (size<=cap) built from effect classes ss (E-mask -> site) that jointly reaches accept at cycle ts,
    verified by joint scalar simulation (a verified set is a true upper bound). Returns list of sites or None."""
    keys = list(ss)
    for k in range(1, cap + 1):
        tries = 0
        for combo in itertools.combinations(keys, k):
            u = 0
            for c in combo: u |= c
            if u & D != D: continue
            tries += 1
            if tries > max_try: break
            faults = [ss[c] for c in combo]
            if len(set(faults)) < k: continue
            res = simulate_faults(nl, inv, faults, T)
            ok = True
            for i in mbits:
                b = gbits[i]
                v = 0 if b == '0' else 1 if b == '1' else res[ts][b]
                if v != ((accept >> i) & 1): ok = False; break
            if ok: return faults
    return None

# ------------------------------------------------------------------ main predictor
def predict(path, top, goal_out='boot_word', mask=0xFF, accept=0x96, key=0xC3, attack_in='sig', T=6, max_sigs=1024, seed=1):
    nl = Net(path, top)
    ports = nl.ports
    gbits = ports[goal_out]['bits']
    mbits = [i for i in range(len(gbits)) if (mask >> i) & 1]
    maskbits_all = 0
    for i in mbits: maskbits_all |= 1 << i
    # ---- attacker values
    w = len(ports[attack_in]['bits'])
    allv = [v for v in range(1 << w) if v != key] if w <= 12 else None
    if allv is None:
        rnd = random.Random(seed)
        allv = sorted({rnd.getrandbits(w) for _ in range(max_sigs)} - {key})
    elif len(allv) > max_sigs:
        rnd = random.Random(seed); allv = sorted(rnd.sample(allv, max_sigs))
    NS = len(allv); FULL = (1 << NS) - 1
    inval = {}
    for p, v in ports.items():
        if v['direction'] != 'input': continue
        for i, b in enumerate(v['bits']):
            if not isinstance(b, int): continue
            if p == attack_in:
                x = 0
                for s, val in enumerate(allv):
                    if (val >> i) & 1: x |= 1 << s
                inval[b] = x
            else:
                inval[b] = 0
    # ---- fault-free trace
    def getv(val, b):
        if b == '0': return 0
        if b == '1': return FULL
        return val[b]
    state = {q: (FULL if nl.init.get(q, False) else 0) for q in nl.flops}
    vals = []
    for t in range(T):
        val = dict(inval); val.update(state)
        for g in nl.topo:
            ty, ins = nl.gates[g]
            val[g] = _eval(ty, [getv(val, f) for f in ins], FULL)
        vals.append(val)
        state = {q: getv(val, d) for q, d in nl.flops.items()}
    out_free = [[getv(vals[t], b) for b in gbits] for t in range(T)]   # [t][bit] -> NS-bit int
    # ---- structural reach A[j][n] = bitmask over goal-bit indices (masked only) reachable from net n with exactly j flop crossings
    goalown = {}
    for i in mbits:
        b = gbits[i]
        if isinstance(b, int): goalown[b] = goalown.get(b, 0) | (1 << i)
    allnets = set(nl.gates) | set(nl.flops)
    A = []
    for j in range(T):
        Aj = {}
        order = list(reversed(nl.topo))
        def comb(n):
            r = goalown.get(n, 0) if j == 0 else 0
            for g in nl.fanout.get(n, []): r |= Aj[g]
            if j >= 1:
                for q in nl.dfan.get(n, []): r |= A[j - 1].get(q, 0)
            return r
        for g in order: Aj[g] = comb(g)
        for q in nl.flops: Aj[q] = comb(q)
        A.append(Aj)
    sites = []
    for t in range(T):
        for n in allnets:
            if any(A[j].get(n, 0) for j in range(0, T - t)): sites.append((t, n))
    # ---- structural cover sets per t*
    struct_sets = {}
    for ts in range(T):
        S = set()
        for (t, n) in sites:
            if t <= ts:
                m = A[ts - t].get(n, 0)
                if m: S.add(m)
        struct_sets[ts] = S
    # ---- single-flip event propagation: eff[ts][(t,n)] = [NS-bit int per masked bit] (toggle indicator)
    eff = {ts: {} for ts in range(T)}
    for (t, n) in sites:
        changed = {n: vals[t][n] ^ FULL}
        cur_state_diff = {}
        for tt in range(t, T):
            if tt > t:
                changed = {q: dv for q, dv in cur_state_diff.items()}
                if not changed: break
            heap = []
            inheap = set()
            def push_fo(net):
                for g in nl.fanout.get(net, []):
                    if g not in inheap:
                        inheap.add(g); heapq.heappush(heap, nl.tidx[g])
            newv = dict(changed)
            for net in list(changed): push_fo(net)
            while heap:
                g = nl.topo[heapq.heappop(heap)]
                ty, ins = nl.gates[g]
                a = [(newv[f] if f in newv else getv(vals[tt], f)) for f in ins]
                nv = _eval(ty, a, FULL)
                if nv != vals[tt][g]:
                    newv[g] = nv; push_fo(g)
            # output toggles at tt
            rec = None
            for i in mbits:
                b = gbits[i]
                if isinstance(b, int) and b in newv:
                    d = newv[b] ^ vals[tt][b]
                    if d:
                        if rec is None: rec = {}
                        rec[i] = d
            if rec: eff[tt][(t, n)] = rec
            cur_state_diff = {}
            for q, d in nl.flops.items():
                if isinstance(d, int) and d in newv:
                    cur_state_diff[q] = newv[d] ^ vals[tt][d]   # == diff vs free next state; apply as XOR on Q
            # convert diffs to new Q values: Q' = free Q(next) ^ diff ; propagate as 'changed' values
            if tt + 1 < T:
                nxt = {}
                for q, dif in cur_state_diff.items():
                    if dif: nxt[q] = vals[tt + 1][q] ^ dif
                cur_state_diff = nxt
    # ---- evaluate per (t*, sig)
    best_lb = best_est = best_dir = None
    wit_lb = wit_est = None
    uncovered_any = False
    for ts in range(T):
        # group sigs by D
        sets_s = list(struct_sets[ts])
        eff_ts = eff[ts]
        for s in range(NS):
            D = 0
            for i in mbits:
                if ((out_free[ts][i] >> s) & 1) != ((accept >> i) & 1): D |= 1 << i
            if D == 0:
                return dict(lb=0, est=0, ub_direct=0, pred=0, flag='collision', witness=dict(t_star=ts, sig=allv[s]), note=NOTE)
            # distinct output nets for direct flips
            nets = set(gbits[i] for i in mbits if (D >> i) & 1)
            dirc = len(nets)
            if best_dir is None or dirc < best_dir: best_dir = dirc
            if best_lb is None or best_lb > 1:
                size, _ = min_cover(D, [m & D for m in sets_s], cap=(best_lb - 1 if best_lb else 8))
                if size is not None and (best_lb is None or size < best_lb):
                    best_lb = size; wit_lb = (ts, allv[s])
            # sensitised sets
            ss = {}
            for site, rec in eff_ts.items():
                E = 0
                for i, d in rec.items():
                    if (d >> s) & 1: E |= 1 << i
                if E & D and not (E & ~D & maskbits_all):
                    ss.setdefault(E, site)
            cap = (best_est - 1) if best_est else 6
            if cap >= 1:
                found = verified_cover(nl, ss, D, cap, gbits, mbits, accept, allv[s], inval_scalar(inval, s), T, ts)
                if found is not None and (best_est is None or len(found) < best_est):
                    best_est = len(found)
                    wit_est = dict(t_star=ts, sig=allv[s], D=D,
                                   sites=[(t_, nl.names.get(n_, n_)) for (t_, n_) in found])
    if best_lb is None: best_lb = 99   # some masked bit has no structural path to any site (constant output)
    pred = best_est if best_est is not None else best_lb + 1
    flag = 'ok' if best_est is not None else 'uncovered'
    if best_est is not None and best_est < best_lb: flag = 'est_below_lb'   # should not happen; sanity flag
    return dict(lb=best_lb, est=best_est, ub_direct=best_dir, pred=pred, flag=flag, witness=wit_est, lb_witness=wit_lb, note=NOTE)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('netlist'); ap.add_argument('--top', required=True)
    ap.add_argument('--goal-out', default='boot_word'); ap.add_argument('--mask', default='0xFF')
    ap.add_argument('--accept', default='0x96'); ap.add_argument('--key', default='0xC3')
    ap.add_argument('--attack-in', default='sig'); ap.add_argument('--cycles', type=int, default=6)
    a = ap.parse_args()
    r = predict(a.netlist, a.top, a.goal_out, int(a.mask, 0), int(a.accept, 0), int(a.key, 0), a.attack_in, a.cycles)
    print(json.dumps(r, indent=1, default=str))
