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
import argparse, json, os, re, subprocess, sys, time, hashlib, collections
try:   # z3 is imported here but only needed to solve: --help, --version and input checks work without it
    from z3 import (Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, Implies, PbLe, sat, unsat,
                    is_true, simplify, set_param)
    _Z3_IMPORT_ERROR = None
except ImportError as _e:
    _Z3_IMPORT_ERROR = _e

__version__ = '0.9.0'
Z3_MISSING = 'z3-solver is not installed: pip install z3-solver'


def _require_z3():
    """Raise a one-line ImportError when z3 is missing (instead of a NameError deep inside the model build)."""
    if _Z3_IMPORT_ERROR is not None:
        raise ImportError(Z3_MISSING) from _Z3_IMPORT_ERROR

HERE = os.path.dirname(os.path.abspath(__file__))
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
SUPPORTED = {'$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_'}
class UnsupportedCell(NetlistError):
    pass

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
                raise UnsupportedCell(f"cell {cn} has type {t} with no Y output (latch, enable/reset flop, memory or other unsupported flop/cell); supported: {sorted(SUPPORTED)} + $_DFF_P_")
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
        self.init = {}
        unknown_init = {}   # flop bit id -> (net, init, char) for an x/z init seen at some alias of that bit
        for n, x in m['netnames'].items():
            iv = x['attributes'].get('init')
            if iv:
                if len(iv) > len(x['bits']):
                    raise NetlistError(f"net {n}: init {iv!r} is wider than the net")
                for i, b in enumerate(reversed(iv)):
                    if b not in '01':
                        if x['bits'][i] in self.driver_cell and any(x['bits'][i] == q for _, _, q in self.dffs):
                            unknown_init.setdefault(x['bits'][i], (n, iv, b))
                        continue
                    self.init[x['bits'][i]] = (b == '1')
        # one flop bit can sit at several net names/positions: an x at one alias yields to a known value at another
        for bit, (n, iv, b) in unknown_init.items():
            if bit not in self.init:
                raise NetlistError(f"flop net {n}: init value {iv!r} contains {b!r} (unknown); the model needs a known power-up state "
                                   "(treating x as 0 would silently hide attacks). Give the flop a 0/1 init.")
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
          reduce='full', bad_only=True, fixed_in=None):
    _require_z3()
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
    allsites = list(nl.qs) + list(nl.drivers.keys())
    if reduce == 'none':
        usable = lambda t, b: True
    elif reduce == 'coi':
        usable = lambda t, b: b in dist
    else:  # full: cone of influence + temporal reach (flip must be able to reach goal bit before the horizon)
        usable = lambda t, b: b in dist and t + dist[b] <= N - 1
    F = {}
    for t in range(N):
        for b in allsites:
            if usable(t, b):
                F[(t, b)] = Bool(f"f_{t}_{b}")
    state = {q: BoolVal(nl.init[q]) for q in nl.qs}
    hits = []
    simp = reduce != 'none'
    for t in range(N):
        val = {}

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
                if (t, b) in F: v = Xor(v, F[(t, b)])
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
        hits.append(And(*[w[i] == BoolVal(bool((goal_value >> i) & 1)) for i in range(len(w))]))
        state = nxt
    s = Solver()
    s.add(Or(*hits))
    ain = inputs[attack_in]
    if bad_only: s.add(ain != key)
    if fixed_in is not None: s.add(ain == fixed_in)
    return s, F, inputs, dict(sites_total=len(allsites) * N, sites_modelled=len(F), reduce=reduce)


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


