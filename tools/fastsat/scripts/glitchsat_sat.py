#!/usr/bin/env python3
"""glitchsat_sat: direct-CNF SAT backend for the GlitchSAT bounded fault-injection check.

Same question as scripts/glitchsat.py (`check`): what is the smallest number of modelled single-cycle bit flips
(gate outputs and flop Q, at most K over cycles 0..N-1) that makes a goal output port show a goal value at some
cycle < N while the attacker input (free, constant) differs from the key?  Verdicts are BOUNDED exactly as there.

Differences from the z3 engine are in HOW the question is solved, not in WHAT is asked:
  * the unrolled circuit is written straight to CNF (Tseitin per gate, constant folding, structural hashing),
  * "at most j flips" is a totalizer (default) or a sequential counter whose outputs are used as solver
    assumptions, so one solver instance answers every budget j = 0..K,
  * fault sites that are provably dominated by another site are not given a variable (fault collapsing; --no-collapse
    turns this off),
  * the CNF is solved by PySAT (CaDiCaL/Glucose/...), by an external DIMACS solver binary, or by the bundled
    pure-Python CDCL (minicdcl.py) when nothing else is installed,
  * every ATTACK_FOUND witness is replayed on a separate gate-level simulator before it is reported.

The netlist parser, the goal/attacker/key semantics, the explanation text and the NOTE are imported from
scripts/glitchsat.py (which imports z3 lazily; z3 is NOT needed by this file).
"""
import argparse, json, os, sys, time, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_engine_dir():
    """Directory that holds scripts/glitchsat.py. Order: $GLITCHSAT_ROOT/scripts, then <repo>/scripts for this file at
    <repo>/ext/fastsat/scripts/, then this directory."""
    cands = []
    if os.environ.get('GLITCHSAT_ROOT'):
        cands.append(os.path.join(os.environ['GLITCHSAT_ROOT'], 'scripts'))
    cands.append(os.path.normpath(os.path.join(HERE, '..', '..', '..', 'scripts')))
    cands.append(HERE)
    for c in cands:
        if os.path.isfile(os.path.join(c, 'glitchsat.py')):
            return c
    raise ImportError('scripts/glitchsat.py not found; set GLITCHSAT_ROOT to the repository root (tried: %s)' % ', '.join(cands))


_ENGINE_DIR = _find_engine_dir()
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import glitchsat as gs          # noqa: E402  (z3 import inside is optional)
import minicdcl                 # noqa: E402

NetlistError = gs.NetlistError
__version__ = '0.1.0'
REPO_ROOT = os.path.dirname(_ENGINE_DIR)
T_, F_ = 1, -1                   # CNF variable 1 is the constant TRUE (unit clause [1]); literal -1 is FALSE


# ---------------------------------------------------------------- CNF encoder
class Encoding:
    """CNF of the unrolled faulty circuit. See encode()."""

    def __init__(self):
        self.nvars = 1
        self.clauses = [[1]]
        self.F = {}                # (t, net) -> fault variable (only sites that got a variable)
        self.inputs = {}           # port -> list of input variables (LSB first)
        self.node = []             # per cycle: net -> literal of the (post-fault) net value
        self.fault_order = []      # fault variables in (cycle, topological) order: leaves of the cardinality network
        self.card = None           # (kind, outs) after add_cardinality
        self.info = {}
        self._hash = {}

    def new_var(self):
        self.nvars += 1
        return self.nvars

    def add(self, c):
        self.clauses.append(c)

    # -- gates (literals may be the constants T_/F_). `f` is None or a fault variable: result = gate XOR f.
    def g_xor(self, a, b, f=None, relax=False):
        if f is not None:
            r = self.g_xor(a, b)
            return self.g_xor(r, f)                      # XOR with the fault variable is itself an XOR gate
        if a == T_: return -b
        if a == F_: return b
        if b == T_: return -a
        if b == F_: return a
        if a == b: return F_
        if a == -b: return T_
        neg = (a < 0) != (b < 0)
        a, b = abs(a), abs(b)
        if a > b: a, b = b, a
        key = ('x', a, b)
        y = self._hash.get(key)
        if y is None:
            y = self.new_var(); self._hash[key] = y
            self.clauses += [[-y, a, b], [-y, -a, -b], [y, -a, b], [y, a, -b]]
        return -y if neg else y

    def g_and(self, a, b, f=None, relax=False):
        r = None
        if a == F_ or b == F_ or a == -b: r = F_
        elif a == T_: r = b
        elif b == T_ or a == b: r = a
        else:
            if a > b: a, b = b, a
            key = ('a', a, b)
            r = self._hash.get(key)
            if r is None:
                if f is None:
                    y = self.new_var(); self._hash[key] = y
                    self.clauses += [[-y, a], [-y, b], [y, -a, -b]]
                    return y
                # merged gate + fault: f=0 -> y = a&b ; f=1 -> y = not(a&b)   (relax: f=1 leaves y unconstrained)
                y = self.new_var()
                self.clauses += [[f, -y, a], [f, -y, b], [f, y, -a, -b]]
                if not relax:
                    self.clauses += [[-f, y, a], [-f, y, b], [-f, -y, -a, -b]]
                return y
        return r if f is None else self.g_xor(r, f)

    def g_or(self, a, b, f=None, relax=False):
        return -self.g_and(-a, -b, f, relax)             # not(and(not a, not b) xor f) = or(a, b) xor f

    def g_mux(self, s, b, a, f=None, relax=False):
        """s ? b : a"""
        if s == T_: r = b
        elif s == F_: r = a
        elif a == b: r = a
        elif a == -b: return self.g_xor(s, a, f, relax)
        elif b == T_ or b == s: return self.g_or(s, a, f, relax)
        elif b == F_ or b == -s: return self.g_and(-s, a, f, relax)
        elif a == T_ or a == -s: return self.g_or(-s, b, f, relax)
        elif a == F_ or a == s: return self.g_and(s, b, f, relax)
        else:
            key = ('m', s, b, a)
            r = self._hash.get(key)
            if r is None:
                y = self.new_var()
                base = [[-s, -b, y], [-s, b, -y], [s, -a, y], [s, a, -y], [-a, -b, y], [a, b, -y]]
                if f is None:
                    self._hash[key] = y
                    self.clauses += base
                    return y
                self.clauses += [c + [f] for c in base]
                if not relax:
                    self.clauses += [[-l if abs(l) == y else l for l in c] + [-f] for c in base]
                return y
        return r if f is None else self.g_xor(r, f)

    def stats(self):
        nl = sum(map(len, self.clauses))
        return dict(vars=self.nvars, clauses=len(self.clauses), literals=nl)

    def to_dimacs(self, extra_units=()):
        out = ['p cnf %d %d' % (self.nvars, len(self.clauses) + len(extra_units))]
        out += [' '.join(map(str, c)) + ' 0' for c in self.clauses]
        out += ['%d 0' % u for u in extra_units]
        return '\n'.join(out) + '\n'


