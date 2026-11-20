#!/usr/bin/env python3
"""burst_sweep.py - License: UNDECIDED.

Communication-engineering experiment: RANDOM single flips against BURST events on the boot state code of rtl/v2.v variants.
One MODELLED burst event (cost 1) changes a fixed set of nets together in one clock cycle:
  flops_all   every state flop Q inverted in that cycle (the glitchsat single-cycle Q flip, applied to all state flops at once)
  flops_group the state flops owned by ONE comparator copy inverted (one event per copy group and cycle)
  rail_1to0   every gate output forced to 0 in that cycle and every flop captures 0 at its end (b3pack gates0 + d0, whole design)
  rail_0to1   every gate output forced to 1 and every flop captures 1 (b3pol gates1 + d1, whole design)
Controls (single flips, to tie this engine to P11's numbers): flip_flop (one state flop), flip_net (one gate output or flop Q).
This is NOT a real overclock or voltage glitch: it is an arithmetic event on a toy netlist. SIMULATED/modelled, bounded by T.

Engine: b3pack-style event unrolling in z3 (Netlist loader imported read-only from scripts/glitchsat.py), checked against a
z3-free bit-parallel brute force (all 256 sig values at once): subset enumeration up to size 3 and an exhaustive state search
over every event subset. `--reduce none` builds the z3 terms without per-net simplification; `--reduce both` runs both and
compares. Random-flip numbers come from results/comms/distance_sweep.csv (P11) or, for codebooks not in it, from the same
generator and product CLI (scripts/comms/distance_sweep.py, imported, not edited).
Pre-registration: research/c6/p14/PREREG.md (written before the first run).

usage: burst_sweep.py --out results/comms/burst.csv [--work DIR] [--cli 'python3 -m faultbound_wt.cli'] [--reduce both]
"none" in a burst cell = no attack with ANY subset of that kind's events within T cycles (bounded; not 'safe').
Toy design; no physical claim; nothing established as new.
"""
import argparse, csv, itertools, os, sys, tempfile, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import distance_sweep as ds          # read-only import (generator, functional check, synthesis, product-CLI measure)
import glitchsat as gs               # read-only import (Netlist loader only)
from z3 import Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, PbLe, sat, unsat, is_true, simplify

KEY = 0xC3
T_DEFAULT = 6
G = ds.DEFAULT_GROUPING
BURST_KINDS = ('flops_all', 'flops_group', 'rail_1to0', 'rail_0to1')


# ----------------------------------------------------------------------------- codebooks (fixed in PREREG.md)
def codebooks():
    """(name, I, C, W, B, grouping, in_p11)."""
    p11 = {c[0]: c for c in ds.codebooks()}
    names = ['69_96_complement', 'C3_3C_complement', 'A5_5A_complement', 'F0_96_stored', '2B_95', '00_1F_F8_E7', 'A5_A6',
             'fam_d2', 'fam_d4', 'Bvar_one_copy']
    out = [p11[n][:6] + (True,) for n in names]
    out += [
        ('F0_96_B3C', 0xF0, 0xCC, 0x96, 0x3C, G, False),       # distance-4 words, fail word not the complement of accept
        ('2B_95_BEB', 0x2B, 0x69, 0x95, 0xEB, G, False),       # distance-6 words, fail word not the complement
        ('A5_A6_BBE', 0xA5, 0x66, 0xA6, 0xBE, G, False),       # distance-2 words, fail word not the complement
        ('F0_96_BDF', 0xF0, 0xCC, 0x96, 0xDF, G, False),       # fail xor accept = 0x49 = exactly copy m0's group
        ('00_FF_C01_B02', 0x00, 0x01, 0xFF, 0x02, G, False),   # the plan's {00,01,FF,02}
        ('FF_00_CFE_BFD', 0xFF, 0xFE, 0x00, 0xFD, G, False),   # its mirror image
    ]
    return out


def group_masks(grouping=G):
    own = ds.owners(grouping)
    return [sum(1 << b for b in range(8) if own[b] == c) for c in range(3)]


# ----------------------------------------------------------------------------- pre-registered rules (arithmetic only)
def visited(I, C, B):
    return [x for x in (I, C, B) if x is not None]


def pred_flops_all(I, C, W, B):
    return '1' if (W ^ 0xFF) in visited(I, C, B) else 'none'


