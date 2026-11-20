#!/usr/bin/env python3
"""faultpack: fault-model pack for bounded fault-injection search on gate-level
Yosys JSON netlists. A COPY/extension of scripts/glitchsat.py's engine (that file is untouched).

A fault model = (site granularity) x (effects) x (optional correlated groups):
  site   : 'stem'   one fault variable per driven net (gate output or flop Q): a fault changes the net for ALL its fanout
                    and for the observed output port (this is glitchsat's model)
           'branch' one fault variable per fanout PIN (gate input pin, flop D pin, observed output-port bit): each branch is
                    faulted separately, the stem net itself is never faulted; a stem with fanout n costs n to hit entirely
           'both'   union of the two
  effects: 'flip' (xor 1), 'set' (forces 1), 'reset' (forces 0), 'hold' (flop keeps old value for one clock edge;
           flop-only; site is the flop, ignores 'site' granularity)
  groups : list of (name, set(net ids)); ONE glitch action costs 1 and may fault up to m sites whose net is in the group,
           all in the same cycle. If singletons=True any single site can also still be faulted at cost 1.
Cost of an attack = number of cost-1 actions. Attacker input `sig` is free but constant over the run, != key (as glitchsat).
Goal: boot_word == goal_value observed at some cycle < N. Verdicts are BOUNDED (<= cap actions, N cycles, this netlist).
Primary inputs and constants are never faulted (same as glitchsat).
"""
import json, sys, os, time, collections, itertools, re
from z3 import (Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, PbLe, sat, unsat, is_true, simplify)

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- netlist (same reading logic as scripts/glitchsat.py)
class Netlist:
    def __init__(self, path, top):
        self.m = json.load(open(path))['modules'][top]
        m = self.m
        self.top = top
        self.ports = m['ports']
        self.drivers = {}   # net -> (cellname, type, connections)
        self.dffs = []      # (cellname, D, Q)
        for cn, c in m['cells'].items():
            t, con = c['type'], c['connections']
            if t == '$_DFF_P_':
                self.dffs.append((cn, con['D'][0], con['Q'][0]))
            else:
                self.drivers[con['Y'][0]] = (cn, t, con)
        self.names = {}
        for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.names.setdefault(b, f"{n}[{i}]" if len(x['bits']) > 1 else n)
        self.init = {}
        for n, x in m['netnames'].items():
            iv = x['attributes'].get('init')
            if iv:
                for i, b in enumerate(reversed(iv)):
                    self.init[x['bits'][i]] = (b == '1')
        self.qs = [q for _, _, q in self.dffs]
        for q in self.qs:
            self.init.setdefault(q, False)
        self.dq = {q: d for _, d, q in self.dffs}

    def fanins(self, b):
        if b in self.drivers:
            _, t, con = self.drivers[b]
            return [v[0] for p, v in con.items() if p != 'Y']
        return []

    def stats(self):
        return dict(gates=len(self.drivers), flops=len(self.dffs))

    def coi_and_dist(self, goal_bits):
        dist = {}
        dq = collections.deque()
        for b in goal_bits:
            if isinstance(b, int):
                dist[b] = 0; dq.append(b)
        while dq:
            b = dq.popleft()
            if b in self.drivers:
                nxt = [(f, dist[b]) for f in self.fanins(b)]
            elif b in self.dq:
                nxt = [(self.dq[b], dist[b] + 1)]
            else:
                nxt = []
            for f, d in nxt:
                if isinstance(f, int) and (f not in dist or d < dist[f]):
                    dist[f] = d; dq.append(f)
        return dist

    def pins(self, goal_out='boot_word', inputs_ok=False):
        """All fanout pins that can be faulted. Returns list of (pinid, src_net, sink_kind, sink_net, pinname).
        pinid is hashable: ('g', gate_out_net, pin) | ('d', q_net) | ('o', bit_index_in_goal_port)."""
        inputs = {b for p in self.ports.values() if p['direction'] == 'input' for b in p['bits']}
        if inputs_ok: inputs = set()
        out = []
        for y, (cn, t, con) in self.drivers.items():
            for p, v in con.items():
                if p != 'Y' and isinstance(v[0], int) and v[0] not in inputs:
                    out.append((('g', y, p), v[0], 'gate', y, p))
        for _, d, q in self.dffs:
            if isinstance(d, int) and d not in inputs:
                out.append((('d', q), d, 'dff', q, 'D'))
        for i, b in enumerate(self.ports[goal_out]['bits']):
            if isinstance(b, int) and b not in inputs:
                out.append((('o', i), b, 'port', i, goal_out))
        return out

    def input_bits(self):
        return [b for n, p in self.ports.items() if p['direction'] == 'input' and n != 'clk' for b in p['bits'] if isinstance(b, int)]

    def fanout_counts(self, goal_out='boot_word'):
        fo = collections.Counter()
        for _, src, *_ in self.pins(goal_out):
            fo[src] += 1
        return fo


