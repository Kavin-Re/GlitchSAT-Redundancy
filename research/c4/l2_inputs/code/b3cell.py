#!/usr/bin/env python3
# copy of research/c4/b3/b3pack.py with ONE patch: CELLOF (subset choice per placed cell). Everything else unchanged.
"""b3pack: rail-dip and wrong-time-capture fault events, as an EXTENSION (copy) of B1's
faultpack. Imports Netlist from faultpack.py (copy of research/c2/b1_faultmodels/faultpack.py, unchanged). New z3 unrolling
below, event-based: one Bool a[t,e] per (cycle, event); cost of an attack = number of active events.

EVENT KINDS (all single-cycle, MODELLED, derived from SIMULATED SPICE hints in research/c2/el1_spice, not physical):
 flips  : stem flip of the listed nets (gate outputs / flop Qs): net value xor 1 (B1 stem_flip as an event; control row)
 gates0 : RAIL DIP. Every gate output in the set is forced to 0 in that cycle (those at 0 stay 0; 1 -> 0 only, never 0 -> 1
          directly; downstream gates then see the dipped value, so a 0 can reach 1 through an inverting gate: that is
          logic, not the dip). Flop Q is NOT touched (EL1: Q held in 60/60 dip points). Gate outputs include output-port
          bits that are gate outputs (observed value is dipped).
 d0     : RAIL DIP, flop capture. For every flop q in the set the value captured at the end of that cycle is D AND 0 = 0
          (the dip makes a flop capture 0 where D should have been 1; EL1: clean-rail flop sampling a sagged high output
          captured 0). Q during the cycle is unaffected. A flop whose D is a gate output already gets 0 through gates0;
          d0 matters when D is a flop Q, a constant 1, or a primary input.
 early  : WRONG-TIME CAPTURE, EARLY (clock runt / extra edge, EL1 exp B: Q takes D). Two-pass cycle: pass 1 evaluates the
          cycle normally (with all non-early faults of that cycle) giving the D value D0[q] each flop would capture; the
          listed flops then show Q := D0[q] in this cycle (their next state is one cycle ahead, "skip-ahead"), pass 2
          re-evaluates the cycle with these Q values and the flops capture from pass 2 at the end of the cycle (normal edge).
 hold   : WRONG-TIME CAPTURE, LATE (setup violation, EL1 exp C: old value kept). Listed flops keep Q across the edge ending
          this cycle (== B1 flop_hold / clock_skip_all; the capture 'one cycle late' is observable only as a hold because
          the next edge captures the fresh D again).
 subset : if True the event may apply early/hold/gates0/d0 to ANY subset of its listed sites (one action, cost 1); else all of them.
Goal: observed output port == value at some cycle < N; attacker input sig free, constant, != 0xC3 (as faultpack).
Primary inputs/constants are never faulted. Init: netlist init values.
"""
import os, sys, time, itertools, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import faultpack as fp
from z3 import (Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, PbLe, Implies, sat, unsat, is_true, simplify)


CELLOF = {}   # LAYOUT patch: net -> placed-cell name; subset selection is then per CELL, not per primitive
SUBS = []   # subset-selection vars of the last build (for minimising the dip domain)


class Event:
    def __init__(self, name, flips=(), gates0=(), d0=(), early=(), hold=(), subset=False):
        self.name = name; self.flips = frozenset(flips); self.gates0 = frozenset(gates0); self.d0 = frozenset(d0)
        self.early = frozenset(early); self.hold = frozenset(hold); self.subset = subset

    def key(self):
        return (self.flips, self.gates0, self.d0, self.early, self.hold, self.subset)


def dedup(evs):
    seen, out = set(), []
    for e in evs:
        if e.key() not in seen: seen.add(e.key()); out.append(e)
    return out


# ------------------------------------------------------------------ groups (netlist-derived, NOT layout)
def unit_of(cellname):
    m = re.match(r'\$flatten\\(.+?)\.', cellname)
    return m.group(1) if m else ''


def units(nl, merge_voters=True):
    """hierarchy unit -> (gate outputs, flop Qs). Flatten prefixes c0/c1/c2/g[i]/...; '' = top-level logic and flops.
    Unit names g[0]..g[7] (V5 voters) are merged into 'g' when merge_voters so unions stay enumerable."""
    U = collections.defaultdict(lambda: (set(), set()))
    nm = lambda cn: (re.sub(r'\[\d+\]$', '', unit_of(cn)) if merge_voters else unit_of(cn))
    for y, (cn, t, con) in nl.drivers.items(): U[nm(cn)][0].add(y)
    for cn, d, q in nl.dffs: U[nm(cn)][1].add(q)
    return dict(U)