def pred_flops_group(I, C, W, B, grouping=G):
    gm = [m for m in group_masks(grouping) if m]
    best = None
    for r in range(1, len(gm) + 1):
        for sub in itertools.combinations(gm, r):
            u = 0
            for m in sub:
                u |= m
            if any((x ^ W) == u for x in visited(I, C, B)):
                best = r if best is None else min(best, r)
    return 'none' if best is None else str(best)


def pred_rail(W, polarity):
    return '1' if W == (0xFF if polarity == 1 else 0x00) else 'none'


# ----------------------------------------------------------------------------- events
class Ev:
    def __init__(self, name, flips=(), g0=(), d0=(), g1=(), d1=()):
        self.name = name
        self.flips, self.g0, self.d0, self.g1, self.d1 = map(frozenset, (flips, g0, d0, g1, d1))


def state_bits(nl, goal_out='boot_word'):
    bits = nl.ports[goal_out]['bits']
    if any(b not in nl.dq for b in bits):
        raise gs.NetlistError(f"{goal_out} bits are not all flop Q nets; the burst model needs the state flops behind the goal port")
    return bits


def events(nl, kind, masks=None, goal_out='boot_word'):
    sb = state_bits(nl, goal_out)
    gates, qs = set(nl.drivers), set(nl.qs)
    if kind == 'flops_all':
        return [Ev('flops_all', flips=qs)]
    if kind == 'flops_group':
        masks = group_masks() if masks is None else masks
        return [Ev(f'group_m{c}_{m:02X}', flips={sb[i] for i in range(len(sb)) if (m >> i) & 1}) for c, m in enumerate(masks) if m]
    if kind == 'rail_1to0':
        return [Ev('rail_1to0', g0=gates, d0=qs)]
    if kind == 'rail_0to1':
        return [Ev('rail_0to1', g1=gates, d1=qs)]
    if kind == 'flip_flop':
        return [Ev('flip_' + nl.names.get(q, str(q)), flips={q}) for q in sb]
    if kind == 'flip_net':
        return [Ev('flip_' + nl.names.get(b, str(b)), flips={b}) for b in list(nl.qs) + list(nl.drivers)]
    raise ValueError(kind)


def topo(nl):
    """Gate output nets in evaluation order (inputs before outputs)."""
    order, seen = [], set()
    for root in nl.drivers:
        stack = [root]
        while stack:
            b = stack[-1]
            if b in seen or b not in nl.drivers:
                stack.pop(); continue
            pend = [f for f in nl.fanins(b) if f in nl.drivers and f not in seen]
            if pend:
                stack.extend(pend)
            else:
                seen.add(b); order.append(b); stack.pop()
    return order


def _per_net(evs):
    fl, g0, g1, d0, d1 = {}, {}, {}, {}, {}
    for ei, e in enumerate(evs):
        for tgt, src in ((fl, e.flips), (g0, e.g0), (g1, e.g1), (d0, e.d0), (d1, e.d1)):
            for b in src:
                tgt.setdefault(b, []).append(ei)
    return fl, g0, g1, d0, d1


# ----------------------------------------------------------------------------- z3 event engine
def build(nl, N, evs, goal_value, goal_out='boot_word', attack_in='sig', key=KEY, simp=True):
    ports = nl.ports
    goal_bits = ports[goal_out]['bits']
    ain = BitVec('in_' + attack_in, len(ports[attack_in]['bits']))
    inbit = {b: Extract(i, i, ain) == 1 for i, b in enumerate(ports[attack_in]['bits'])}
    for p, v in ports.items():
        if v['direction'] == 'input' and p not in ('clk', attack_in):
            raise gs.NetlistError(f"unexpected extra input port {p!r}")
    order = topo(nl)
    fl, g0, g1, d0, d1 = _per_net(evs)
    A, hits = {}, []
    state = {q: BoolVal(nl.init[q]) for q in nl.qs}
    for t in range(N):
        a = [Bool(f'a_{t}_{ei}') for ei in range(len(evs))]
        for ei in range(len(evs)):
            A[(t, ei)] = a[ei]
        val = {}

        def get(b):
            if b == '0': return BoolVal(False)
            if b == '1': return BoolVal(True)
            if b in val: return val[b]
            if b in inbit: return inbit[b]
            raise gs.NetlistError(f"net {b!r} has no driver")

        def fault(b, v):
            for ei in fl.get(b, ()): v = Xor(v, a[ei])
            if b in g0: v = And(v, Not(Or(*[a[ei] for ei in g0[b]])))
            if b in g1: v = Or(v, Or(*[a[ei] for ei in g1[b]]))
            return simplify(v) if simp else v
        for q in nl.qs:
            val[q] = fault(q, state[q])
        for b in order:
            _, ty, con = nl.drivers[b]
            g = lambda p: get(con[p][0])
            if ty == '$_AND_': v = And(g('A'), g('B'))
            elif ty == '$_OR_': v = Or(g('A'), g('B'))
            elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
            elif ty == '$_NOT_': v = Not(g('A'))
            elif ty == '$_MUX_': v = If(g('S'), g('B'), g('A'))
            else: raise gs.UnsupportedCell('unsupported cell ' + str(ty))
            val[b] = fault(b, v)
        w = [get(b) for b in goal_bits]
        hits.append(And(*[w[i] == BoolVal(bool((goal_value >> i) & 1)) for i in range(len(w))]))
        nxt = {}
        for q, d in nl.dq.items():
            dv = get(d)
            if q in d0: dv = And(dv, Not(Or(*[a[ei] for ei in d0[q]])))
            if q in d1: dv = Or(dv, Or(*[a[ei] for ei in d1[q]]))
            nxt[q] = simplify(dv) if simp else dv
        state = nxt
    s = Solver()
    s.add(Or(*hits)); s.add(ain != key)
    return s, A, ain


