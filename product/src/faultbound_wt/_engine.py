# ORIGIN: copied from scripts/glitchsat.py of this repository (GlitchSAT), engine
# part only (Netlist, build, solve, honest_boots, explain). The original file is NOT modified; this copy is a
# snapshot and will drift unless re-synced by hand. Local changes versus the original (all marked "PS-CHANGE"):
#   1. the CLI / synth / run_check section is dropped (the package has its own CLI and runner);
#   2. build() and solve() accept `site_filter`, a predicate (net_bit, kind) -> bool restricting which nets may be
#      faulted (threat-model config); with filter=None behaviour is identical to the original;
#   3. Netlist records all net aliases (nl.aliases) so config globs can match any name of a net, and reports
#      unsupported cell types at load time (UnsupportedCell) instead of crashing mid-build.
#   5. (PS4) build()/solve() accept goal_mask (consumed bits only; M1 semantics, research/c3/m1/gs_mask.py), input_sites (input-port bits are
#      fault sites, one shared site per bit; B2 semantics, research/c2/b2_scope/gs.py) and init_mode 'arbitrary' (free power-up state, B2 'free');
#      with the defaults (None / False / 'known') behaviour is identical.
#   4. (PS2) explain() text derives from the fault set / cone structure instead of canned prose; async-reset flops get a specific refusal message.
# H1 also hardened this copy (NetlistError etc.); see research/c3/h1/H1_LOG.md. No third-party source is vendored; only z3-solver is imported.
#!/usr/bin/env python3
"""glitchsat: bounded fault-injection model checker for gate-level Verilog (Yosys JSON + z3).

Fault model (MODELLED, not physical): a fault is a single-cycle bit flip of
  (a) the output net of any combinational gate, or (b) the Q net of any flip-flop, at one clock cycle t.
At most K faults in total over cycles 0..N-1. The attacker input (default `sig`) is a free value held constant.
Attack goal: some output port equals a goal value (default boot_word == 0x96) at some cycle < N while the
attacker input differs from the legitimate key.
Verdicts are BOUNDED: NO_ATTACK_UP_TO_BOUND means no attack with <=K faults within N cycles. It is not a proof for
more cycles or more faults.
"""
import argparse, re, json, os, subprocess, sys, time, hashlib, collections
from z3 import (Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, Implies, PbLe, sat, unsat,
                is_true, simplify, set_param)

NOTE = ("BOUNDED, NOT UNBOUNDED: verdict holds only for <= {k} single-cycle bit-flip faults (gate outputs and flop Q) "
        "within {n} cycles on this synthesized netlist. It says nothing about more faults, longer runs, other fault "
        "types (stuck-at, multi-bit/spatial, clock/voltage effects), or physical feasibility. Toy design; modelled faults.")


# ---------------------------------------------------------------- netlist
# H1 hardening: malformed netlists fail LOUDLY with NetlistError (never a silent verdict).
class NetlistError(Exception):
    """Malformed or unsupported input netlist / usage error. CLIs map it to exit code 3."""


def load_json_strict(path):
    """json.load that rejects duplicate object keys (a duplicated cell/net name would otherwise silently drop one)."""
    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                raise NetlistError(f"duplicate JSON key {k!r} in {path}: the later entry would silently replace the earlier one")
            d[k] = v
        return d
    try:
        with open(path) as f:
            return json.load(f, object_pairs_hook=hook)
    except RecursionError:
        raise NetlistError(f"{path}: JSON nesting too deep")
    except (OSError, ValueError) as e:
        raise NetlistError(f"cannot read {path} as JSON: {e}")


_CELL_PINS = {'$_AND_': ('A', 'B'), '$_OR_': ('A', 'B'), '$_XOR_': ('A', 'B'), '$_NOT_': ('A',), '$_MUX_': ('A', 'B', 'S')}
_PIN_ORDER = {'$_AND_': ('A', 'B'), '$_OR_': ('A', 'B'), '$_XOR_': ('A', 'B'), '$_NOT_': ('A',), '$_MUX_': ('S', 'B', 'A')}  # z3 term build order of the original recursive evaluator
SUPPORTED = {'$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_'}   # PS-CHANGE
class NothingToAttack(NetlistError):   # H2 (N4)
    pass


class UnsupportedCell(NetlistError):   # PS-CHANGE
    pass