def solve(nl, N, k, timeout_ms=0, minimize=True, amk=None, **kw):
    amk = amk or os.environ.get('FAULTBOUND_AMK') or AMK_DEFAULT
    if amk not in ('counter', 'legacy'): raise ValueError(f'amk must be counter or legacy, not {amk!r}')
    t0 = time.time()
    s, F, inputs, info = build(nl, N, **kw)
    info['build_s'] = round(time.time() - t0, 3)
    if timeout_ms: s.set('timeout', timeout_ms)
    allf = list(F.values())
    info['amk'] = amk
    outs = None
    if allf and amk == 'counter':
        kcap = k
        cl, outs = seq_counter(allf, kcap); s.add(*cl)
        atmost = lambda j: [BoolVal(False)] if j < 0 else ([Not(outs[j + 1])] if j <= kcap else [])   # j<0: 'at most -1' is unsatisfiable (as PbLe)
    elif allf: s.add(PbLe([(f, 1) for f in allf], k))
    t0 = time.time(); r = s.check(*(atmost(kcap) if outs else [])); info['solve_s'] = round(time.time() - t0, 3)
    if r == unsat: return 'NO_ATTACK_UP_TO_BOUND', info, None
    if r != sat: return 'UNKNOWN_TIMEOUT', info, None
    def extract(mod):
        return [kk for kk, f in F.items() if is_true(mod.eval(f, model_completion=True))]
    mod = s.model(); best = extract(mod)
    if outs and len(best) > kcap: raise RuntimeError(f'internal error: model has {len(best)} faults, bound is {kcap} (at-most-k encoding inconsistent)')
    t0 = time.time()
    while minimize and best:
        if outs:
            if s.check(*atmost(len(best) - 1)) == sat: mod = s.model(); best = extract(mod)
            else: break
            continue
        s.push(); s.add(PbLe([(f, 1) for f in allf], len(best) - 1))
        if s.check() == sat:
            mod = s.model(); best = extract(mod); s.pop()
        else:
            s.pop(); break
    info['minimize_s'] = round(time.time() - t0, 3)
    atk = {p: mod.eval(v, model_completion=True).as_long() for p, v in inputs.items()}
    return 'ATTACK_FOUND', info, dict(inputs=atk, faults=sorted(best, key=lambda x: (x[0], x[1])))


def honest_boots(nl, N, **kw):
    """Sanity: fault-free run with the legitimate key reaches the goal."""
    kw = dict(kw); key = kw.get('key', 0xC3)
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
        kind = 'flip-flop Q' if b in nl.dq else 'gate output'
        gt = nl.drivers[b][1].strip('$_') if b in nl.drivers else 'DFF'
        sup = support(nl, b)
        n_in = len(sup & in_bits)
        reach = forward_reach(nl, b, goal_bits, N)
        nets.append(dict(net=nm, cycle=t, kind=kind, gate=gt, input_bits_in_fanin_cone=n_in,
                         goal_bits_reached=len(reach), goal_bits_total=len(goal_bits)))
    ncyc = len({t for t, _ in faults})
    if k_found == 1:
        n = nets[0]
        if n['kind'] == 'gate output' and n['goal_bits_reached'] >= len(goal_bits) // 2 and n['input_bits_in_fanin_cone'] > 1:
            summary = (f"SINGLE POINT OF FAILURE: one {n['gate']} gate output, net `{n['net']}`, combines {n['input_bits_in_fanin_cone']} "
                       f"input bits of `{attack_in}` (the redundant checks converge here) and alone drives {n['goal_bits_reached']} of "
                       f"{n['goal_bits_total']} bits of `{goal_out}`. Flipping it for ONE cycle (cycle {n['cycle']}) makes a wrong "
                       f"`{attack_in}` look valid, even though the checks upstream are duplicated.")
            fix = ("Do not let any one net decide. Split the decision across independent bits: give each redundant check its own "
                   "disjoint group of result-word bits (no shared AND/OR of the checks), use a sparse result encoding with Hamming "
                   "distance > fault budget, and make the final accept require all groups to agree bit-by-bit.")
        elif n['kind'] == 'flip-flop Q':
            summary = (f"SINGLE POINT OF FAILURE: the state register bit `{n['net']}` can be flipped for one cycle (cycle {n['cycle']}) "
                       f"and the state/output word then reads as the accept value.")
            fix = ("Encode state with Hamming distance greater than the fault budget (e.g. sparse one-hot-ish codes), add a parity/redundant "
                   "shadow register compared every cycle, and make illegal codes latch a sticky FAIL state.")
        else:
            summary = (f"SINGLE POINT OF FAILURE: gate output `{n['net']}` ({n['gate']}), flipped for one cycle at cycle {n['cycle']}, "
                       f"reaches {n['goal_bits_reached']}/{n['goal_bits_total']} bits of `{goal_out}` and is enough to reach the accept value.")
            fix = ("Duplicate the logic that feeds this net and keep the copies independent (no shared gate), then compare/decide per bit "
                   "instead of through one net.")
    else:
        names = ', '.join(f"`{n['net']}`@{n['cycle']}" for n in nets)
        nn = len({n['net'] for n in nets})
        summary = (f"MINIMUM ATTACK COST = {k_found} faults ({names}). No single net decides; the attacker needs {k_found} "
                   f"coordinated single-cycle flips (spanning {ncyc} distinct cycle(s)). Faults at {nn} distinct nets (names listed); "
                   "this output does not classify whether they sit on independent copies or on a shared decision path; "
                   "see the consumer-bits and ledger docs.")
        fix = (f"Raise the cost above the attacker's fault budget (currently {k_found}); inspect the listed nets in the netlist to see "
               "where they sit, then re-run the tool at k=%d." % (k_found))
    return dict(summary=summary, fix_pattern=fix, fault_details=nets)