def z3_min(nl, N, evs, goal_value, cap=None, simp=True, timeout_ms=120000, **kw):
    """Minimum number of active events. Returns (cell, witness): '<n>' | 'none' (cap None: no attack with any subset) |
    '>cap' | 'unknown'."""
    s, A, ain = build(nl, N, evs, goal_value, simp=simp, **kw)
    s.set('timeout', timeout_ms)
    allv = list(A.values())
    if cap is not None:
        s.add(PbLe([(x, 1) for x in allv], cap))
    r = s.check()
    if r == unsat:
        return ('none' if cap is None else f'>{cap}'), ''
    if r != sat:
        return 'unknown', ''
    act = lambda m: sorted(k for k, x in A.items() if is_true(m.eval(x, model_completion=True)))
    m = s.model(); best = act(m)
    while best:
        s.push(); s.add(PbLe([(x, 1) for x in allv], len(best) - 1))
        r = s.check()
        if r == sat:
            m = s.model(); best = act(m); s.pop()
        elif r == unsat:
            s.pop(); break
        else:
            return 'unknown', ''
    wit = ','.join(f'{evs[ei].name}@{t}' for t, ei in best) + f';sig={m.eval(ain, model_completion=True).as_long():02X}'
    return str(len(best)), wit


# ----------------------------------------------------------------------------- z3-free brute force (bit-parallel over sig)
class BF:
    """Concrete simulator; every net value is a 256-bit integer, bit v = value when sig == v. No z3."""

    def __init__(self, nl, N, evs, goal_value, goal_out='boot_word', attack_in='sig', key=KEY):
        self.nl, self.N, self.evs = nl, N, evs
        nin = len(nl.ports[attack_in]['bits'])
        self.n = 1 << nin
        self.M = (1 << self.n) - 1
        self.inbit = {b: sum(1 << v for v in range(self.n) if (v >> i) & 1) for i, b in enumerate(nl.ports[attack_in]['bits'])}
        self.wrong = self.M & ~(1 << key)
        self.goal_bits = nl.ports[goal_out]['bits']
        self.goal_value = goal_value
        self.order = topo(nl)
        self.per = _per_net(evs)
        self.qs = list(nl.qs)
        self.init = tuple(self.M if nl.init[q] else 0 for q in self.qs)

    def step(self, state, active):
        """One cycle. state: tuple of ints (per flop). active: set of event indices. Returns (hit, next_state)."""
        nl, M = self.nl, self.M
        fl, g0, g1, d0, d1 = self.per
        on = lambda lst: any(ei in active for ei in lst)
        val = dict(self.inbit)

        def fault(b, v):
            if b in fl:
                for ei in fl[b]:
                    if ei in active: v ^= M
            if b in g0 and on(g0[b]): v = 0
            if b in g1 and on(g1[b]): v = M
            return v

        def get(b):
            if b == '0': return 0
            if b == '1': return M
            return val[b]
        for q, v in zip(self.qs, state):
            val[q] = fault(q, v)
        for b in self.order:
            _, ty, con = nl.drivers[b]
            A = get(con['A'][0])
            if ty == '$_NOT_': v = A ^ M
            else:
                Bv = get(con['B'][0])
                if ty == '$_AND_': v = A & Bv
                elif ty == '$_OR_': v = A | Bv
                elif ty == '$_XOR_': v = A ^ Bv
                elif ty == '$_MUX_':
                    S = get(con['S'][0]); v = (S & Bv) | ((S ^ M) & A)
                else: raise ValueError(ty)
            val[b] = fault(b, v)
        hit = self.wrong
        for i, b in enumerate(self.goal_bits):
            v = get(b)
            hit &= v if (self.goal_value >> i) & 1 else (v ^ M)
        nxt = []
        for q in self.qs:
            dv = get(nl.dq[q])
            if q in d0 and on(d0[q]): dv = 0
            if q in d1 and on(d1[q]): dv = M
            nxt.append(dv)
        return hit, tuple(nxt)

    def run(self, active_te):
        """active_te: iterable of (t, ei). True if some wrong sig value sees the goal word at some cycle."""
        by_t = {}
        for t, ei in active_te:
            by_t.setdefault(t, set()).add(ei)
        st = self.init
        for t in range(self.N):
            hit, st = self.step(st, by_t.get(t, ()))
            if hit:
                return True
        return False

    def enum_min(self, kmax):
        """Plain enumeration of every event subset of size 0..kmax. Returns '<n>' or '>kmax'."""
        sites = [(t, ei) for t in range(self.N) for ei in range(len(self.evs))]
        for k in range(0, kmax + 1):
            for sub in itertools.combinations(sites, k):
                if self.run(sub):
                    return str(k)
        return f'>{kmax}'

    def search_min(self):
        """Exhaustive over ALL event subsets: forward search on (cycle, state bundle) keeping the cheapest cost.
        Per cycle every subset of that cycle's events is tried (so only for small per-cycle event counts)."""
        ne = len(self.evs)
        if ne > 10:
            raise ValueError('search_min is for small event sets')
        subsets = [frozenset(c) for r in range(ne + 1) for c in itertools.combinations(range(ne), r)]
        front, best = {self.init: 0}, None
        for t in range(self.N):
            nf = {}
            for st, c in front.items():
                for sub in subsets:
                    cc = c + len(sub)
                    if best is not None and cc >= best:
                        continue
                    hit, nx = self.step(st, sub)
                    if hit:
                        best = cc
                    elif nx not in nf or cc < nf[nx]:
                        nf[nx] = cc
            front = nf
        return 'none' if best is None else str(best)