def _input_bits(nl):
    """net -> (port, index) for the model's free inputs: every input port except `clk` (as glitchsat.build)."""
    inbit = {}
    for p, v in nl.ports.items():
        if v['direction'] == 'input' and p != 'clk':
            for i, b in enumerate(v['bits']):
                inbit[b] = (p, i)
    return inbit


def _validate_and_order(nl, goal_bits, inbit):
    """Walk the logic cone of every flop D and every goal bit (what glitchsat.build evaluates each cycle), raise the
    same NetlistError classes for x/z constants, undriven nets and unsupported cells, and return the gates of that cone
    in topological order (fan-ins first)."""
    order = []; done = set()
    roots = list(nl.dq.values()) + list(goal_bits)
    qset = set(nl.qs)
    for root in roots:
        stack = [root]
        while stack:
            b = stack[-1]
            if b == '0' or b == '1':
                stack.pop(); continue
            if b == 'x' or b == 'z':
                raise NetlistError("constant x/z (unknown) bit in the logic cone of the goal or flop inputs; refusing (would be treated as 0)")
            if b in done or b in inbit or b in qset:
                stack.pop(); continue
            if b not in nl.drivers:
                raise NetlistError(f"net {nl.names.get(b, b)!r} (id {b}) is used but has no driver and is not an input port (undriven)")
            _, ty, con = nl.drivers[b]
            if ty not in gs._PIN_ORDER:
                raise NetlistError('unsupported cell ' + str(ty))
            pend = [con[p][0] for p in gs._PIN_ORDER[ty]
                    if con[p][0] not in ('0', '1') and con[p][0] not in done and con[p][0] not in inbit and con[p][0] not in qset]
            if pend:
                stack.extend(reversed(pend)); continue
            done.add(b); order.append(b); stack.pop()
    return order


def dominated_sites(nl, N, goal_bits, dist):
    """Fault collapsing. Returns {(t, b): (t2, h)}: a flip of site b at cycle t is dominated by a flip of site h at
    cycle t2 and needs no fault variable.

    A node (t, x) is *time-relevant* when x is in the goal cone and t + dist[x] <= N-1 (otherwise no value of x at
    cycle t can reach a goal bit before the horizon). Site (t, b) is dominated when b is not itself a goal bit and
    exactly ONE time-relevant cell reads b at cycle t:
      - a gate h (reads b on one or more pins):  dominator (t, h);
      - a flop with D = b and output q:          dominator (t+1, q).
    Soundness (README section 4): the flip of b can change the goal only through that one reader; its whole effect on
    the reader's output is "flipped" or "not flipped", which is what the dominator's own fault (or no fault) does.
    """
    goal_set = {b for b in goal_bits if isinstance(b, int)}
    readers = {}                                   # net -> list of ('g', h) / ('f', q), one entry per reading CELL
    for h in nl.drivers:
        if h in dist:
            for fi in set(x for x in nl.fanins(h) if isinstance(x, int)):
                readers.setdefault(fi, []).append(('g', h))
    for q, d in nl.dq.items():
        if q in dist and isinstance(d, int):
            readers.setdefault(d, []).append(('f', q))
    dom = {}
    sites = [b for b in list(nl.qs) + list(nl.drivers) if b in dist and b not in goal_set]
    for b in sites:
        rs = readers.get(b, [])
        if not rs:
            continue
        for t in range(N):
            if t + dist[b] > N - 1:
                break
            live = [(k, h) for k, h in rs if (t + dist[h] <= N - 1 if k == 'g' else t + 1 + dist[h] <= N - 1)]
            if len(live) == 1:
                k, h = live[0]
                dom[(t, b)] = (t, h) if k == 'g' else (t + 1, h)
    return dom