def _unsupported_msg(cn, t):   # PS2-CHANGE: name the async-reset case explicitly
    base = f"cell {cn} has type {t}, which this tool does not model; supported: {sorted(SUPPORTED)} + $_DFF_P_ (plain rising-edge flop)."
    if re.match(r"^\$_DFF_[PN][PN][01]_$", str(t)) or re.match(r"^\$_DFFSR", str(t)):
        return (base + " This is a flop with an ASYNCHRONOUS reset/set. Async reset is not modelled (its timing semantics would need a "
                "model of the reset signal inside a cycle). Re-synthesize with a synchronous reset (`if (rst) ...` inside "
                "`always @(posedge clk)` only, no `or posedge rst`), or run `async2sync` in Yosys before `write_json` and state that in your scope.")
    return base + " (latch, enable/sync-reset flop, memory or other cell with no Y output): resynthesize to plain gates + $_DFF_P_."


class Netlist:
    def __init__(self, path, top):
        doc = load_json_strict(path)
        if not isinstance(doc, dict) or not isinstance(doc.get('modules'), dict) or top not in doc['modules']:
            raise NetlistError(f"{path}: no module {top!r} (modules: {list(doc.get('modules', {})) if isinstance(doc, dict) and isinstance(doc.get('modules'), dict) else 'none'})")
        self.m = doc['modules'][top]
        m = self.m
        self.top = top
        self.ports = m['ports']
        self.drivers = {}   # net -> (cellname, type, connections)
        self.dffs = []      # (cellname, D, Q)
        self.driver_cell = {}   # net -> cell name of whatever drives it (gate Y, flop Q), for multi-driver detection
        in_bits = {b for p in self.ports.values() if p.get('direction') in ('input', 'inout') for b in p['bits'] if isinstance(b, int)}

        def _claim(net, cn):
            if not isinstance(net, int):
                raise NetlistError(f"cell {cn} drives constant/unknown net {net!r}")
            if net in self.driver_cell:
                raise NetlistError(f"net {net} has multiple drivers: cells {self.driver_cell[net]!r} and {cn!r} (result would depend on cell order; refusing)")
            if net in in_bits:
                raise NetlistError(f"net {net} is driven by cell {cn!r} but is also a module input port bit (multiple drivers)")
            self.driver_cell[net] = cn
        for cn, c in m['cells'].items():
            t, con = c.get('type'), c.get('connections')
            if t == '$scopeinfo' and not any(d != 'input' for d in (c.get('port_directions') or {}).values()):
                # H5: Yosys >= 0.38 emits $scopeinfo cells after flatten. They carry hierarchy metadata only (attributes/parameters);
                # they have no ports that drive or read logic, so they are skipped (no gate, no net). A $scopeinfo with any
                # non-input port_direction is NOT skipped and falls through to the normal rejection. Unknown types still fail loudly.
                continue
            if not isinstance(con, dict):
                raise NetlistError(f"cell {cn} has no 'connections'")
            if t == '$_DFF_P_':
                for p in ('D', 'Q'):
                    if len(con.get(p, [])) != 1:
                        raise NetlistError(f"flop {cn}: pin {p} missing or not 1 bit")
                _claim(con['Q'][0], cn)
                self.dffs.append((cn, con['D'][0], con['Q'][0]))
            elif 'Y' not in con:
                raise UnsupportedCell(_unsupported_msg(cn, t))
            else:
                if len(con['Y']) != 1:
                    raise NetlistError(f"cell {cn} ({t}): Y is not 1 bit")
                if t in _CELL_PINS:
                    for p in _CELL_PINS[t]:
                        if len(con.get(p, [])) != 1:
                            raise NetlistError(f"cell {cn} ({t}): pin {p} missing or not 1 bit")
                _claim(con['Y'][0], cn)
                self.drivers[con['Y'][0]] = (cn, t, con)
        self.names = {}
        for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.names.setdefault(b, f"{n}[{i}]" if len(x['bits']) > 1 else n)
        self.aliases = collections.defaultdict(list)   # PS-CHANGE: every name of each net bit
        for n, x in m['netnames'].items():
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    self.aliases[b].append(f"{n}[{i}]" if len(x['bits']) > 1 else n)
        for b, (cn, t, con) in self.drivers.items():   # PS-CHANGE
            if t not in SUPPORTED:
                raise UnsupportedCell(f"cell {cn} has type {t}; supported: {sorted(SUPPORTED)} (+ $_DFF_P_)")
        self.init = {}
        for n, x in m['netnames'].items():
            iv = x['attributes'].get('init')
            if iv:
                if len(iv) > len(x['bits']):
                    raise NetlistError(f"net {n}: init {iv!r} is wider than the net")
                for i, b in enumerate(reversed(iv)):
                    if b not in '01':
                        if x['bits'][i] in self.driver_cell and any(x['bits'][i] == q for _, _, q in self.dffs):
                            raise NetlistError(f"flop net {n}: init value {iv!r} contains {b!r} (unknown); the model needs a known power-up state "
                                               "(treating x as 0 would silently hide attacks). Give the flop a 0/1 init.")
                        continue
                    self.init[x['bits'][i]] = (b == '1')
        self.qs = [q for _, _, q in self.dffs]
        for q in self.qs:
            self.init.setdefault(q, False)
        self.dq = {q: d for _, d, q in self.dffs}
        self._check_acyclic()

    def _check_acyclic(self):
        """Combinational loops (through gates only; flops break them) are an input error, not a RecursionError."""
        color = {}
        for root in self.drivers:
            if root in color:
                continue
            stack = [(root, iter(self.fanins(root)))]
            color[root] = 1
            while stack:
                b, it = stack[-1]
                for f in it:
                    if f in self.drivers:
                        if color.get(f) == 1:
                            raise NetlistError(f"combinational loop through net {f} (cell {self.drivers[f][0]!r}); the model needs acyclic logic between flops")
                        if f not in color:
                            color[f] = 1
                            stack.append((f, iter(self.fanins(f))))
                            break
                else:
                    color[b] = 2
                    stack.pop()

    def fanins(self, b):
        if b in self.drivers:
            _, t, con = self.drivers[b]
            return [v[0] for p, v in con.items() if p != 'Y']
        return []

    def stats(self):
        return dict(gates=len(self.drivers), flops=len(self.dffs))

    def coi_and_dist(self, goal_bits):
        """Backward cone of the goal output bits. dist[b] = min #clock edges between a flip of b and a goal bit."""
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