# ---------------------------------------------------------------- fault model definition
class FaultModel:
    def __init__(self, name, site='stem', effects=('flip',), groups=None, m=1, singletons=True, desc='', inputs=False, exact=False):
        assert site in ('stem', 'branch', 'both')
        assert set(effects) <= {'flip', 'set', 'reset', 'hold'}
        self.name, self.site, self.effects = name, site, tuple(effects)
        self.groups = groups   # None, or callable(nl) -> list[(gname, frozenset(nets))], or list
        self.m, self.singletons, self.desc = m, singletons, desc
        self.inputs = inputs   # also allow faults on primary-input nets (stem) / their fanout pins (branch); clk excluded
        self.exact = exact     # group action flips ALL member sites together (not any subset up to m)

    def resolve_groups(self, nl):
        if self.groups is None: return []
        g = self.groups(nl) if callable(self.groups) else self.groups
        return [(n, frozenset(s)) for n, s in g]


def groups_flops(nl):
    return [('all_flops', frozenset(nl.qs))]

def groups_hood(nl):
    """1-hop neighbourhood of every gate output y: y, the non-input nets driving y, and the gate/flop nets y feeds.
    A crude, netlist-derived stand-in for 'physically adjacent logic'. NOT derived from any layout."""
    inputs = {b for p in nl.ports.values() if p['direction'] == 'input' for b in p['bits']}
    fo = collections.defaultdict(set)
    for y in nl.drivers:
        for f in nl.fanins(y):
            if isinstance(f, int): fo[f].add(y)
    for d, q in [(d, q) for _, d, q in nl.dffs]:
        if isinstance(d, int): fo[d].add(q)
    seen, out = set(), []
    for y in nl.drivers:
        s = {y} | {f for f in nl.fanins(y) if isinstance(f, int) and f not in inputs} | fo[y]
        s = frozenset(s)
        if s not in seen:
            seen.add(s); out.append((f'hood_{nl.names.get(y, y)}', s))
    return out

def groups_cone(nl):
    """For every net r (gate output, flop Q, or primary-input bit) the group {r} + all gate outputs in its COMBINATIONAL
    fanout cone (does not cross flops). Used with exact=True: the whole cone flips together as ONE event
    (crude locality / supply-dip model, NOT derived from layout)."""
    fo = collections.defaultdict(set)
    for y in nl.drivers:
        for f in nl.fanins(y):
            if isinstance(f, int): fo[f].add(y)
    seen, out = set(), []
    for r in list(nl.drivers) + list(nl.qs) + nl.input_bits():
        cone, st = {r}, [r]
        while st:
            x = st.pop()
            for y in fo[x]:
                if y not in cone: cone.add(y); st.append(y)
        s = frozenset(cone)
        if s not in seen:
            seen.add(s); out.append((f'cone_{nl.names.get(r, r)}', s))
    return out

def groups_from_regex(patterns):
    """user-defined groups: {group_name: regex matched (re.search) against the net's name}."""
    def f(nl):
        res = []
        for gn, pat in patterns.items():
            r = re.compile(pat)
            s = frozenset(b for b in list(nl.drivers) + nl.qs if r.search(nl.names.get(b, '')))
            if s: res.append((gn, s))
        return res
    return f

def groups_from_json(path):
    """user-defined groups from JSON {group: [net name substrings or regexes]}; same regex matching as above."""
    return groups_from_regex({k: '|'.join(v) for k, v in json.load(open(path)).items()})