def encode(nl, N, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, reduce='full', bad_only=True,
           fixed_in=None, collapse=True, fault_enc='xor', faults=True):
    """Build the CNF. Mirrors glitchsat.build(): same ports, inputs, flop init, fault sites, goal and input constraints.

    reduce: which sites the MODEL allows to be flipped ('none' every site, 'coi' goal cone, 'full' cone + timing), as in
    the z3 engine. A site that is not time-relevant cannot change any goal bit before the horizon, so it never gets a
    CNF variable (it is fixed to "no flip"); this changes no verdict and no minimum (README section 4).
    collapse: drop dominated sites (dominated_sites()).   fault_enc: 'xor' (exact flip) or 'relax' (flip variable
    frees the gate output; same verdicts and minimum, witness is normalised afterwards).
    faults=False: no fault variables at all (used for the fault-free sanity run)."""
    if reduce not in ('none', 'coi', 'full'): raise ValueError(f'reduce must be none, coi or full, not {reduce!r}')
    if fault_enc not in ('xor', 'relax'): raise ValueError(f'fault_enc must be xor or relax, not {fault_enc!r}')
    ports = nl.ports
    if goal_out not in ports or ports[goal_out].get('direction') != 'output':
        raise NetlistError(f"goal output {goal_out!r} is not an output port (outputs: {[p for p, v in ports.items() if v.get('direction') == 'output']})")
    if attack_in not in ports or ports[attack_in].get('direction') != 'input':
        raise NetlistError(f"attacker input {attack_in!r} is not an input port (inputs: {[p for p, v in ports.items() if v.get('direction') == 'input']})")
    goal_bits = ports[goal_out]['bits']
    inbit = _input_bits(nl)
    order = _validate_and_order(nl, goal_bits, inbit)
    dist = nl.coi_and_dist(goal_bits)
    allsites = list(nl.qs) + list(nl.drivers.keys())
    if reduce == 'none': n_model = len(allsites) * N
    elif reduce == 'coi': n_model = sum(1 for b in allsites if b in dist) * N
    else: n_model = sum(max(0, N - dist[b]) for b in allsites if b in dist)
    e = Encoding()
    for p, v in ports.items():
        if v['direction'] == 'input' and p != 'clk':
            e.inputs[p] = [e.new_var() for _ in v['bits']]
    inlit = {b: e.inputs[p][i] for b, (p, i) in inbit.items()}
    dom = dominated_sites(nl, N, goal_bits, dist) if (collapse and faults) else {}
    relax = fault_enc == 'relax'
    rel_order = [b for b in order if b in dist]
    qs_rel = [q for q in nl.qs if q in dist]
    n_rel_sites = 0
    state = {q: (T_ if nl.init[q] else F_) for q in qs_rel}
    hits = []
    for t in range(N):
        val = {}
        slack = N - 1 - t                           # node (t, b) is time-relevant iff dist[b] <= slack

        def lit(b):
            if b == '0': return F_
            if b == '1': return T_
            r = inlit.get(b)
            return val[b] if r is None else r

        def fvar(b):
            nonlocal n_rel_sites
            n_rel_sites += 1
            if not faults or (t, b) in dom:
                return None
            f = e.new_var(); e.F[(t, b)] = f; e.fault_order.append(f)
            return f
        for q in qs_rel:
            if dist[q] > slack:
                continue
            f = fvar(q)
            val[q] = state[q] if f is None else e.g_xor(state[q], f)
        for b in rel_order:
            if dist[b] > slack:
                continue
            _, ty, con = nl.drivers[b]
            f = fvar(b)
            if ty == '$_AND_': v = e.g_and(lit(con['A'][0]), lit(con['B'][0]), f, relax)
            elif ty == '$_OR_': v = e.g_or(lit(con['A'][0]), lit(con['B'][0]), f, relax)
            elif ty == '$_XOR_': v = e.g_xor(lit(con['A'][0]), lit(con['B'][0]), f, relax)
            elif ty == '$_NOT_':
                v = -lit(con['A'][0])
                if f is not None: v = e.g_xor(v, f)
            else: v = e.g_mux(lit(con['S'][0]), lit(con['B'][0]), lit(con['A'][0]), f, relax)
            val[b] = v
        # goal at cycle t: h_t -> every goal bit has its goal value (one direction is enough: h_t only occurs
        # positively, in the clause OR_t h_t)
        want = [lit(b) if (goal_value >> i) & 1 else -lit(b) for i, b in enumerate(goal_bits)]
        if F_ in want:
            pass                                     # goal impossible at this cycle
        else:
            want = [w for w in want if w != T_]
            if not want: hits.append(T_)
            elif len(want) == 1: hits.append(want[0])
            else:
                h = e.new_var()
                for w in want: e.add([-h, w])
                hits.append(h)
        if t + 1 < N:
            state = {q: lit(nl.dq[q]) for q in qs_rel if dist[q] <= slack - 1}
        e.node.append(val)
    if T_ not in hits:
        e.add(sorted(set(hits)) or [F_])             # [FALSE] when the goal is unreachable by construction
    width = len(ports[attack_in]['bits'])
    ain = e.inputs[attack_in]
    if bad_only:
        e.add([-ain[i] if (key >> i) & 1 else ain[i] for i in range(width)])
    if fixed_in is not None:
        for i in range(width):
            e.add([ain[i] if (fixed_in >> i) & 1 else -ain[i]])
    e.info = dict(sites_total=len(allsites) * N, sites_modelled=n_model if faults else 0, reduce=reduce,
                  sites_time_relevant=n_rel_sites, fault_vars=len(e.F), sites_collapsed=len(dom),
                  collapse=bool(collapse), fault_enc=fault_enc)
    e.dom = dom
    return e


# ---------------------------------------------------------------- cardinality (at most j of the fault variables)
def totalizer(e, xs, kmax):
    """Totalizer (Bailleux-Boufkhad) truncated at kmax+1, one direction only: outs[j-1] is forced TRUE whenever at least
    j of xs are true (j = 1..min(len(xs), kmax+1)). Assuming -outs[j] therefore means "at most j"."""
    cap = kmax + 1
    layer = [[x] for x in xs]
    while len(layer) > 1:
        nxt = []
        for i in range(0, len(layer) - 1, 2):
            a, b = layer[i], layer[i + 1]
            m = min(len(a) + len(b), cap)
            o = [e.new_var() for _ in range(m)]
            for ia in range(len(a) + 1):
                for ib in range(len(b) + 1):
                    s = ia + ib
                    if s == 0 or s > m: continue
                    c = [o[s - 1]]
                    if ia: c.append(-a[ia - 1])
                    if ib: c.append(-b[ib - 1])
                    e.add(c)
            nxt.append(o)
        if len(layer) & 1:
            nxt.append(layer[-1])
        layer = nxt
    return layer[0] if layer else []


def seqcounter(e, xs, kmax):
    """Sequential counter (Sinz), one direction, same contract as totalizer(). Same construction as
    glitchsat.seq_counter."""
    cap = kmax + 1
    prev = []
    for x in xs:
        m = min(len(prev) + 1, cap)
        cur = [e.new_var() for _ in range(m)]
        for j in range(m):
            if j < len(prev): e.add([-prev[j], cur[j]])
            if j == 0: e.add([-x, cur[0]])
            else: e.add([-x, -prev[j - 1], cur[j]])
        prev = cur
    return prev


def add_cardinality(e, kmax, card='totalizer'):
    if card not in ('totalizer', 'seqcounter'): raise ValueError(f'card must be totalizer or seqcounter, not {card!r}')
    outs = (totalizer if card == 'totalizer' else seqcounter)(e, e.fault_order, kmax)
    e.card = (card, outs, kmax)
    return outs


def atmost(e, j):
    """Assumption literals that mean "at most j fault variables are true" (j <= kmax given to add_cardinality)."""
    _, outs, kmax = e.card
    if j < 0: return [F_]
    if j > kmax: raise ValueError('budget above the built cardinality bound')
    return [-outs[j]] if j < len(outs) else []


# ---------------------------------------------------------------- solver backends
class BackendError(NetlistError):
    """Requested solver backend is not available (CLI exit 3, like a missing z3 in the z3 engine)."""


class PyBackend:
    """Bundled pure-Python CDCL (minicdcl). Always available; slow."""
    def __init__(self, e):
        self.name = 'minicdcl'
        self.s = minicdcl.Solver(e.nvars)
        for c in e.clauses: self.s.add_clause(c)
        self.nvars = e.nvars
    def solve(self, assumptions, deadline=None):
        return self.s.solve(assumptions, deadline=deadline)
    def model(self):
        return self.s.model()
    def close(self): pass