def rail_events(nl, family):
    gates = set(nl.drivers); qs = set(nl.qs)
    U = units(nl)
    evs = []
    if family == 'all':
        evs.append(Event('rail_all', gates0=gates, d0=qs))
    elif family in ('unions', 'half'):
        names = sorted(U)
        tot = len(gates)
        for r in range(1, len(names) + 1):
            for sub in itertools.combinations(names, r):
                g = set().union(*[U[n][0] for n in sub]); f = set().union(*[U[n][1] for n in sub])
                if family == 'half' and len(g) * 2 > tot: continue
                if g or f: evs.append(Event('rail_' + '+'.join(n or 'top' for n in sub), gates0=g, d0=f))
    elif family == 'cone':    # gates in the combinational fanout cone of one net (gates only, never flop Q)
        fo = collections.defaultdict(set)
        for y in nl.drivers:
            for f in nl.fanins(y):
                if isinstance(f, int): fo[f].add(y)
        for r in list(nl.drivers) + list(nl.qs):
            cone, st = set(), [r]
            while st:
                x = st.pop()
                for y in fo[x]:
                    if y not in cone: cone.add(y); st.append(y)
            if cone: evs.append(Event('rail_cone_' + nl.names.get(r, str(r)), gates0=cone))
    else:
        raise ValueError(family)
    return dedup(evs)


def models(nl):
    """model name -> list[Event]"""
    qs = list(nl.qs); gates = list(nl.drivers)
    M = {}
    M['stem_flip'] = [Event('flip_' + nl.names.get(b, str(b)), flips={b}) for b in qs + gates]
    M['rail_all'] = rail_events(nl, 'all')
    M['rail_half'] = rail_events(nl, 'half')
    M['rail_unions'] = rail_events(nl, 'unions')
    M['rail_cone'] = rail_events(nl, 'cone')
    M['rail_any'] = dedup(M['rail_all'] + M['rail_unions'] + M['rail_cone'])
    M['reset_one'] = [Event('reset_' + nl.names.get(y, str(y)), gates0={y}) for y in gates]       # ONE gate forced 0 (not a rail; B1 reset_only analogue)
    M['dip_subset'] = [Event('dip_subset', gates0=set(gates), d0=set(qs), subset=True)]          # UPPER BOUND: any subset of gates (and flop D pins) forced 0 by ONE event
    M['early_one'] = [Event('early_' + nl.names.get(q, str(q)), early={q}) for q in qs]
    M['early_all'] = [Event('early_all', early=set(qs))]
    M['early_subset'] = [Event('early_subset', early=set(qs), subset=True)]
    M['hold_one'] = [Event('hold_' + nl.names.get(q, str(q)), hold={q}) for q in qs]
    M['hold_subset'] = [Event('hold_subset', hold=set(qs), subset=True)]
    M['wrongtime_any'] = dedup(M['early_one'] + M['early_all'] + M['early_subset'] + M['hold_one'] + M['hold_subset'])
    M['rail_or_wrongtime'] = dedup(M['rail_any'] + M['wrongtime_any'])
    return M