# ---------------------------------------------------------------- model + solve
def build(nl, N, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3,
          reduce='full', bad_only=True, fixed_in=None, site_filter=None,
          goal_mask=None, input_sites=False, init_mode='known'):   # PS4-CHANGE
    ports = nl.ports
    if goal_out not in ports or ports[goal_out].get('direction') != 'output':
        raise NetlistError(f"goal output {goal_out!r} is not an output port (outputs: {[p for p, v in ports.items() if v.get('direction') == 'output']})")
    if attack_in not in ports or ports[attack_in].get('direction') != 'input':
        raise NetlistError(f"attacker input {attack_in!r} is not an input port (inputs: {[p for p, v in ports.items() if v.get('direction') == 'input']})")
    goal_bits = ports[goal_out]['bits']
    inputs = {p: BitVec(f'in_{p}', len(v['bits'])) for p, v in ports.items()
              if v['direction'] == 'input' and p != 'clk'}
    inbit = {}
    for p, v in ports.items():
        if p in inputs:
            for i, b in enumerate(v['bits']):
                inbit[b] = Extract(i, i, inputs[p]) == 1
    dist = nl.coi_and_dist(goal_bits)
    in_sites = [b for p, v in ports.items() if v['direction'] == 'input' and p != 'clk' for b in v['bits'] if isinstance(b, int)] if input_sites else []   # PS4-CHANGE
    allsites = list(nl.qs) + list(nl.drivers.keys()) + in_sites
    if reduce == 'none':
        usable = lambda t, b: True
    elif reduce == 'coi':
        usable = lambda t, b: b in dist
    else:  # full: cone of influence + temporal reach (flip must be able to reach goal bit before the horizon)
        usable = lambda t, b: b in dist and t + dist[b] <= N - 1
    F = {}
    for t in range(N):
        for b in allsites:
            if usable(t, b) and (site_filter is None or site_filter(b, 'flop' if b in nl.dq else ('input' if b in inbit else 'gate'))):   # PS-CHANGE / PS4
                F[(t, b)] = Bool(f"f_{t}_{b}")
    if init_mode in ('arbitrary', 'free_nongoal'):   # PS4-CHANGE: every flop may power up as 0 or 1 (chosen by the solver); PS5: free_nongoal adds a constraint below
        initvars = {q: Bool(f"init_{q}") for q in nl.qs}
        state0 = dict(initvars)
    else:
        initvars = {}
        state0 = {q: BoolVal(nl.init[q]) for q in nl.qs}

    def unroll(use_f):
        state = dict(state0)
        hits = []
        simp = reduce != 'none'
        for t in range(N):
            val = {}
            for b in in_sites:   # PS4-CHANGE: a flipped input net is seen by ALL of its fanout (one shared site per input bit)
                if use_f and (t, b) in F:
                    val[b] = Xor(inbit[b], F[(t, b)])

            def get(root):
                """Iterative post-order evaluation (no Python recursion limit); builds the same z3 terms in the same order as the
                original recursive version (children A,B / S,B,A first, then the gate, then fault xor, then simplify)."""
                stack = [root]
                while stack:
                    b = stack[-1]
                    if b == '0': stack.pop(); continue
                    if b == '1': stack.pop(); continue
                    if b == 'x' or b == 'z':
                        raise NetlistError("constant x/z (unknown) bit in the logic cone of the goal or flop inputs; refusing (would be treated as 0)")
                    if b in val or b in inbit:
                        stack.pop(); continue
                    if b in state:
                        v = state[b]
                    else:
                        if b not in nl.drivers:
                            raise NetlistError(f"net {nl.names.get(b, b)!r} (id {b}) is used but has no driver and is not an input port (undriven)")
                        _, ty, con = nl.drivers[b]
                        if ty not in _PIN_ORDER:
                            raise NetlistError('unsupported cell ' + ty)
                        pend = [con[p][0] for p in _PIN_ORDER[ty]
                                if con[p][0] not in ('0', '1') and con[p][0] not in val and con[p][0] not in inbit]
                        if pend:
                            stack.extend(reversed(pend)); continue
                        g = lambda p: cget(con[p][0])
                        if ty == '$_AND_': v = And(g('A'), g('B'))
                        elif ty == '$_OR_': v = Or(g('A'), g('B'))
                        elif ty == '$_XOR_': v = Xor(g('A'), g('B'))
                        elif ty == '$_NOT_': v = Not(g('A'))
                        else: v = If(g('S'), g('B'), g('A'))
                    if use_f and (t, b) in F: v = Xor(v, F[(t, b)])
                    if simp: v = simplify(v)
                    val[b] = v
                    stack.pop()
                return cget(root)

            def cget(b):
                if b == '0': return BoolVal(False)
                if b == '1': return BoolVal(True)
                if b in val: return val[b]
                return inbit[b]
            nxt = {q: get(d) for q, d in nl.dq.items()}
            w = [get(b) for b in goal_bits]
            hits.append(And(*[w[i] == BoolVal(bool((goal_value >> i) & 1)) for i in range(len(w)) if goal_mask is None or (goal_mask >> i) & 1]))   # PS4: mask
            state = nxt
        return hits

    hits = unroll(True)
    s = Solver()
    s.add(Or(*hits))
    if init_mode == 'free_nongoal':   # PS5 (B2 semantics): the fault-free run from this power-up state, same inputs, never accepts
        nongoal = Not(Or(*unroll(False)))
        s.add(nongoal)
    ain = inputs[attack_in]
    if bad_only: s.add(ain != key)
    if fixed_in is not None: s.add(ain == fixed_in)
    info = dict(sites_total=len(allsites) * N, sites_modelled=len(F), reduce=reduce, initvars=initvars)
    if init_mode == 'free_nongoal':   # H2 (N4): the admissible power-up set must be non-empty, else 'no attack' would be vacuous
        s2 = Solver(); s2.add(nongoal)
        if bad_only: s2.add(ain != key)
        if fixed_in is not None: s2.add(ain == fixed_in)
        info['nongoal_check'] = s2
    return s, F, inputs, info