def _pysat_name(name):
    """Canonical PySAT solver name. 'cadical' picks the newest CaDiCaL the installed PySAT offers."""
    try:
        from pysat.solvers import SolverNames
    except ImportError as ex:
        raise BackendError('python-sat is not installed: pip install python-sat   (or use --backend py)') from ex
    known = {a: getattr(SolverNames, a) for a in dir(SolverNames) if not a.startswith('_') and isinstance(getattr(SolverNames, a), (tuple, list))}
    if name in ('cadical', 'auto'):
        for cand in ('cadical195', 'cadical153', 'cadical103'):
            if cand in known: return cand
        if name == 'auto':
            for cand in ('glucose42', 'glucose4', 'glucose3', 'minisat22'):
                if cand in known: return cand
        raise BackendError(f'this PySAT has no CaDiCaL (solvers: {sorted(known)})')
    for canon, aliases in known.items():
        if name == canon or name in aliases: return canon
    raise BackendError(f'PySAT has no solver {name!r} (solvers: {sorted(known)})')


class PySATBackend:
    """PySAT (pip install python-sat). One incremental solver object; budgets are passed as assumptions.
    No in-process time limit is used (not every PySAT solver supports interruption); a time limit is enforced by
    running the whole query in a child process (see _solve_with_timeout)."""
    def __init__(self, e, name='cadical'):
        self.name = _pysat_name(name)      # raises BackendError when python-sat is missing
        from pysat.solvers import Solver
        self.s = Solver(name=self.name, bootstrap_with=e.clauses)
        self.nvars = e.nvars
    def solve(self, assumptions, deadline=None):
        return bool(self.s.solve(assumptions=list(assumptions)))
    def model(self):
        m = [None] + [False] * self.nvars
        for l in self.s.get_model() or []:
            if 0 < l <= self.nvars: m[l] = True
        return m
    def close(self):
        try: self.s.delete()
        except Exception: pass