# ----------------------------------------------------------------------------- one netlist
def measure_netlist(path, W, T=T_DEFAULT, reduce='both', grouping=G, k_ctrl=6, bf_ctrl=2, top='v2'):
    """All burst kinds and both controls on one netlist. Returns dict of cells and check flags."""
    nl = gs.Netlist(path, top)
    out = {'engine_notes': []}
    masks = group_masks(grouping)
    bf_ok = red_ok = True
    for kind in BURST_KINDS:
        evs = events(nl, kind, masks)
        simp_modes = {'both': (True, False), 'none': (False,), 'simp': (True,)}[reduce]
        cells = [z3_min(nl, T, evs, W, simp=sm) for sm in simp_modes]
        cell, wit = cells[0]
        if any(c[0] != cell for c in cells):
            red_ok = False; out['engine_notes'].append(f'{kind}: reduce modes disagree {[c[0] for c in cells]}')
        bf = BF(nl, T, evs, W)
        e, sm = bf.enum_min(3), bf.search_min()
        if not (sm == cell and (e == cell or (e == '>3' and (cell == 'none' or int(cell) > 3)))):
            bf_ok = False; out['engine_notes'].append(f'{kind}: z3 {cell} enum {e} search {sm}')
        if cell not in ('none', 'unknown') and not bf.run([(int(x.split('@')[1]), [v.name for v in evs].index(x.split('@')[0]))
                                                           for x in wit.split(';')[0].split(',')]):
            bf_ok = False; out['engine_notes'].append(f'{kind}: z3 witness does not replay in the brute-force simulator')
        out[kind], out['wit_' + kind] = cell, wit
    for kind, cap in (('flip_flop', k_ctrl), ('flip_net', min(k_ctrl, 3))):
        evs = events(nl, kind)
        cell, _ = z3_min(nl, T, evs, W, cap=cap, simp=(reduce != 'none'))
        if kind == 'flip_flop' or cell in ('1', '2'):
            e = BF(nl, T, evs, W).enum_min(bf_ctrl if kind == 'flip_flop' else int(cell))
            if not (e == cell or (e.startswith('>') and (cell.startswith('>') or int(cell) > int(e[1:])))):
                bf_ok = False; out['engine_notes'].append(f'{kind}: z3 {cell} enum {e}')
        out[kind] = cell
    out['bf_agree'], out['reduce_agree'] = bf_ok, (red_ok if reduce == 'both' else '')
    out['gates'], out['flops'] = len(nl.drivers), len(nl.dffs)
    return out