def seq_counter(xs, kmax):
    """T3/R27: unary sequential counter (Sinz style, one-directional x -> count). Returns (clauses, outs); outs[j] is forced
    TRUE whenever at least j of xs are true (j = 1..kmax+1). Assuming Not(outs[j+1]) means 'at most j' (j <= kmax)."""
    cl = []; prev = [BoolVal(False)] * (kmax + 2)
    for i, x in enumerate(xs):
        cur = [BoolVal(False)] * (kmax + 2)
        for j in range(1, kmax + 2):
            c = Bool(f'__amk_{i}_{j}')
            cl.append(Implies(prev[j], c))
            cl.append(Implies(And(x, prev[j - 1]) if j > 1 else x, c))
            cur[j] = c
        prev = cur
    return cl, prev


# at-most-k encoding: 'counter' (T3, default; sequential counter + assumption literals) or 'legacy' (PbLe, push/pop).
# Override per call (solve(..., amk=...)), by the CLI flag --amk (scripts/glitchsat.py) or env FAULTBOUND_AMK (product).
AMK_DEFAULT = 'counter'


COUNT_RULES = ('stem', 'fanout_pins', 'fanout_gates')   # PS6


def net_weights(nl, rule):
    """PS6: cost of ONE flip of each net under a counting rule. stem: every flip costs 1 (a stem flip reaches all its fanout).
    fanout_pins / fanout_gates (research/c3/rep, docs/edu/tools/edu_scope.py): cost = number of sink pins the net feeds
    (gate input pins incl. repeated pins of one gate, flop D pins; fanout_pins also counts output-port bits), at least 1.
    Returns a dict net -> weight, or None for 'stem'."""
    if rule == 'stem':
        return None
    if rule not in COUNT_RULES:
        raise ValueError(f'count rule must be one of {COUNT_RULES}, not {rule!r}')
    pins = collections.Counter(); outp = collections.Counter()
    for o, (cn, t, con) in nl.drivers.items():
        for p, v in con.items():
            if p != 'Y' and isinstance(v[0], int): pins[v[0]] += 1
    for q, d in nl.dq.items():
        if isinstance(d, int): pins[d] += 1
    if rule == 'fanout_pins':
        for p, v in nl.ports.items():
            if v['direction'] == 'output':
                for b in v['bits']:
                    if isinstance(b, int): outp[b] += 1
    allnets = set(pins) | set(outp) | set(nl.drivers) | set(nl.qs)
    for p, v in nl.ports.items():
        for b in v['bits']:
            if isinstance(b, int): allnets.add(b)
    return {b: max(1, pins[b] + outp[b]) for b in allnets}