# ------------------------------------------------------------------ z3 unrolling
def build(nl, N, events, goal_out='boot_word', goal_value=0x96, key=0xC3, simp=True):
    ports = nl.ports
    goal_bits = ports[goal_out]['bits']
    gv = goal_value
    inputs = {p: BitVec(f'in_{p}', len(v['bits'])) for p, v in ports.items() if v['direction'] == 'input' and p != 'clk'}
    inbit = {}
    for p, v in ports.items():
        if p in inputs:
            for i, b in enumerate(v['bits']): inbit[b] = Extract(i, i, inputs[p]) == 1
    A = {}
    SUBS.clear()
    cost = []
    s = Solver()
    state = {q: BoolVal(nl.init[q]) for q in nl.qs}
    hits = []
    for t in range(N):
        flipf = collections.defaultdict(list); g0 = collections.defaultdict(list); d0 = collections.defaultdict(list)
        earlyf = collections.defaultdict(list); holdf = collections.defaultdict(list)
        for ei, e in enumerate(events):
            if e.hold and t > N - 2: continue
            a = Bool(f'a_{t}_{ei}'); A[(t, ei)] = a; cost.append(a)
            for b in e.flips: flipf[b].append(a)
            for y in e.gates0:
                if e.subset:
                    sv = Bool(f's_c_{t}_{ei}_{CELLOF.get(y, y)}'); SUBS.append(sv); s.add(Implies(sv, a)); g0[y].append(sv)
                else: g0[y].append(a)
            for q in e.d0:
                if e.subset:
                    sv = Bool(f's_c_{t}_{ei}_{CELLOF.get(q, q)}'); SUBS.append(sv); s.add(Implies(sv, a)); d0[q].append(sv)
                else: d0[q].append(a)
            for kind, qset, tgt in (('early', e.early, earlyf), ('hold', e.hold, holdf)):
                for q in qset:
                    if e.subset:
                        sv = Bool(f's_{kind}_{t}_{ei}_{q}'); s.add(Implies(sv, a)); tgt[q].append(sv)
                    else: tgt[q].append(a)

        def evaluate(st):
            val = {}
            def raw(b):
                if b in ('0', 'x', 'z'): return BoolVal(False)
                if b == '1': return BoolVal(True)
                if b in val: return val[b]
                if b in inbit: return inbit[b]
                if b in st: v = st[b]
                else:
                    _, ty, con = nl.drivers[b]
                    g = lambda p: raw(con[p][0])
                    if ty == '$_AND_': v = And(g('A'), g('B'))
                    elif ty == '$_OR_': v = Or(g('A'), g('B'))
                    elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
                    elif ty == '$_NOT_': v = Not(g('A'))
                    elif ty == '$_MUX_': v = If(g('S'), g('B'), g('A'))
                    else: raise Exception('unsupported cell ' + ty)
                for a in flipf.get(b, ()): v = Xor(v, a)
                if b in g0: v = And(v, Not(Or(*g0[b])))
                if simp: v = simplify(v)
                val[b] = v
                return v
            dvs = {}
            for q, d in nl.dq.items():
                dv = raw(d) if isinstance(d, int) else raw(d)
                if q in d0: dv = And(dv, Not(Or(*d0[q])))
                dvs[q] = dv
            return raw, dvs

        raw, dvs = evaluate(state)
        if earlyf:
            st2 = dict(state)
            for q, fl in earlyf.items(): st2[q] = If(Or(*fl), dvs[q], state[q])
            raw, dvs = evaluate(st2)
        w = [raw(b) for b in goal_bits]
        hits.append(And(*[w[i] == BoolVal(bool((gv >> i) & 1)) for i in range(len(w))]))
        nxt = {}
        for q in nl.qs:
            dv = dvs[q]
            if q in holdf: dv = If(Or(*holdf[q]), state[q], dv)
            nxt[q] = simplify(dv) if simp else dv
        state = nxt
    s.add(Or(*hits)); s.add(inputs['sig'] != key)
    return s, A, cost, inputs


def min_cost(nl, N, events, cap=3, timeout_ms=60000, **kw):
    t0 = time.time()
    s, A, cost, inputs = build(nl, N, events, **kw)
    s.set('timeout', timeout_ms)
    bt = round(time.time() - t0, 1)
    for k in range(cap + 1):
        s.push(); s.add(PbLe([(c, 1) for c in cost], k)); t1 = time.time(); r = s.check(); dt = round(time.time() - t1, 1)
        if r == sat:
            m = s.model()
            act = sorted([(t, events[ei].name) for (t, ei), a in A.items() if is_true(m.eval(a, model_completion=True))])
            atk = m.eval(inputs['sig'], model_completion=True).as_long()
            s.pop(); return dict(min=k, status='ATTACK', events=act, sig=atk, build_s=bt, solve_s=dt, n_events=len(events))
        s.pop()
        if r != unsat: return dict(min=None, status='UNKNOWN', cap=cap, timeout_at_k=k, build_s=bt, n_events=len(events))
    return dict(min=None, status='NONE_UP_TO_CAP', cap=cap, build_s=bt, n_events=len(events))


def fmt(r):
    return str(r['min']) if r['status'] == 'ATTACK' else (f">{r['cap']}" if r['status'] == 'NONE_UP_TO_CAP' else 'unknown')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('netlist'); ap.add_argument('--top', required=True); ap.add_argument('--model', required=True)
    ap.add_argument('--cycles', type=int, default=6); ap.add_argument('--cap', type=int, default=3)
    ap.add_argument('--timeout-ms', type=int, default=60000); ap.add_argument('--goal', default='word', choices=['word', 'ok'])
    a = ap.parse_args()
    nl = fp.Netlist(a.netlist, a.top)
    ev = models(nl)[a.model]
    kw = dict(goal_out='boot_word', goal_value=0x96) if a.goal == 'word' else dict(goal_out='boot_ok', goal_value=1)
    r = min_cost(nl, a.cycles, ev, a.cap, a.timeout_ms, **kw)
    print(a.netlist, a.top, a.model, a.goal, 'T=%d' % a.cycles, 'min cost =', fmt(r), r)