# ----------------------------------------------------------------------------- sweep
COLUMNS = ['codebook', 'idle', 'step', 'accept', 'fail', 'flow', 'yosys', 'T', 'd_to_accept', 'd_min', 'netlist_sha256',
           'random_min_flops', 'random_min_all', 'random_source',
           'burst_flops_all', 'burst_flops_group', 'burst_rail_1to0', 'burst_rail_0to1',
           'pred_flops_all', 'pred_flops_group', 'pred_rail_1to0', 'pred_rail_0to1', 'pred_match',
           'random_robust', 'burst_robust', 'quadrant',
           'control_flop_flip', 'control_any_net', 'control_agree', 'bf_agree', 'reduce_none_agree',
           'witness_flops_all', 'witness_flops_group', 'label', 'status']


def as_int(cell):
    """'>6' -> 7 (lower bound), 'none' -> large, '4' -> 4."""
    if cell == 'none': return 99
    return int(cell[1:]) + 1 if cell.startswith('>') else int(cell)


def quadrant(random_flops, burst_all):
    rr = as_int(random_flops) >= 4          # threshold fixed in PREREG.md
    br = burst_all != '1'
    return rr, br, ('random-robust' if rr else 'random-fragile') + ' / ' + ('burst-robust' if br else 'burst-fragile')