def solve(nl, N, k, timeout_ms=0, minimize=True, amk=None, count_rule='stem', **kw):
    amk = amk or os.environ.get('FAULTBOUND_AMK') or AMK_DEFAULT
    if amk not in ('counter', 'legacy'): raise ValueError(f'amk must be counter or legacy, not {amk!r}')
    wmap = net_weights(nl, count_rule)   # PS6
    wt = (lambda tb: 1) if wmap is None else (lambda tb: wmap[tb[1]])
    t0 = time.time()
    s, F, inputs, info = build(nl, N, **kw)
    info['build_s'] = round(time.time() - t0, 3)
    info['count_rule'] = count_rule
    if timeout_ms: s.set('timeout', timeout_ms)
    s2 = info.pop('nongoal_check', None)   # H2 (N4)
    if s2 is not None:
        if timeout_ms: s2.set('timeout', timeout_ms)
        if s2.check() == unsat:
            raise NothingToAttack('goal output is constant: nothing to attack. With --init free_nongoal no power-up state exists from which the fault-free design '
                                  'does not already reach the goal (the output port is constant or always accepting), so the set of admissible start states is '
                                  'empty and a "no attack" verdict would be vacuous. Use --init known, or pick a goal output that depends on the inputs/state.')
    allf = list(F.values())
    if wmap is not None:   # PS6: a flip of weight w is w items in the counter; flips heavier than the budget are impossible
        too_heavy = [f for tb, f in F.items() if wt(tb) > k]
        if too_heavy: s.add(*[Not(f) for f in too_heavy])
        allf = [f for tb, f in F.items() if wt(tb) <= k for _ in range(wt(tb))]
    cost = lambda faults: sum(wt(tb) for tb in faults)
    info['amk'] = amk
    outs = None
    if allf and amk == 'counter':
        kcap = min(k, len(allf))   # H2 (N8): a bound above the number of flip items is vacuous; the counter is O(items x kcap)
        cl, outs = seq_counter(allf, kcap); s.add(*cl)
        atmost = lambda j: [BoolVal(False)] if j < 0 else ([Not(outs[j + 1])] if j <= kcap else [])   # j<0: 'at most -1' is unsatisfiable (as PbLe)
    elif allf: s.add(PbLe([(f, 1) for f in allf], k))
    t0 = time.time(); r = s.check(*(atmost(kcap) if outs else [])); info['solve_s'] = round(time.time() - t0, 3)
    if r == unsat: return 'NO_ATTACK_UP_TO_BOUND', info, None
    if r != sat: return 'UNKNOWN_TIMEOUT', info, None
    def extract(mod):
        return [kk for kk, f in F.items() if is_true(mod.eval(f, model_completion=True))]
    mod = s.model(); best = extract(mod)
    if outs and cost(best) > kcap: raise RuntimeError(f'internal error: model has cost {cost(best)}, bound is {kcap} (at-most-k encoding inconsistent)')
    t0 = time.time()
    while minimize and best:
        if outs:
            r2 = s.check(*atmost(cost(best) - 1))
            if r2 == sat: mod = s.model(); best = extract(mod)
            else:
                if r2 != unsat: info['minimize_incomplete'] = True   # PS4: timeout while minimizing; the count is an upper bound
                break
            continue
        s.push(); s.add(PbLe([(f, 1) for f in allf], cost(best) - 1))
        r2 = s.check()
        if r2 == sat:
            mod = s.model(); best = extract(mod); s.pop()
        else:
            s.pop()
            if r2 != unsat: info['minimize_incomplete'] = True   # PS4: timeout while minimizing; the count is an upper bound
            break
    info['minimize_s'] = round(time.time() - t0, 3)
    atk = {p: mod.eval(v, model_completion=True).as_long() for p, v in inputs.items()}
    res = dict(inputs=atk, faults=sorted(best, key=lambda x: (x[0], x[1])), cost=cost(best), weights={b: wmap[b] for _, b in best} if wmap is not None else None)   # PS6: cost
    if info.get('initvars'):   # PS4
        res['init_ones'] = sorted(q for q, v in info['initvars'].items() if is_true(mod.eval(v, model_completion=True)))
    return 'ATTACK_FOUND', info, res