MODELS = {m.name: m for m in [
    FaultModel('stem_flip', 'stem', ('flip',), desc='glitchsat model: one flip of a net hits all its fanout'),
    FaultModel('branch_flip', 'branch', ('flip',), desc='each fanout pin flipped separately (stem never)'),
    FaultModel('stem_or_branch_flip', 'both', ('flip',), desc='union of stem and branch flips'),
    FaultModel('set_only', 'stem', ('set',), desc='a net is forced to 1 for one cycle'),
    FaultModel('reset_only', 'stem', ('reset',), desc='a net is forced to 0 for one cycle'),
    FaultModel('branch_set', 'branch', ('set',), desc='a fanout pin forced to 1'),
    FaultModel('branch_reset', 'branch', ('reset',), desc='a fanout pin forced to 0'),
    FaultModel('flop_hold', 'stem', ('hold',), desc='clock skip of ONE flop: keeps old value for one edge'),
    FaultModel('group_flops_m2', 'stem', ('flip',), groups=groups_flops, m=2,
               desc='one glitch flips up to 2 flop Qs in the same cycle (cost 1); singles still allowed'),
    FaultModel('group_hood_m2', 'stem', ('flip',), groups=groups_hood, m=2,
               desc='one glitch flips up to 2 nets inside a 1-hop neighbourhood (cost 1); singles still allowed'),
    FaultModel('cone_flip_exact', 'stem', ('flip',), groups=groups_cone, m=10 ** 6, exact=True,
               desc='one event flips ALL gates in the combinational fanout cone of one net together (cost 1); singles still allowed'),
    FaultModel('hood_flip_exact', 'stem', ('flip',), groups=groups_hood, m=10 ** 6, exact=True,
               desc='one event flips ALL nets of a 1-hop neighbourhood together (cost 1); singles still allowed'),
    FaultModel('input_flip', 'stem', ('flip',), inputs=True, desc='stem flip incl. primary-input bits (a flipped input bit seen by all its fanout for one cycle)'),
    FaultModel('input_set', 'stem', ('set',), inputs=True, desc='set (force 1) incl. primary-input bits'),
    FaultModel('input_reset', 'stem', ('reset',), inputs=True, desc='reset (force 0) incl. primary-input bits'),
    FaultModel('input_branch_flip', 'branch', ('flip',), inputs=True, desc='branch flips incl. pins fed by primary inputs (buffered-input model)'),
    FaultModel('clock_skip_all', 'stem', ('hold',), groups=groups_flops, m=10 ** 6,
               desc='one clock glitch holds ANY subset of flops for one edge (cost 1)'),
]}