class DimacsBackend:
    """External solver binary that reads DIMACS and prints SAT-competition output ('s SATISFIABLE' + 'v ...' lines):
    kissat, cadical, cryptominisat5 and similar. Not incremental: one process per budget, assumptions become unit
    clauses."""
    def __init__(self, e, binary):
        path = shutil.which(binary)
        if not path:
            raise BackendError(f'solver binary {binary!r} not found on PATH')
        self.bin = path; self.name = os.path.basename(binary); self.e = e; self.nvars = e.nvars; self._m = None
        self.args = os.environ.get('GLITCHSAT_DIMACS_ARGS', '').split()
        # CaDiCaL >= 2 prints only the literals that occur in the formula unless --modelalllits=true is given.
        if 'cadical' in self.name.lower() and not any('modelalllits' in a for a in self.args):
            try:
                h = subprocess.run([self.bin, '--help'], capture_output=True, text=True, timeout=10)
                if 'modelalllits' in (h.stdout + h.stderr):
                    self.args.append('--modelalllits=true')
            except (OSError, subprocess.TimeoutExpired):
                pass
    def solve(self, assumptions, deadline=None):
        self._m = None
        fd, path = tempfile.mkstemp(suffix='.cnf', prefix='glitchsat_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(self.e.to_dimacs(list(assumptions)))
            to = None if deadline is None else max(0.01, deadline - time.time())
            try:
                r = subprocess.run([self.bin] + self.args + [path], capture_output=True, text=True, timeout=to)
            except subprocess.TimeoutExpired:
                return None
        finally:
            os.unlink(path)
        status = None; lits = []
        for line in r.stdout.splitlines():
            if line.startswith('s '): status = line[2:].strip()
            elif line.startswith('v '): lits += [int(x) for x in line[2:].split()]
        if status == 'UNSATISFIABLE': return False
        if status == 'SATISFIABLE':
            m = [None] + [False] * self.nvars
            for l in lits:
                if 0 < l <= self.nvars: m[l] = True
            self._m = m
            return True
        if status in (None, 'UNKNOWN') and r.returncode not in (10, 20):
            if status is None and r.returncode != 0:
                raise RuntimeError(f'solver {self.name} failed (exit {r.returncode}): {r.stderr[-300:]}')
            return None
        raise RuntimeError(f'solver {self.name}: cannot parse output (status {status!r}, exit {r.returncode})')
    def model(self): return self._m
    def close(self): pass


def backend_kind(backend):
    """'py', 'pysat' or 'dimacs' for a --backend value (auto: pysat when python-sat is importable, else py)."""
    if backend in ('py', 'minicdcl', 'builtin'): return 'py'
    if str(backend).startswith('dimacs:'): return 'dimacs'
    if backend in (None, 'auto'):
        try:
            import pysat.solvers   # noqa: F401
        except ImportError:
            return 'py'
    return 'pysat'


def make_backend(e, backend='auto'):
    """backend: auto | py | pysat:<name> | <pysat name> | dimacs:<binary>.  auto = PySAT CaDiCaL when python-sat is
    importable, else the bundled pure-Python solver."""
    if backend in (None, 'auto'):
        try:
            import pysat.solvers   # noqa: F401
        except ImportError:
            return PyBackend(e)
        return PySATBackend(e, 'auto')
    if backend in ('py', 'minicdcl', 'builtin'):
        return PyBackend(e)
    if backend.startswith('dimacs:'):
        return DimacsBackend(e, backend[7:])
    return PySATBackend(e, backend[6:] if backend.startswith('pysat:') else backend)


# ---------------------------------------------------------------- reference simulator (witness replay)
def simulate(nl, N, inputs, faults, goal_out):
    """Scalar gate-level simulation, written independently of the encoder. inputs: port -> int (constant over the
    run). faults: iterable of (cycle, net). Returns the goal port value at each cycle (None if a bit is x/z)."""
    fset = set(faults)
    inbit = _input_bits(nl)
    goal_bits = nl.ports[goal_out]['bits']
    order = _validate_and_order(nl, goal_bits, inbit)
    inval = {b: bool((inputs[p] >> i) & 1) for b, (p, i) in inbit.items()}
    state = {q: bool(nl.init[q]) for q in nl.qs}
    out = []
    for t in range(N):
        v = {}

        def g(b):
            if b == '0': return False
            if b == '1': return True
            if b in inval: return inval[b]
            return v[b]
        for q in nl.qs:
            v[q] = state[q] ^ ((t, q) in fset)
        for b in order:
            _, ty, con = nl.drivers[b]
            if ty == '$_AND_': r = g(con['A'][0]) and g(con['B'][0])
            elif ty == '$_OR_': r = g(con['A'][0]) or g(con['B'][0])
            elif ty == '$_XOR_': r = g(con['A'][0]) != g(con['B'][0])
            elif ty == '$_NOT_': r = not g(con['A'][0])
            else: r = g(con['B'][0]) if g(con['S'][0]) else g(con['A'][0])
            v[b] = bool(r) ^ ((t, b) in fset)
        out.append(sum(1 << i for i, b in enumerate(goal_bits) if g(b)))
        state = {q: g(d) for q, d in nl.dq.items()}
    return out


def _normalise_relaxed(nl, N, e, model, inputs, goal_out):
    """fault_enc='relax': a true fault variable only FREES the site, the model may leave the value unflipped. Return the
    sites whose model value really differs from the fault-free gate function of the model's own fan-in values."""
    cand = {kk for kk, f in e.F.items() if model[f]}
    real = []
    mval = lambda l: (model[l] if l > 0 else not model[-l])
    inbit = _input_bits(nl)
    order = _validate_and_order(nl, nl.ports[goal_out]['bits'], inbit)
    inval = {b: bool((inputs[p] >> i) & 1) for b, (p, i) in inbit.items()}
    state = {q: bool(nl.init[q]) for q in nl.qs}
    for t in range(N):
        v = {}

        def g(b):
            if b == '0': return False
            if b == '1': return True
            if b in inval: return inval[b]
            return v[b]

        def settle(b, r):
            if (t, b) in cand:
                m = mval(e.node[t][b])
                if m != r: real.append((t, b))
                r = m
            v[b] = r
        for q in nl.qs: settle(q, state[q])
        for b in order:
            _, ty, con = nl.drivers[b]
            if ty == '$_AND_': r = g(con['A'][0]) and g(con['B'][0])
            elif ty == '$_OR_': r = g(con['A'][0]) or g(con['B'][0])
            elif ty == '$_XOR_': r = g(con['A'][0]) != g(con['B'][0])
            elif ty == '$_NOT_': r = not g(con['A'][0])
            else: r = g(con['B'][0]) if g(con['S'][0]) else g(con['A'][0])
            settle(b, bool(r))
        state = {q: g(d) for q, d in nl.dq.items()}
    return real


# ---------------------------------------------------------------- solve
def _extract(nl, N, e, model, kw):
    inputs = {p: sum(1 << i for i, x in enumerate(vs) if model[x]) for p, vs in e.inputs.items()}
    if e.info['fault_enc'] == 'relax':
        faults = _normalise_relaxed(nl, N, e, model, inputs, kw['goal_out'])
    else:
        faults = [kk for kk, f in e.F.items() if model[f]]
    faults = sorted(faults, key=lambda x: (x[0], x[1]))
    # independent replay: the witness must reach the goal on the plain simulator, with a wrong attacker input
    tr = simulate(nl, N, inputs, faults, kw['goal_out'])
    if kw['goal_value'] not in tr:
        raise RuntimeError('internal error: SAT model does not replay on the reference simulator (encoding bug); no verdict')
    if kw.get('bad_only', True) and inputs[kw['attack_in']] == (kw['key'] & ((1 << len(e.inputs[kw['attack_in']])) - 1)):
        raise RuntimeError('internal error: SAT model uses the legitimate key; no verdict')
    return inputs, faults


def _search(nl, N, k, e, be, deadline, minimize, kw, info):
    """Same search order as glitchsat.solve: ask for <= k, then tighten to (found - 1) until UNSAT."""
    t0 = time.time()
    r = be.solve(atmost(e, k), deadline)
    info['solve_s'] = round(time.time() - t0, 3)
    if r is False: return 'NO_ATTACK_UP_TO_BOUND', None
    if r is None: return 'UNKNOWN_TIMEOUT', None
    inputs, best = _extract(nl, N, e, be.model(), kw)
    if len(best) > k:
        raise RuntimeError(f'internal error: model has {len(best)} faults, bound is {k} (at-most-k encoding inconsistent)')
    t0 = time.time()
    proved = not best
    while minimize and best:
        r = be.solve(atmost(e, len(best) - 1), deadline)
        if r is True:
            inputs, b2 = _extract(nl, N, e, be.model(), kw)
            if len(b2) >= len(best): raise RuntimeError('internal error: minimisation did not decrease the fault count')
            best = b2
            proved = not best
        else:
            proved = r is False                     # None = time limit: the witness stands, its minimality is NOT proved
            break
    info['minimize_s'] = round(time.time() - t0, 3)
    info['minimum_proved'] = bool(proved) if minimize else False
    return 'ATTACK_FOUND', dict(inputs=inputs, faults=best)


def _child(conn, nl, N, k, e, backend, minimize, kw):
    try:
        info = {}
        be = make_backend(e, backend)
        info['backend'] = be.name
        v, res = _search(nl, N, k, e, be, None, minimize, kw, info)
        conn.send(('ok', v, info, res))
    except BaseException as ex:        # report, the parent re-raises
        conn.send(('err', type(ex).__name__, str(ex), None))
    finally:
        conn.close()


def _solve_with_timeout(nl, N, k, e, backend, minimize, kw, timeout_s):
    """Run the search in a forked child and kill it at the time limit. Used for backends without an in-process limit
    (PySAT). A killed search is reported as UNKNOWN_TIMEOUT (never as "no attack")."""
    import multiprocessing as mp
    ctx = mp.get_context('fork')
    pc, cc = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_child, args=(cc, nl, N, k, e, backend, minimize, kw), daemon=True)
    p.start(); cc.close()
    try:
        if pc.poll(timeout_s):
            msg = pc.recv()
        else:
            msg = None
    except EOFError:
        msg = ('err', 'RuntimeError', 'solver process died without a result', None)
    finally:
        if p.is_alive(): p.kill()
        p.join()
    if msg is None:
        return 'UNKNOWN_TIMEOUT', {}, None
    if msg[0] == 'err':
        if msg[1] in ('BackendError', 'NetlistError'): raise BackendError(msg[2])
        raise RuntimeError(f'{msg[1]}: {msg[2]}')
    return msg[1], msg[2], msg[3]