def honest_boots(nl, N, **kw):
    """Sanity: fault-free run with the legitimate key reaches the goal."""
    kw = dict(kw); key = kw.get('key', 0xC3)
    kw['init_mode'] = 'known'; kw['input_sites'] = False   # PS4: the honest check is always the fault-free known-state run
    v, info, res = solve(nl, N, 0, minimize=False, bad_only=False, fixed_in=key, **kw)
    return v == 'ATTACK_FOUND'


# ---------------------------------------------------------------- explanation
def support(nl, b, memo=None):
    memo = {} if memo is None else memo
    stack = [b]   # iterative post-order (H1: no recursion limit on deep logic)
    while stack:
        x = stack[-1]
        if x in memo: stack.pop(); continue
        if x in nl.drivers:
            fi = [f for f in nl.fanins(x) if isinstance(f, int)]
            pend = [f for f in fi if f not in memo]
            if pend: stack.extend(pend); continue
            memo[x] = frozenset().union(*[memo[f] for f in fi])
        elif x in nl.dq:
            memo[x] = frozenset([('flop', x)])
        else:
            memo[x] = frozenset([x])
        stack.pop()
    return memo[b]

def forward_reach(nl, b, goal_bits, maxcyc):
    """goal bits reachable from b through combinational fanout (<= maxcyc flop crossings)."""
    fan = collections.defaultdict(list)
    for o, (_, _, con) in nl.drivers.items():
        for f in nl.fanins(o): fan[f].append(o)
    for d, q in [(d, q) for _, d, q in nl.dffs]: fan[d].append(('Q', q))
    seen = {(b, 0)}; st = [(b, 0)]; goals = set(goal_bits)
    reach = set()
    while st:
        x, c = st.pop()
        if x in goals: reach.add(x)
        for y in fan.get(x, []):
            if isinstance(y, tuple): y, c2 = y[1], c + 1
            else: c2 = c
            if c2 <= maxcyc and (y, c2) not in seen: seen.add((y, c2)); st.append((y, c2))
    return reach