# ---------------------------------------------------------------- z3 model
def build(nl, N, fm, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, reduce='full'):
    ports = nl.ports
    goal_bits = ports[goal_out]['bits']
    inputs = {p: BitVec(f'in_{p}', len(v['bits'])) for p, v in ports.items()
              if v['direction'] == 'input' and p != 'clk'}
    inbit = {}
    for p, v in ports.items():
        if p in inputs:
            for i, b in enumerate(v['bits']):
                inbit[b] = Extract(i, i, inputs[p]) == 1
    dist = nl.coi_and_dist(goal_bits)
    pins = nl.pins(goal_out, fm.inputs)
    stem_sites = list(nl.qs) + list(nl.drivers.keys()) + (nl.input_bits() if fm.inputs else [])
    ok = (lambda t, d: True) if reduce == 'none' else (lambda t, d: d is not None and t + d <= N - 1)
    # fault variables: key (t, site, effect); site = ('n', net) | pinid
    F = {}
    src_of = {}       # site -> net used for group membership
    for t in range(N):
        for eff in fm.effects:
            if eff == 'hold':
                for q in nl.qs:
                    if t <= N - 2 and ok(t, None if q not in dist else dist[q] + 1):
                        F[(t, ('h', q), 'hold')] = Bool(f"f_{t}_h{q}"); src_of[('h', q)] = q
                continue
            if fm.site in ('stem', 'both'):
                for b in stem_sites:
                    if ok(t, dist.get(b)):
                        F[(t, ('n', b), eff)] = Bool(f"f_{t}_n{b}_{eff}"); src_of[('n', b)] = b
            if fm.site in ('branch', 'both'):
                for pid, src, kind, sink, pn in pins:
                    if kind == 'gate': d = dist.get(sink)
                    elif kind == 'dff': d = None if sink not in dist else dist[sink] + 1
                    else: d = 0
                    if ok(t, d):
                        F[(t, pid, eff)] = Bool(f"f_{t}_{'_'.join(map(str, pid))}_{eff}"); src_of[pid] = src
    # at most one effect per (t, site)
    cons = []
    bysite = collections.defaultdict(list)
    for (t, s, e), v in F.items(): bysite[(t, s)].append(v)
    for vs in bysite.values():
        for a, b in itertools.combinations(vs, 2): cons.append(Or(Not(a), Not(b)))

    def apply(v, t, site):
        for eff in ('flip', 'set', 'reset'):
            f = F.get((t, site, eff))
            if f is not None:
                v = Xor(v, f) if eff == 'flip' else (Or(v, f) if eff == 'set' else And(v, Not(f)))
        return v

    state = {q: BoolVal(nl.init[q]) for q in nl.qs}
    hits = []
    simp = reduce != 'none'
    for t in range(N):
        val = {}
        def raw(b):   # value of net b BEFORE branch faults, WITH stem fault (stem fault is part of the net)
            if b == '0' or b == 'x' or b == 'z': return BoolVal(False)
            if b == '1': return BoolVal(True)
            if b in val: return val[b]
            if b in inbit:
                v = apply(inbit[b], t, ('n', b)) if fm.inputs else inbit[b]
                val[b] = v; return v
            if b in state: v = state[b]
            else:
                _, ty, con = nl.drivers[b]
                g = lambda p: apply(raw(con[p][0]), t, ('g', b, p)) if isinstance(con[p][0], int) else raw(con[p][0])
                if ty == '$_AND_': v = And(g('A'), g('B'))
                elif ty == '$_OR_': v = Or(g('A'), g('B'))
                elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
                elif ty == '$_NOT_': v = Not(g('A'))
                elif ty == '$_MUX_': v = If(g('S'), g('B'), g('A'))
                else: raise Exception('unsupported cell ' + ty)
            v = apply(v, t, ('n', b))
            if simp: v = simplify(v)
            val[b] = v
            return v
        nxt = {}
        for q, d in nl.dq.items():
            dv = apply(raw(d), t, ('d', q)) if isinstance(d, int) else raw(d)
            h = F.get((t, ('h', q), 'hold'))
            nxt[q] = If(h, state[q], dv) if h is not None else dv
        w = [apply(raw(b), t, ('o', i)) if isinstance(b, int) else raw(b) for i, b in enumerate(goal_bits)]
        hits.append(And(*[w[i] == BoolVal(bool((goal_value >> i) & 1)) for i in range(len(w))]))
        state = {q: (simplify(v) if simp else v) for q, v in nxt.items()}
    s = Solver()
    s.add(Or(*hits))
    s.add(inputs[attack_in] != key)
    for c in cons: s.add(c)
    # cost variables
    groups = fm.resolve_groups(nl)
    cost = []
    info = dict(sites_modelled=len(F), groups=len(groups), model=fm.name, reduce=reduce)
    if not groups:
        cost = list(F.values())
    else:
        sing = {}
        covers = collections.defaultdict(list)    # (gname, t) -> list of c vars
        acts = {}
        for (t, s_, e), f in F.items():
            opts = []
            if fm.singletons:
                sv = Bool(f"s_{t}_{'_'.join(map(str, s_))}_{e}"); sing[(t, s_, e)] = sv; opts.append(sv)
            for gn, gs in groups:
                if src_of[s_] in gs:
                    a = acts.setdefault((gn, t), Bool(f"a_{gn}_{t}"))
                    c = Bool(f"c_{gn}_{t}_{'_'.join(map(str, s_))}_{e}")
                    s.add(Or(Not(c), a)); covers[(gn, t)].append(c); opts.append(c)
            s.add(Or(Not(f), *opts) if opts else Not(f))
        for key_, cs in covers.items():
            if len(cs) > fm.m: s.add(PbLe([(c, 1) for c in cs], fm.m))
        if fm.exact:   # an active group action flips every modelled member site in that cycle
            gset = dict(groups)
            for (t, s_, e), f in F.items():
                for gn, gs in groups:
                    if src_of[s_] in gs and (gn, t) in acts: s.add(Or(Not(acts[(gn, t)]), f))
        cost = list(sing.values()) + list(acts.values())
        info['actions_vars'] = len(acts)
    return s, F, cost, inputs, info