def solve(nl, N, k, timeout_ms=0, minimize=True, backend='auto', card='totalizer', collapse=True, fault_enc='xor',
          dimacs_out=None, **kw):
    """Drop-in counterpart of glitchsat.solve(): returns (verdict, info, res) with res = dict(inputs, faults) or None."""
    kw.setdefault('goal_out', 'boot_word'); kw.setdefault('goal_value', 0x96)
    kw.setdefault('attack_in', 'sig'); kw.setdefault('key', 0xC3)
    t0 = time.time()
    e = encode(nl, N, collapse=collapse, fault_enc=fault_enc, **kw)
    add_cardinality(e, min(k, len(e.fault_order)), card)
    info = dict(e.info)
    info['build_s'] = round(time.time() - t0, 3)
    info['amk'] = card
    info['cnf'] = e.stats()
    if dimacs_out:
        with open(dimacs_out, 'w') as f:
            f.write('c glitchsat_sat %s  N=%d k<=%d  assumptions for "at most k": %s\n' % (__version__, N, k, atmost(e, min(k, e.card[2]))))
            f.write(e.to_dimacs(atmost(e, min(k, e.card[2]))))
    kk = min(k, e.card[2])
    if timeout_ms and backend_kind(backend) == 'pysat':
        t1 = time.time()
        verdict, cinfo, res = _solve_with_timeout(nl, N, kk, e, backend, minimize, kw, timeout_ms / 1000.0)
        cinfo.setdefault('solve_s', round(time.time() - t1, 3))
        cinfo.setdefault('backend', _pysat_name(backend[6:] if str(backend).startswith('pysat:') else (backend or 'auto')))
        info.update(cinfo)
    else:
        be = make_backend(e, backend)
        info['backend'] = be.name
        try:
            verdict, res = _search(nl, N, kk, e, be, time.time() + timeout_ms / 1000.0 if timeout_ms else None, minimize, kw, info)
        finally:
            be.close()
    return verdict, info, res


def _sweep_rows(nl, N, kmax, e, backend, timeout_ms, kw, emit):
    """Ascending budgets on one solver instance; reports through emit(('backend', name)) / emit(('row', row, found))."""
    be = make_backend(e, backend)
    emit(('backend', be.name))
    last = None; found = None
    try:
        for j in range(kmax + 1):
            if found is not None:
                row = dict(k=j, verdict='ATTACK_FOUND', min_faults=len(found['faults']), solve_s=0.0, implied_by=len(found['faults']))
            elif j > e.card[2]:                       # more budget than fault variables: same query as the last one
                row = dict(k=j, verdict=last['verdict'], solve_s=0.0, implied_by=last['k'])
            else:
                t1 = time.time()
                r = be.solve(atmost(e, j), time.time() + timeout_ms / 1000.0 if timeout_ms else None)
                dt = round(time.time() - t1, 3)
                if r is None:
                    emit(('row', dict(k=j, verdict='UNKNOWN_TIMEOUT', solve_s=dt), None)); break
                if r is False:
                    row = dict(k=j, verdict='NO_ATTACK_UP_TO_BOUND', solve_s=dt)
                else:
                    inputs, faults = _extract(nl, N, e, be.model(), kw)
                    if len(faults) != j:              # j-1 was refuted and the budget is j, so the witness has exactly j flips
                        raise RuntimeError(f'internal error: witness with {len(faults)} faults at budget {j}')
                    found = dict(inputs=inputs, faults=faults)
                    row = dict(k=j, verdict='ATTACK_FOUND', min_faults=len(faults), solve_s=dt)
            last = row
            emit(('row', row, found))
    finally:
        be.close()


def _sweep_child(conn, *args):
    try:
        _sweep_rows(*args, emit=conn.send)
        conn.send(('end',))
    except BaseException as ex:
        conn.send(('err', type(ex).__name__, str(ex)))
    finally:
        conn.close()


def sweep(nl, N, kmax, timeout_ms=0, backend='auto', card='totalizer', collapse=True, fault_enc='xor', **kw):
    """One CNF, one solver instance, budgets j = 0..kmax in ascending order (each an assumption on the same instance).
    Returns (rows, info, found); rows[j] = dict(k, verdict, solve_s, min_faults?). After the first ATTACK_FOUND at budget
    m (the minimum, because m-1 was just refuted) every larger budget has the same answer and is not solved again.
    timeout_ms is per budget; a budget that hits it is reported as UNKNOWN_TIMEOUT and the sweep stops there."""
    kw.setdefault('goal_out', 'boot_word'); kw.setdefault('goal_value', 0x96)
    kw.setdefault('attack_in', 'sig'); kw.setdefault('key', 0xC3)
    t0 = time.time()
    e = encode(nl, N, collapse=collapse, fault_enc=fault_enc, **kw)
    add_cardinality(e, min(kmax, len(e.fault_order)), card)
    info = dict(e.info); info['build_s'] = round(time.time() - t0, 3); info['amk'] = card; info['cnf'] = e.stats()
    rows = []; state = dict(found=None)

    def take(msg):
        if msg[0] == 'backend': info['backend'] = msg[1]
        elif msg[0] == 'row':
            rows.append(msg[1])
            if msg[2] is not None: state['found'] = msg[2]
    if timeout_ms and backend_kind(backend) == 'pysat':     # no in-process limit there: child process, killed at the limit
        import multiprocessing as mp
        ctx = mp.get_context('fork')
        pc, cc = ctx.Pipe(duplex=False)
        p = ctx.Process(target=_sweep_child, args=(cc, nl, N, kmax, e, backend, 0, kw), daemon=True)
        p.start(); cc.close()
        try:
            while True:
                t1 = time.time()
                try:
                    msg = pc.recv() if pc.poll(timeout_ms / 1000.0) else None
                except EOFError:
                    msg = ('err', 'RuntimeError', 'solver process died without a result')
                if msg is None:
                    rows.append(dict(k=len(rows), verdict='UNKNOWN_TIMEOUT', solve_s=round(time.time() - t1, 3))); break
                if msg[0] == 'end': break
                if msg[0] == 'err':
                    if msg[1] in ('BackendError', 'NetlistError'): raise BackendError(msg[2])
                    raise RuntimeError(f'{msg[1]}: {msg[2]}')
                take(msg)
        finally:
            if p.is_alive(): p.kill()
            p.join()
        info.setdefault('backend', _pysat_name(backend[6:] if str(backend).startswith('pysat:') else (backend or 'auto')))
    else:
        _sweep_rows(nl, N, kmax, e, backend, timeout_ms, kw, take)
    return rows, info, state['found']