def explain(nl, res, k_found, N, goal_out='boot_word', attack_in='sig'):
    ports = nl.ports
    goal_bits = ports[goal_out]['bits']
    in_bits = set(ports[attack_in]['bits'])
    faults = res['faults']
    lines, nets = [], []
    for t, b in faults:
        nm = nl.names.get(b, str(b))
        kind = 'flip-flop Q' if b in nl.dq else ('gate output' if b in nl.drivers else 'input net')   # PS4: input sites
        gt = nl.drivers[b][1].strip('$_') if b in nl.drivers else ('DFF' if b in nl.dq else 'input')
        sup = support(nl, b)
        n_in = len(sup & in_bits)
        reach = forward_reach(nl, b, goal_bits, N)
        nets.append(dict(net=nm, cycle=t, kind=kind, gate=gt, input_bits_in_fanin_cone=n_in,
                         goal_bits_reached=len(reach), goal_bits_total=len(goal_bits)))
    ncyc = len({t for t, _ in faults})
    GENERIC = "(Generic design pattern, not derived from this netlist.) "
    if k_found == 0:
        summary = ("NO FAULT NEEDED: with no flips at all, an attacker input different from `legitimate_value` already makes "
                   f"`{goal_out}` reach the goal value. Either the design accepts more than one input, or the goal / legitimate_value in the config is wrong.")
        fix = "Check the threat-model config (goal value, legitimate_value) before treating this as a design finding."
    elif k_found == 1:
        n = nets[0]
        if n['kind'] == 'gate output':
            conv = _parallel_fanins(nl, faults[0][1], in_bits)
            parts = [f"one {n['gate']} gate output, net `{n['net']}`, has {n['input_bits_in_fanin_cone']} bit(s) of `{attack_in}` in its fan-in cone "
                     f"and reaches {n['goal_bits_reached']} of {n['goal_bits_total']} bits of `{goal_out}`"]
            if conv:
                parts.append("STRUCTURE: its direct fan-in nets " + " and ".join(f"`{x}`" for x in conv) +
                             " are distinct sub-circuits that depend on the same input bits (parallel checks that this gate recombines)")
            summary = ("SINGLE POINT OF FAILURE: " + "; ".join(parts) + f". Flipping it for ONE cycle (cycle {n['cycle']}) is enough to reach the goal value.")
            fix = GENERIC + ("Avoid letting one net decide: duplicate the logic feeding it with copies that share no gate, and decide per bit." if not conv else
                             "Keep each parallel check's result in its own disjoint output bits instead of recombining them in one gate.")
        elif n['kind'] == 'input net':
            summary = (f"SINGLE POINT OF FAILURE: flipping the primary-input net `{n['net']}` for ONE cycle (cycle {n['cycle']}) is enough to reach the goal "
                       "value (input nets are fault sites in this scope: --input-sites all).")
            fix = GENERIC + "Do not let one sampled input bit decide: sample inputs redundantly (several registers, several cycles) and compare."
        else:
            summary = (f"SINGLE POINT OF FAILURE: the state register bit `{n['net']}` flipped for one cycle (cycle {n['cycle']}) is enough to reach "
                       f"the goal value on `{goal_out}` (reaches {n['goal_bits_reached']}/{n['goal_bits_total']} goal bits).")
            fix = GENERIC + "Encode state with Hamming distance above the fault budget, or add a shadow register compared every cycle."
    else:
        names = ', '.join(f"`{n['net']}`@{n['cycle']}" for n in nets)
        distinct = len({n['net'] for n in nets})
        summary = (f"MINIMUM ATTACK COST = {k_found} flips ({names}), on {distinct} distinct net(s) in {ncyc} distinct cycle(s). "
                   f"With fewer flips the solver found no attack within the bound (cycles={N}).")
        fix = GENERIC + f"To raise the cost above {k_found}, the circuit must be changed so that no {k_found} flips suffice; re-run the tool at a larger bound to check."
    return dict(summary=summary, fix_pattern=fix, fault_details=nets)


def _parallel_fanins(nl, b, in_bits):
    """Direct fan-in nets of gate b that are distinct gate outputs with identical, non-empty supports over the attacker input
    bits (structural 'parallel checks'). Empty list when the structure does not show it."""
    fis = [f for f in nl.fanins(b) if isinstance(f, int) and f in nl.drivers]
    sups = {f: frozenset(support(nl, f) & in_bits) for f in fis}
    for i, f in enumerate(fis):
        for g in fis[i + 1:]:
            if f != g and sups[f] and sups[f] == sups[g]:
                return [nl.names.get(f, str(f)), nl.names.get(g, str(g))]
    return []