def run_codebook(cb, args, p11rows, yv):
    name, I, C, W, B, grouping, in_p11 = cb
    wd = os.path.join(args.work, name)
    os.makedirs(wd, exist_ok=True)
    rows = []
    cli = args.cli.split()
    if in_p11:
        vfile = os.path.join(wd, name + '.v')
        with open(vfile, 'w') as f:
            f.write(ds.gen_verilog(I, W, B, C, grouping))
        ok, msg = ds.functional_check(vfile, W, workdir=wd)
        if not ok:
            raise RuntimeError(f'{name}: functional check failed: {msg}')
        jp, js = os.path.join(wd, name + '_plain.json'), os.path.join(wd, name + '_struct.json')
        ds.synth_plain(vfile, 'v2', jp); ds.synth_struct(vfile, 'v2', js)
        r = p11rows[name]
        rnd = {'plain': (r['min_flops'], r['min_all']), 'struct': (r['min_flops_struct'], r['min_all_struct'])}
        src = 'results/comms/distance_sweep.csv (P11, MEASURED)'
        p11sha = {'plain': r['netlist_sha256'], 'struct': r['struct_sha256']}
    else:
        a = types.SimpleNamespace(work=args.work, T=args.T, timeout_s=args.timeout_s)
        r = ds.run_codebook((name, I, C, W, B, grouping, 'p14'), a, cli, yv)
        if not r['status'].startswith('measured'):
            raise RuntimeError(f"{name}: {r['status']}")
        jp, js = os.path.join(wd, name + '_plain.json'), os.path.join(wd, name + '_struct.json')
        rnd = {'plain': (r['min_flops'], r['min_all']), 'struct': (r['min_flops_struct'], r['min_all_struct'])}
        src = 'this run: distance_sweep.run_codebook + product CLI (MEASURED)'
        p11sha = None
    pred = dict(flops_all=pred_flops_all(I, C, W, B), flops_group=pred_flops_group(I, C, W, B, grouping),
                rail_1to0=pred_rail(W, 0), rail_0to1=pred_rail(W, 1))
    for flow, path in (('plain', jp), ('struct', js)):
        m = measure_netlist(path, W, T=args.T, reduce=args.reduce, grouping=grouping, k_ctrl=min(ds.pop(I ^ W), 6) or 1)
        sha = ds.sha256(path)
        notes = list(m['engine_notes'])
        if p11sha and p11sha[flow] != sha:
            notes.append('netlist sha differs from the P11 CSV row')
        ctrl_ok = (m['flip_flop'] == rnd[flow][0]) and (m['flip_net'] == rnd[flow][1] or
                                                         (m['flip_net'].startswith('>') and as_int(rnd[flow][1]) > 3))
        rr, br, quad = quadrant(rnd[flow][0], m['flops_all'])
        match = all(m[k] == pred[k] for k in BURST_KINDS)
        engine_ok = m['bf_agree'] and ctrl_ok and m['reduce_agree'] in (True, '') and not notes
        rows.append(dict(
            codebook=name, idle=f'{I:02X}', step='' if C is None else f'{C:02X}', accept=f'{W:02X}', fail=f'{B:02X}', flow=flow,
            yosys=yv, T=args.T, d_to_accept=ds.pop(I ^ W), d_min=ds.d_min(I, C, W, B), netlist_sha256=sha,
            random_min_flops=rnd[flow][0], random_min_all=rnd[flow][1], random_source=src,
            burst_flops_all=m['flops_all'], burst_flops_group=m['flops_group'], burst_rail_1to0=m['rail_1to0'],
            burst_rail_0to1=m['rail_0to1'], pred_flops_all=pred['flops_all'], pred_flops_group=pred['flops_group'],
            pred_rail_1to0=pred['rail_1to0'], pred_rail_0to1=pred['rail_0to1'], pred_match='yes' if match else 'NO',
            random_robust='yes' if rr else 'no', burst_robust='yes' if br else 'no', quadrant=quad,
            control_flop_flip=m['flip_flop'], control_any_net=m['flip_net'], control_agree='yes' if ctrl_ok else 'NO',
            bf_agree='yes' if m['bf_agree'] else 'NO', reduce_none_agree={True: 'yes', False: 'NO', '': 'not run'}[m['reduce_agree']],
            witness_flops_all=m['wit_flops_all'], witness_flops_group=m['wit_flops_group'],
            label='SIMULATED (modelled burst events, toy netlist, bounded T; not a physical glitch)',
            status='measured' if engine_ok else 'ENGINE_CHECK_FAILED: ' + '; '.join(notes or ['control mismatch'])))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True)
    ap.add_argument('--work', default=None)
    ap.add_argument('--cli', default='faultbound-wt', help="product CLI for random-flip rows of codebooks not in P11's CSV")
    ap.add_argument('--p11', default=os.path.join(ROOT, 'results', 'comms', 'distance_sweep.csv'))
    ap.add_argument('--T', type=int, default=T_DEFAULT)
    ap.add_argument('--timeout-s', type=int, default=300)
    ap.add_argument('--reduce', choices=['both', 'none', 'simp'], default='both',
                    help='z3 term building: simp = per-net simplify, none = raw terms, both = run both and compare')
    ap.add_argument('--only', nargs='*')
    args = ap.parse_args()
    args.work = args.work or tempfile.mkdtemp(prefix='p14_burst_')
    os.makedirs(args.work, exist_ok=True)
    p11rows = {r['codebook']: r for r in csv.DictReader(open(args.p11))}
    yv = ds.yosys_version()
    t0 = time.time()
    rows = []
    for cb in codebooks():
        if args.only and cb[0] not in args.only:
            continue
        t1 = time.time()
        rs = run_codebook(cb, args, p11rows, yv)
        rows += rs
        for r in rs:
            print(f"{r['codebook']:18s} {r['flow']:6s} random flops={r['random_min_flops']:3s} all={r['random_min_all']:3s} | burst all={r['burst_flops_all']:4s}"
                  f" group={r['burst_flops_group']:4s} 1to0={r['burst_rail_1to0']:4s} 0to1={r['burst_rail_0to1']:4s} | pred {r['pred_flops_all']}/{r['pred_flops_group']}/"
                  f"{r['pred_rail_1to0']}/{r['pred_rail_0to1']} match={r['pred_match']} | ctrl={r['control_agree']} bf={r['bf_agree']} red={r['reduce_none_agree']}"
                  f" | {r['quadrant']} | {r['status'][:60]} ({time.time() - t1:.1f}s)", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator='\n')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f'total wall {time.time() - t0:.1f}s; wrote {args.out}; rows {len(rows)}; '
          f"prediction mismatches {sum(r['pred_match'] != 'yes' for r in rows)}; engine check failures {sum(r['status'] != 'measured' for r in rows)}")


if __name__ == '__main__':
    main()