# ---------------------------------------------------------------- CLI
_TOP_RE = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]{0,254}\Z')
_BAD_PATH_CH = re.compile(r'[\x00-\x1f\x7f"\'`;\\#]')

def _check_synth_args(verilog, top, out):
    """H3: same rules as product/src runner.check_top / check_path (copied): TOP is a plain identifier, file names have no control
    characters/quotes/';'/backslash/'#' and do not start with '-'. scripts/synth.sh repeats the check."""
    if not isinstance(top, str) or not _TOP_RE.match(top):
        raise NetlistError(f'top {top!r} is not a plain module identifier ([A-Za-z_$][A-Za-z0-9_$]*)')
    for what, p in (('verilog', verilog), ('output', out)):
        if not isinstance(p, str) or not p or p.startswith('-') or _BAD_PATH_CH.search(p):
            raise NetlistError(f'{what} path {p!r} is not accepted (empty, leading "-", control characters, quotes, backtick, ";", backslash or "#")')

def synth(verilog, top, out, flow='plain'):
    _check_synth_args(verilog, top, out)
    r = subprocess.run(['sh', os.path.join(HERE, 'synth.sh'), verilog, top, out, flow], capture_output=True, text=True)
    if r.returncode: raise NetlistError('synthesis failed:\n' + r.stderr[-2000:])

EXIT_INPUT_ERROR, EXIT_INTERNAL_ERROR = 3, 4