def honest_boots(nl, N, **kw):
    """Sanity, as glitchsat.honest_boots: the fault-free run with the legitimate key reaches the goal. Solved on a
    fault-free CNF with the bundled solver (constant propagation leaves almost nothing to search)."""
    kw = dict(kw); key = kw.get('key', 0xC3)
    kw.pop('reduce', None)
    e = encode(nl, N, bad_only=False, fixed_in=key, faults=False, **kw)
    be = PyBackend(e)
    return be.solve([]) is True


# ---------------------------------------------------------------- run_check + CLI
def run_check(verilog, top, k, N, out=None, reduce='full', goal_out='boot_word', goal_value=0x96, attack_in='sig',
              key=0xC3, timeout_ms=0, workdir=None, label='MEASURED', flow='plain', backend='auto', card='totalizer',
              collapse=True, fault_enc='xor', dimacs_out=None):
    """Counterpart of glitchsat.run_check: same checks, same result fields, plus "backend": "sat:<solver>"."""
    if k < 0: raise NetlistError(f'--k must be >= 0 (got {k})')
    if N < 1: raise NetlistError(f'--cycles must be >= 1 (got {N}); 0 cycles would give a vacuous NO_ATTACK')
    if goal_value < 0 or key < 0: raise NetlistError('--goal-value and --key must be non-negative')
    if not os.path.isfile(verilog): raise NetlistError(f'no such file: {verilog}')
    t0 = time.time()
    if verilog.endswith('.json'):
        jpath = verilog; flow = 'given-netlist'
    else:
        workdir = workdir or os.path.join(REPO_ROOT, 'results', 'work')
        os.makedirs(workdir, exist_ok=True)
        jpath = os.path.join(workdir, f'{top}.json' if flow == 'plain' else f'{top}_{flow}.json')
        gs.synth(verilog, top, jpath, flow)
    t_syn = time.time() - t0
    nl = gs.Netlist(jpath, top)
    for pn, role in ((goal_out, 'output'), (attack_in, 'input')):
        if pn not in nl.ports or nl.ports[pn].get('direction') != role:
            raise NetlistError(f'{pn!r} is not an {role} port of {top}')
    if goal_value >> len(nl.ports[goal_out]['bits']):
        raise NetlistError(f'--goal-value 0x{goal_value:X} does not fit the {len(nl.ports[goal_out]["bits"])}-bit port {goal_out!r}')
    if key >> len(nl.ports[attack_in]['bits']):
        raise NetlistError(f'--key 0x{key:X} does not fit the {len(nl.ports[attack_in]["bits"])}-bit port {attack_in!r}')
    kw = dict(goal_out=goal_out, goal_value=goal_value, attack_in=attack_in, key=key, reduce=reduce)
    t0 = time.time()
    verdict, info, res = solve(nl, N, k, timeout_ms=timeout_ms, backend=backend, card=card, collapse=collapse,
                               fault_enc=fault_enc, dimacs_out=dimacs_out, **kw)
    wall = time.time() - t0
    out_d = dict(label=label, tool='glitchsat_sat.py', backend='sat:' + str(info.get('backend')),
                 design=os.path.relpath(verilog, REPO_ROOT) if os.path.isabs(verilog) else verilog,
                 design_sha256_16=gs.sha(verilog), top=top, synth_flow=flow, verdict=verdict,
                 bound=dict(max_faults=k, cycles=N, fault_model='single-cycle bit flip of any gate output or flop Q',
                            attacker_input=f'`{attack_in}` free, held constant, != key 0x{key:02X}',
                            goal=f'{goal_out} == 0x{goal_value:X} at some cycle < {N}'),
                 note=gs.NOTE.format(k=k, n=N), netlist=nl.stats(),
                 honest_key_boots_fault_free=honest_boots(nl, N, **kw),
                 model=info, runtime_s=dict(synth=round(t_syn, 3), solve_and_minimize=round(wall, 3)),
                 netlist_json=os.path.relpath(jpath, REPO_ROOT))
    if res:
        faults = [dict(net=nl.names.get(b, str(b)), net_id=b, cycle=t, kind='flop_Q' if b in nl.dq else 'gate_output') for t, b in res['faults']]
        out_d['min_faults'] = len(faults)
        out_d['faults'] = faults
        out_d['attacker_input'] = {p: f'0x{v:02X}' if v < 256 else hex(v) for p, v in res['inputs'].items()}
        out_d['attacker_input_raw'] = res['inputs']
        out_d['explanation'] = gs.explain(nl, res, len(faults), N, goal_out, attack_in)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w') as f:
            json.dump(out_d, f, indent=2)
    return out_d