def min_cost(nl, N, fm, cap=4, timeout_ms=0, **kw):
    """Smallest number of cost-1 actions that achieves the goal, ascending search. Returns dict(min=int|None, status,...)
    status: 'ATTACK' (min exact: all smaller costs UNSAT), 'NONE_UP_TO_CAP' (UNSAT for every cost <= cap), 'TIMEOUT'."""
    t0 = time.time()
    s, F, cost, inputs, info = build(nl, N, fm, **kw)
    info['build_s'] = round(time.time() - t0, 2)
    if timeout_ms: s.set('timeout', timeout_ms)
    if not cost:
        return dict(min=None, status='NONE_UP_TO_CAP', cap=cap, info=info)
    for k in range(0, cap + 1):
        s.push(); s.add(PbLe([(c, 1) for c in cost], k))
        t1 = time.time(); r = s.check(); dt = round(time.time() - t1, 2)
        if r == sat:
            m = s.model()
            faults = sorted([(t, site, e) for (t, site, e), f in F.items() if is_true(m.eval(f, model_completion=True))],
                            key=lambda x: (x[0], str(x[1]), x[2]))
            atk = {p: m.eval(v, model_completion=True).as_long() for p, v in inputs.items()}
            s.pop()
            info['last_solve_s'] = dt
            return dict(min=k, status='ATTACK', faults=faults, inputs=atk, info=info)
        s.pop()
        if r != unsat:
            info['timeout_at_k'] = k
            return dict(min=None, status='TIMEOUT', cap=cap, info=info)
    return dict(min=None, status='NONE_UP_TO_CAP', cap=cap, info=info)


def describe(nl, site):
    if site[0] == 'n': return nl.names.get(site[1], str(site[1]))
    if site[0] == 'h': return 'hold:' + nl.names.get(site[1], str(site[1]))
    if site[0] == 'g': return f"pin {site[2]} of gate {nl.names.get(site[1], site[1])}"
    if site[0] == 'd': return f"D pin of flop {nl.names.get(site[1], site[1])}"
    if site[0] == 'o': return f"output-port bit {site[1]}"


def fmt(r):
    return str(r['min']) if r['status'] == 'ATTACK' else (f">{r['cap']}" if r['status'] == 'NONE_UP_TO_CAP' else 'TIMEOUT')


def main():
    import argparse
    ap = argparse.ArgumentParser(description='faultpack: minimum attack cost under a chosen fault model (bounded, modelled faults)')
    ap.add_argument('netlist'); ap.add_argument('--top', required=True)
    ap.add_argument('--model', default='stem_flip', help='one of: ' + ', '.join(MODELS))
    ap.add_argument('--cycles', type=int, default=6); ap.add_argument('--cap', type=int, default=4)
    ap.add_argument('--timeout-ms', type=int, default=0)
    ap.add_argument('--groups-json', help='user-defined groups {name:[regex,...]} (overrides the model groups; use with --m)')
    ap.add_argument('--m', type=int, help='max sites per glitch action for --groups-json')
    ap.add_argument('--effects', default=None, help='override effects, e.g. flip,set')
    ap.add_argument('--site', default=None, choices=['stem', 'branch', 'both'])
    a = ap.parse_args()
    fm = MODELS[a.model]
    if a.groups_json or a.effects or a.site:
        fm = FaultModel(a.model + '*', a.site or fm.site, tuple(a.effects.split(',')) if a.effects else fm.effects,
                        groups_from_json(a.groups_json) if a.groups_json else fm.groups, a.m or fm.m, True)
    nl = Netlist(a.netlist, a.top)
    r = min_cost(nl, a.cycles, fm, a.cap, a.timeout_ms)
    print(f"{a.netlist} {a.top} model={fm.name} N={a.cycles}: min cost = {fmt(r)}  [{r['status']}]  {r['info']}")
    for t, site, e in r.get('faults', []):
        print(f"  cycle {t}: {e} {describe(nl, site)}")
    if 'inputs' in r: print('  input', r['inputs'])


if __name__ == '__main__':
    main()