def _safe(s):
    """Escape control/bidi/ANSI characters in text derived from netlists before printing to a terminal."""
    return ''.join(c if (c.isprintable() and c not in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069') else c.encode('unicode_escape').decode('ascii') if ord(c) < 0x10000 else '\\U%08x' % ord(c) for c in s)

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

def run_check(verilog, top, k, N, out=None, reduce='full', goal_out='boot_word', goal_value=0x96, attack_in='sig',
              key=0xC3, timeout_ms=0, workdir=None, label='MEASURED', flow='plain', amk=None):
    if k < 0: raise NetlistError(f'--k must be >= 0 (got {k})')
    if N < 1: raise NetlistError(f'--cycles must be >= 1 (got {N}); 0 cycles would give a vacuous NO_ATTACK')
    if goal_value < 0 or key < 0: raise NetlistError('--goal-value and --key must be non-negative')
    if not os.path.isfile(verilog): raise NetlistError(f'no such file: {verilog}')
    workdir = workdir or os.path.join(os.path.dirname(HERE), 'results', 'work')
    os.makedirs(workdir, exist_ok=True)
    jpath = os.path.join(workdir, f'{top}.json' if flow == 'plain' else f'{top}_{flow}.json')
    t0 = time.time()
    if verilog.endswith('.json'):   # pre-synthesized Yosys JSON netlist (e.g. reference/spike_netlists)
        jpath = verilog; flow = 'given-netlist'
    else:
        synth(verilog, top, jpath, flow)
    t_syn = time.time() - t0
    nl = Netlist(jpath, top)
    for pn, role in ((goal_out, 'output'), (attack_in, 'input')):
        if pn not in nl.ports or nl.ports[pn].get('direction') != role:
            raise NetlistError(f'{pn!r} is not an {role} port of {top}')
    if goal_value >> len(nl.ports[goal_out]['bits']):
        raise NetlistError(f'--goal-value 0x{goal_value:X} does not fit the {len(nl.ports[goal_out]["bits"])}-bit port {goal_out!r}')
    if key >> len(nl.ports[attack_in]['bits']):
        raise NetlistError(f'--key 0x{key:X} does not fit the {len(nl.ports[attack_in]["bits"])}-bit port {attack_in!r}')
    kw = dict(goal_out=goal_out, goal_value=goal_value, attack_in=attack_in, key=key, reduce=reduce)
    t0 = time.time()
    verdict, info, res = solve(nl, N, k, timeout_ms=timeout_ms, amk=amk, **kw)
    wall = time.time() - t0
    out_d = dict(label=label, tool='glitchsat.py', design=os.path.relpath(verilog, os.path.dirname(HERE)) if os.path.isabs(verilog) else verilog,
                 design_sha256_16=sha(verilog), top=top, synth_flow=flow, verdict=verdict,
                 bound=dict(max_faults=k, cycles=N, fault_model='single-cycle bit flip of any gate output or flop Q',
                            attacker_input=f'`{attack_in}` free, held constant, != key 0x{key:02X}',
                            goal=f'{goal_out} == 0x{goal_value:X} at some cycle < {N}'),
                 note=NOTE.format(k=k, n=N), netlist=nl.stats(),
                 honest_key_boots_fault_free=honest_boots(nl, N, **kw),
                 model=info, runtime_s=dict(synth=round(t_syn, 3), solve_and_minimize=round(wall, 3)),
                 netlist_json=os.path.relpath(jpath, os.path.dirname(HERE)))
    if res:
        faults = [dict(net=nl.names.get(b, str(b)), net_id=b, cycle=t, kind='flop_Q' if b in nl.dq else 'gate_output') for t, b in res['faults']]
        out_d['min_faults'] = len(faults)
        out_d['faults'] = faults
        out_d['attacker_input'] = {p: f'0x{v:02X}' if v < 256 else hex(v) for p, v in res['inputs'].items()}
        out_d['attacker_input_raw'] = res['inputs']
        out_d['explanation'] = explain(nl, res, len(faults), N, goal_out, attack_in)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        json.dump(out_d, open(out, 'w'), indent=2)
    return out_d


def main():
    ap = argparse.ArgumentParser(prog='glitchsat.py',
        description='GlitchSAT engine: find the minimum number of modelled single-cycle bit flips that make a gate-level '
                    'netlist accept a wrong input, within a fixed number of clock cycles. Results are bounded, not proofs.',
        epilog='exit codes: 0 verdict printed (NO_ATTACK_UP_TO_BOUND or ATTACK_FOUND: read the text); 2 solver unknown/timeout; '
               '3 usage/input/netlist error (including z3 not installed); 4 internal error. '
               'Example: python3 scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6')
    ap.add_argument('--version', action='version', version=f'GlitchSAT engine (scripts/glitchsat.py) {__version__}')
    sp = ap.add_subparsers(dest='cmd', required=True, metavar='COMMAND')
    c = sp.add_parser('check', help='bounded attack search: smallest number of flips (up to --k) that reaches the goal',
                      description='Bounded attack search on one netlist. Faults are modelled single-cycle bit flips of gate outputs '
                                  'and flip-flop outputs; the attacker input is free, held constant and never equal to --key.')
    c.add_argument('verilog', metavar='NETLIST', help='Yosys JSON netlist (.json, e.g. reference/spike_netlists/v2.json) or Verilog (.v; needs yosys on PATH)')
    c.add_argument('--top', required=True, help='name of the top module inside NETLIST (e.g. v2)')
    c.add_argument('--k', type=int, required=True, help='largest number of flips the attacker may use (the fault budget)')
    c.add_argument('--cycles', type=int, required=True, help='number of clock cycles to unroll; the goal must be reached before this many cycles')
    c.add_argument('--out', metavar='FILE', help='also write the full result as JSON to FILE')
    c.add_argument('--reduce', choices=['none', 'coi', 'full'], default='full',
                   help='which fault sites to model: none = every site; coi = only sites in the goal\'s cone of influence; '
                        'full = coi plus a timing filter (a flip must be able to reach the goal in time). Default full')
    c.add_argument('--goal-out', default='boot_word', metavar='PORT', help='output port the attacker wants to control (default boot_word)')
    c.add_argument('--goal-value', type=lambda x: int(x, 0), default=0x96, metavar='N', help='value the goal port must show (default 0x96, the accept word)')
    c.add_argument('--attack-input', default='sig', metavar='PORT', help='input port the attacker chooses (default sig)')
    c.add_argument('--key', type=lambda x: int(x, 0), default=0xC3, metavar='N', help='the legitimate key; the attacker input must differ from it (default 0xC3)')
    c.add_argument('--timeout-ms', type=int, default=0, metavar='MS', help='solver time limit in milliseconds; 0 = no limit (default). A timeout gives exit 2, never "no attack"')
    c.add_argument('--amk', choices=['counter', 'legacy'], default=None,
                   help='how "at most k flips" is encoded for the solver: counter (default; sequential counter with assumptions) '
                        'or legacy (pseudo-Boolean PbLe constraint)')
    c.add_argument('--flow', choices=['plain', 'opt'], default='plain', help='Yosys synthesis flow for Verilog input (see scripts/synth.sh); ignored for .json netlists')
    a = ap.parse_args()
    if _Z3_IMPORT_ERROR is not None:
        print(f'error: {Z3_MISSING}', file=sys.stderr); sys.exit(EXIT_INPUT_ERROR)
    try:
        r = run_check(a.verilog, a.top, a.k, a.cycles, a.out, a.reduce, a.goal_out, a.goal_value, a.attack_input, a.key, a.timeout_ms, flow=a.flow, amk=a.amk)
    except NetlistError as e:   # distinct, loud failure (exit 3); 0 = verdict printed (attack or no attack, see text), 2 = solver unknown
        print(f'error: {_safe(str(e))}', file=sys.stderr); sys.exit(EXIT_INPUT_ERROR)
    except (RecursionError, KeyError, IndexError, TypeError) as e:
        print(f'internal error ({type(e).__name__}: {_safe(str(e))}); no verdict', file=sys.stderr); sys.exit(EXIT_INTERNAL_ERROR)
    print(f"{a.top}: {r['verdict']}  (k<={a.k}, cycles={a.cycles}, reduce={a.reduce})  solve={r['runtime_s']['solve_and_minimize']}s")
    if 'faults' in r:
        print('  min faults:', r['min_faults'], _safe(str([(f['net'], f['cycle']) for f in r['faults']])), 'input', r['attacker_input'])
        print('  ' + r['explanation']['summary']); print('  FIX: ' + r['explanation']['fix_pattern'])
    print('  ' + r['note'])
    sys.exit(0 if r['verdict'] in ('NO_ATTACK_UP_TO_BOUND', 'ATTACK_FOUND') else 2)

if __name__ == '__main__':
    main()