def _add_common(c):
    c.add_argument('verilog', metavar='NETLIST', help='Yosys JSON netlist (.json) or Verilog (.v; needs yosys on PATH)')
    c.add_argument('--top', required=True, help='name of the top module inside NETLIST')
    c.add_argument('--k', type=int, required=True, help='largest number of flips the attacker may use (the fault budget)')
    c.add_argument('--cycles', type=int, required=True, help='number of clock cycles to unroll')
    c.add_argument('--out', metavar='FILE', help='also write the full result as JSON to FILE')
    c.add_argument('--reduce', choices=['none', 'coi', 'full'], default='full',
                   help='which fault sites the model allows (same meaning as glitchsat.py check). Sites that cannot reach the goal '
                        'in time never get a CNF variable under any setting; this changes no verdict. Default full')
    c.add_argument('--goal-out', default='boot_word', metavar='PORT', help='output port the attacker wants to control (default boot_word)')
    c.add_argument('--goal-value', type=lambda x: int(x, 0), default=0x96, metavar='N', help='value the goal port must show (default 0x96)')
    c.add_argument('--attack-input', default='sig', metavar='PORT', help='input port the attacker chooses (default sig)')
    c.add_argument('--key', type=lambda x: int(x, 0), default=0xC3, metavar='N', help='the legitimate key; the attacker input must differ from it (default 0xC3)')
    c.add_argument('--timeout-ms', type=int, default=0, metavar='MS', help='solver time limit in milliseconds; 0 = no limit. A timeout gives exit 2, never "no attack"')
    c.add_argument('--flow', choices=['plain', 'opt'], default='plain', help='Yosys synthesis flow for Verilog input; ignored for .json netlists')
    c.add_argument('--backend', default='auto', metavar='B',
                   help='auto (PySAT CaDiCaL if python-sat is installed, else the bundled Python solver) | py | pysat:<name> '
                        '(cadical, cadical195, cadical153, glucose4, glucose42, minisat22, ...) | dimacs:<binary> (kissat, cadical, ...)')
    c.add_argument('--card', choices=['totalizer', 'seqcounter'], default='totalizer', help='at-most-k encoding (default totalizer)')
    c.add_argument('--amk', choices=['counter', 'legacy'], default=None, help='accepted for compatibility with glitchsat.py; ignored (see --card)')
    c.add_argument('--no-collapse', action='store_true', help='give every time-relevant fault site its own variable (no fault collapsing)')
    c.add_argument('--fault-enc', choices=['xor', 'relax'], default='xor', help='fault selector encoding: xor = exact flip (default); relax = selector frees the net')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='glitchsat_sat.py',
        description='GlitchSAT bounded fault-injection check on a direct CNF encoding (PySAT / DIMACS solver / bundled Python CDCL). '
                    'Same question, bounds and result fields as scripts/glitchsat.py check. Results are bounded, not proofs.',
        epilog='exit codes: 0 verdict printed; 2 solver unknown/timeout; 3 usage/input/netlist error or backend not installed; 4 internal error. '
               'Example: python3 ext/fastsat/scripts/glitchsat_sat.py check reference/spike_netlists/v2.json --top v2 --k 3 --cycles 6')
    ap.add_argument('--version', action='version', version=f'glitchsat_sat.py {__version__} (engine semantics of glitchsat.py {gs.__version__})')
    sp = ap.add_subparsers(dest='cmd', required=True, metavar='COMMAND')
    c = sp.add_parser('check', help='bounded attack search: smallest number of flips (up to --k) that reaches the goal')
    _add_common(c)
    c.add_argument('--dimacs-out', metavar='FILE', help='also write the CNF (with the at-most-k assumption as a unit clause) to FILE')
    w = sp.add_parser('sweep', help='one solver instance, every budget 0..--k: verdict and solve time per budget')
    _add_common(w)
    s = sp.add_parser('cnf', help='print CNF size (variables, clauses) for the given bound; solves nothing')
    _add_common(s)
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'check':
            r = run_check(a.verilog, a.top, a.k, a.cycles, a.out, a.reduce, a.goal_out, a.goal_value, a.attack_input, a.key,
                          a.timeout_ms, flow=a.flow, backend=a.backend, card=a.card, collapse=not a.no_collapse,
                          fault_enc=a.fault_enc, dimacs_out=a.dimacs_out)
        else:
            if a.k < 0 or a.cycles < 1: raise NetlistError('--k must be >= 0 and --cycles >= 1')
            if not a.verilog.endswith('.json'): raise NetlistError(f'{a.cmd} needs a .json netlist')
            if not os.path.isfile(a.verilog): raise NetlistError(f'no such file: {a.verilog}')
            nl = gs.Netlist(a.verilog, a.top)
            for pn, role in ((a.goal_out, 'output'), (a.attack_input, 'input')):
                if pn not in nl.ports or nl.ports[pn].get('direction') != role:
                    raise NetlistError(f'{pn!r} is not an {role} port of {a.top}')
            if a.goal_value < 0 or a.key < 0 or a.goal_value >> len(nl.ports[a.goal_out]['bits']) or a.key >> len(nl.ports[a.attack_input]['bits']):
                raise NetlistError('--goal-value / --key do not fit their ports')
            kw = dict(goal_out=a.goal_out, goal_value=a.goal_value, attack_in=a.attack_input, key=a.key, reduce=a.reduce)
            if a.cmd == 'cnf':
                e = encode(nl, a.cycles, collapse=not a.no_collapse, fault_enc=a.fault_enc, **kw)
                base = e.stats()
                add_cardinality(e, min(a.k, len(e.fault_order)), a.card)
                d = dict(netlist=nl.stats(), cycles=a.cycles, k=a.k, model=e.info, cnf_circuit=base, cnf_total=e.stats(), card=a.card)
                print(json.dumps(d, indent=2))
                if a.out:
                    with open(a.out, 'w') as f: json.dump(d, f, indent=2)
                sys.exit(0)
            rows, info, found = sweep(nl, a.cycles, a.k, timeout_ms=a.timeout_ms, backend=a.backend, card=a.card,
                                      collapse=not a.no_collapse, fault_enc=a.fault_enc, **kw)
            d = dict(tool='glitchsat_sat.py', backend='sat:' + info['backend'], top=a.top, cycles=a.cycles, netlist=nl.stats(), model=info, rows=rows)
            if found:
                d['faults'] = [dict(net=nl.names.get(b, str(b)), net_id=b, cycle=t) for t, b in found['faults']]
                d['attacker_input_raw'] = found['inputs']
            print(f"{a.top}: sweep k=0..{a.k}, cycles={a.cycles}, backend sat:{info['backend']}, CNF {info['cnf']['vars']} vars / {info['cnf']['clauses']} clauses")
            for r in rows:
                print(f"  k<={r['k']}: {r['verdict']:<22} solve={r['solve_s']}s" + (f"  min faults {r['min_faults']}" if 'min_faults' in r else '')
                      + ('  (implied, not re-solved)' if 'implied_by' in r else ''))
            print('  ' + gs.NOTE.format(k=a.k, n=a.cycles))
            if a.out:
                with open(a.out, 'w') as f: json.dump(d, f, indent=2)
            sys.exit(2 if rows[-1]['verdict'] == 'UNKNOWN_TIMEOUT' else 0)
    except NetlistError as e:
        print(f'error: {gs._safe(str(e))}', file=sys.stderr); sys.exit(gs.EXIT_INPUT_ERROR)
    except (RecursionError, KeyError, IndexError, TypeError, RuntimeError) as e:
        print(f'internal error ({type(e).__name__}: {gs._safe(str(e))}); no verdict', file=sys.stderr); sys.exit(gs.EXIT_INTERNAL_ERROR)
    print(f"{a.top}: {r['verdict']}  (k<={a.k}, cycles={a.cycles}, reduce={a.reduce}, backend={r['backend']})  solve={r['runtime_s']['solve_and_minimize']}s")
    if 'faults' in r:
        print('  min faults:', r['min_faults'], gs._safe(str([(f['net'], f['cycle']) for f in r['faults']])), 'input', r['attacker_input'],
              '' if r['model'].get('minimum_proved') else ' [minimum NOT proved: time limit during minimisation]')
        print('  ' + r['explanation']['summary']); print('  FIX: ' + r['explanation']['fix_pattern'])
    print('  ' + r['note'])
    sys.exit(0 if r['verdict'] in ('NO_ATTACK_UP_TO_BOUND', 'ATTACK_FOUND') else 2)


if __name__ == '__main__':
    main()
