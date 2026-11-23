#!/usr/bin/env python3
"""Attack surface ("heatmap") for GlitchSAT: ALL minimum-size attacks of a netlist, and where they sit.

Question it answers: the engine (scripts/glitchsat.py) reports ONE smallest attack. This lists every attack of that
smallest size m (within the bound) and counts, per gate/flop and per cycle, how many of those attacks use it, and how
the faults split over the redundant copies (c0/c1/c2 ...).

Same modelled fault model and goal as scripts/glitchsat.py `build()`: a fault is a single-cycle bit flip of a gate
output or a flop Q net at one cycle t < N; every input port except clk is free and held constant; the goal is
goal_out == goal_value at some cycle < N while attack_in != key. Fault sites are the engine's `reduce` site set
(default 'full'; the set of MINIMUM attacks does not depend on it: a minimum attack cannot contain a flip that cannot
reach the goal, since dropping it would give a smaller attack).

Two methods:
  exhaustive  pure Python + numpy, no z3. Simulates every set of s single-cycle flips for s = 0, 1, 2, ... until the
              first size with an attack (that size is m), bit-parallel over all values of the free inputs (up to 16
              input bits). Exact and complete when it finishes; cost grows as C(sites, m).
  sat         z3 (lazy import). Finds m with the engine's at-most-k counter, then repeats: get a model with m flips,
              add a blocking clause Or(Not f) over its fault-selector variables, until UNSAT (complete), the cap, or the
              timeout. Each found attack is re-simulated with the exhaustive simulator when the inputs are small.

JSON output (schema "glitchsat-attack-surface/1"):
  schema, method: "sat"|"exhaustive", netlist (repository-relative when inside the repository), netlist_sha256, top,
  bound: {cycles, max_faults, goal, attacker_input, key, reduce, fault_model},
  verdict: "ATTACK_FOUND" | "NO_ATTACK_UP_TO_BOUND" | "INCOMPLETE",
  min_faults: m or null, count: number of minimum attacks listed,
  complete: true only if every attack of size m was found AND no smaller attack exists,
  stop_reason: "exhausted" | "cap" | "timeout" | "solver_unknown" | "no_attack",
  sites_modelled, sets_simulated (exhaustive) / solver_calls (sat), runtime_s,
  copy_source: "names" | "structural" | "none",
  nets:   [{net, net_id, kind: "gate_output"|"flop_Q", gate, copy, count, share, cycles: {cycle: count}}]
          count = number of minimum attacks that flip this net (at any cycle); share = count / total count;
          sorted by count, descending,
  cycles: {cycle: {faults, attacks}}  faults = flips at that cycle over all attacks; attacks = attacks with >= 1 flip there,
  copies: {label: {faults, share, attacks}}  share = that label's flips / all flips. Labels from merge_lint:
          "c0".. (net inside that copy's cone), "c0:path".. (net downstream of that copy only, e.g. its result-word
          gate), "shared" (inside two copy cones), "merge" (combines copies), "outside" (no copy logic: state, decode),
  copies_touched: {n: number of attacks whose flips touch n distinct copies (cX and cX:path count as copy cX)},
  attacks: [{faults: [[net, cycle], ...], inputs: number of free-input values that work | example input}] (first
           `list_limit` attacks; the note says so when the list is truncated), note.
BOUNDED and MODELLED: nothing here is about more cycles, other fault types, or physical feasibility.
"""
import argparse, collections, hashlib, itertools, json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import merge_lint   # noqa: E402  (no z3)

np = None


def _np():
    global np
    if np is None:
        import numpy
        np = numpy
    return np


def engine():
    return merge_lint.engine()


NOTE = ('BOUNDED and MODELLED: all attacks of the minimum size m with single-cycle bit flips of gate outputs and flop Q '
        'within {n} cycles on this netlist. Nothing is said about more cycles, other fault types, or physical feasibility.')
ALL64 = 0xFFFFFFFFFFFFFFFF


class Sim:
    """Bit-parallel simulator of a Netlist for batches of fault sets (numpy). Semantics copy scripts/glitchsat.py build():
    a flip of net b at cycle t XORs b's value during cycle t only (a flop Q flip is seen by the logic and by the outputs in
    that cycle; the stored flop value is not changed); outputs are sampled before the clock edge."""

    MAX_INPUT_BITS = 16

    def __init__(self, nl, N, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, reduce='full'):
        _np()
        GS = engine()
        self.nl, self.N = nl, N
        ports = nl.ports
        if goal_out not in ports or ports[goal_out].get('direction') != 'output':
            raise GS.NetlistError(f'goal output {goal_out!r} is not an output port')
        if attack_in not in ports or ports[attack_in].get('direction') != 'input':
            raise GS.NetlistError(f'attacker input {attack_in!r} is not an input port')
        self.goal_bits = ports[goal_out]['bits']
        self.goal_value = goal_value
        ins = [(p, v['bits']) for p, v in ports.items() if v.get('direction') == 'input' and p != 'clk']
        W = sum(len(b) for _, b in ins)
        if W > self.MAX_INPUT_BITS:
            raise ValueError(f'{W} free input bits: exhaustive lanes limited to {self.MAX_INPUT_BITS}')
        L = 1 << W
        self.words = max(1, L // 64)
        lanes = np.arange(self.words * 64, dtype=np.uint64)
        valid = lanes < L

        def pack(boolarr):
            bits = boolarr.reshape(self.words, 64).astype(np.uint64)
            return (bits << np.arange(64, dtype=np.uint64)).sum(axis=1, dtype=np.uint64)[None, :]
        self.inbit = {}
        off = 0
        self.fields = {}
        for p, bits in ins:
            self.fields[p] = (off, len(bits))
            for i, b in enumerate(bits):
                if isinstance(b, int):
                    self.inbit[b] = pack(((lanes >> np.uint64(off + i)) & np.uint64(1)).astype(bool) & valid)
            off += len(bits)
        ao, aw = self.fields[attack_in]
        aval = (lanes >> np.uint64(ao)) & np.uint64((1 << aw) - 1)
        self.bad = pack(valid & (aval != np.uint64(key)))
        self.honest = pack(valid & (aval == np.uint64(key)))
        self.ZERO = np.zeros((1, self.words), dtype=np.uint64)
        self.ONE = np.full((1, self.words), ALL64, dtype=np.uint64)
        # sites: same set and order as build()
        dist = nl.coi_and_dist(self.goal_bits)
        allsites = list(nl.qs) + list(nl.drivers.keys())
        if reduce == 'none':
            usable = lambda t, b: True
        elif reduce == 'coi':
            usable = lambda t, b: b in dist
        else:
            usable = lambda t, b: b in dist and t + dist[b] <= N - 1
        self.sites = [(t, b) for t in range(N) for b in allsites if usable(t, b)]
        self.site_index = {s: i for i, s in enumerate(self.sites)}
        self.by_cycle = collections.defaultdict(dict)   # t -> {net: site idx}
        for i, (t, b) in enumerate(self.sites):
            self.by_cycle[t][b] = i
        # evaluation order (gates needed for flop D nets and goal bits)
        order, seen = [], set()
        for root in list(nl.dq.values()) + [b for b in self.goal_bits]:
            st = [root]
            while st:
                b = st[-1]
                if not isinstance(b, int) or b in seen or b in self.inbit or b in nl.dq:
                    if isinstance(b, str) and b not in ('0', '1'):
                        raise GS.NetlistError(f'constant {b!r} bit in the logic; refusing (would be treated as 0)')
                    st.pop(); continue
                if b not in nl.drivers:
                    raise GS.NetlistError(f'net {nl.names.get(b, b)!r} (id {b}) is used but has no driver')
                _, ty, con = nl.drivers[b]
                if ty not in GS.SUPPORTED:
                    raise GS.NetlistError('unsupported cell ' + ty)
                pend = [con[p][0] for p in GS._CELL_PINS[ty] if isinstance(con[p][0], int) and con[p][0] not in seen
                        and con[p][0] not in self.inbit and con[p][0] not in nl.dq]
                if pend:
                    st.extend(pend); continue
                for p in GS._CELL_PINS[ty]:
                    if isinstance(con[p][0], str) and con[p][0] not in ('0', '1'):
                        raise GS.NetlistError(f'constant {con[p][0]!r} bit in the logic; refusing (would be treated as 0)')
                seen.add(b); order.append(b); st.pop()
        self.order = [(b, nl.drivers[b][1], {p: v[0] for p, v in nl.drivers[b][2].items() if p != 'Y'}) for b in order]
        self.init = {q: (self.ONE if nl.init.get(q, False) else self.ZERO) for q in nl.qs}

    def _get(self, val, b):
        if b == '0':
            return self.ZERO
        if b == '1':
            return self.ONE
        if b in self.inbit:
            return self.inbit[b]
        return val[b]

    def run(self, combos):
        """combos: int array (B, s) of site indices. Returns (B, words) uint64 lanes of free-input values that reach the
        goal while attack_in != key."""
        B = combos.shape[0]
        flips = collections.defaultdict(dict)   # t -> {net: (B,1) uint64 mask}
        if combos.shape[1]:
            P = len(self.sites)
            M = np.zeros((P, B), dtype=bool)
            ar = np.arange(B)
            for j in range(combos.shape[1]):
                M[combos[:, j], ar] = True
            for i in np.nonzero(M.any(axis=1))[0]:
                t, b = self.sites[i]
                flips[t][b] = (M[i].astype(np.uint64) * np.uint64(ALL64))[:, None]
        state = dict(self.init)
        hit = self.ZERO
        for t in range(self.N):
            f = flips.get(t, {})
            val = {}
            for q, v in state.items():
                val[q] = v ^ f[q] if q in f else v
            g = self._get
            for b, ty, p in self.order:
                if ty == '$_AND_':
                    v = g(val, p['A']) & g(val, p['B'])
                elif ty == '$_OR_':
                    v = g(val, p['A']) | g(val, p['B'])
                elif ty == '$_XOR_':
                    v = g(val, p['A']) ^ g(val, p['B'])
                elif ty == '$_NOT_':
                    v = ~g(val, p['A'])
                else:
                    S = g(val, p['S'])
                    v = (g(val, p['B']) & S) | (g(val, p['A']) & ~S)
                if b in f:
                    v = v ^ f[b]
                val[b] = v
            m = self.ONE
            for i, b in enumerate(self.goal_bits):
                x = g(val, b)
                m = m & (x if (self.goal_value >> i) & 1 else ~x)
            hit = hit | m
            state = {q: g(val, d) for q, d in self.nl.dq.items()}
        out = hit & self.bad
        if out.shape[0] != B:
            out = np.broadcast_to(out, (B, self.words))
        return out

    def honest_boots(self):
        """Fault-free run with the legitimate key reaches the goal (lanes where attack_in == key)."""
        saved = self.bad
        self.bad = self.honest
        try:
            return bool(self.run(np.zeros((1, 0), dtype=np.int64)).any())
        finally:
            self.bad = saved

    @staticmethod
    def popcount(lanes):
        return np.unpackbits(np.ascontiguousarray(lanes).view(np.uint8), axis=1).sum(axis=1)


def _batches(P, s, target):
    """Yield int arrays (b, s) covering all s-subsets of range(P) in lexicographic order."""
    if s == 0:
        yield np.zeros((1, 0), dtype=np.int64); return
    if s == 1:
        for a in range(0, P, target):
            yield np.arange(a, min(P, a + target), dtype=np.int64)[:, None]
        return
    buf, n = [], 0
    for pre in itertools.combinations(range(P), s - 2):
        start = pre[-1] + 1 if pre else 0
        r = P - start
        if r < 2:
            continue
        i, j = np.triu_indices(r, 1)
        pairs = np.stack([i, j], axis=1).astype(np.int64) + start
        rows = np.hstack([np.tile(np.array(pre, dtype=np.int64), (len(pairs), 1)), pairs]) if pre else pairs
        buf.append(rows); n += len(rows)
        if n >= target:
            yield np.vstack(buf); buf, n = [], 0
    if buf:
        yield np.vstack(buf)


def exhaustive(nl, N, max_faults=3, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, reduce='full',
               timeout_s=None, cap=None, batch=50000, sim=None):
    """Returns dict(verdict, min_faults, attacks=[(sites tuple, n_inputs)], complete, stop_reason, sets_simulated, sites)."""
    _np()
    sim = sim or Sim(nl, N, goal_out, goal_value, attack_in, key, reduce)
    P = len(sim.sites)
    t0 = time.time()
    sets = 0
    for s in range(0, max_faults + 1):
        found = []
        stop = 'exhausted'
        for combos in _batches(P, s, batch):
            out = sim.run(combos)
            sets += len(combos)
            ok = out.any(axis=1)
            if ok.any():
                cnt = Sim.popcount(out[ok])
                for row, c in zip(combos[ok], cnt):
                    found.append((tuple(sim.sites[i] for i in row), int(c)))
            if cap and len(found) >= cap:
                found = found[:cap]; stop = 'cap'; break
            if timeout_s and time.time() - t0 > timeout_s:
                stop = 'timeout'; break
        if found:
            return dict(verdict='ATTACK_FOUND', min_faults=s, attacks=found, complete=stop == 'exhausted',
                        stop_reason=stop, sets_simulated=sets, sites=P, sim=sim)
        if stop != 'exhausted':
            return dict(verdict='INCOMPLETE', min_faults=None, attacks=[], complete=False, stop_reason=stop,
                        sets_simulated=sets, sites=P, sim=sim, searched_below=s)
    return dict(verdict='NO_ATTACK_UP_TO_BOUND', min_faults=None, attacks=[], complete=True, stop_reason='no_attack',
                sets_simulated=sets, sites=P, sim=sim)


def enumerate_sat(nl, N, max_faults=3, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, reduce='full',
                  timeout_s=None, cap=None, sim=None, verify=True):
    """z3 path. Same return shape as exhaustive(); attacks carry the solver's example input instead of an input count."""
    GS = engine()
    GS._require_z3()
    import z3
    t0 = time.time()
    deadline = t0 + timeout_s if timeout_s else None
    s, F, inputs, info = GS.build(nl, N, goal_out=goal_out, goal_value=goal_value, attack_in=attack_in, key=key, reduce=reduce)
    keys = list(F.keys())
    allf = [F[k] for k in keys]
    if allf:
        cl, outs = GS.seq_counter(allf, max_faults)
        s.add(*cl)
        atmost = lambda j: [z3.Not(outs[j + 1])]
    else:
        atmost = lambda j: []
    calls = 0

    def check(j):
        nonlocal calls
        if deadline:
            rem = int((deadline - time.time()) * 1000)
            if rem <= 0:
                return z3.unknown
            s.set('timeout', max(1, rem))
        calls += 1
        return s.check(*atmost(j))
    base = dict(sites=len(keys), solver_calls=0)
    m = None
    for j in range(0, max_faults + 1):
        r = check(j)
        if r == z3.sat:
            m = j; break
        if r != z3.unsat:
            base.update(verdict='INCOMPLETE', min_faults=None, attacks=[], complete=False,
                        stop_reason='timeout' if deadline and time.time() >= deadline else 'solver_unknown', solver_calls=calls)
            return base
    if m is None:
        base.update(verdict='NO_ATTACK_UP_TO_BOUND', min_faults=None, attacks=[], complete=True, stop_reason='no_attack', solver_calls=calls)
        return base
    found = []
    stop = 'exhausted'
    first = True
    while True:
        r = z3.sat if first else check(m)
        first = False
        if r == z3.unsat:
            break
        if r != z3.sat:
            stop = 'timeout' if deadline and time.time() >= deadline else 'solver_unknown'
            break
        mod = s.model()
        faults = tuple(sorted((k for k in keys if z3.is_true(mod.eval(F[k], model_completion=True))), key=lambda x: (x[0], x[1])))
        if len(faults) != m:
            raise RuntimeError(f'internal error: model has {len(faults)} faults, minimum is {m}')
        ex = {p: mod.eval(v, model_completion=True).as_long() for p, v in inputs.items()}
        found.append((faults, ex))
        if cap and len(found) >= cap:
            stop = 'cap'; break
        if not faults:
            break   # m == 0: the fault-free run already attacks; one (empty) attack
        s.add(z3.Or(*[z3.Not(F[k]) for k in faults]))
    res = dict(verdict='ATTACK_FOUND', min_faults=m, attacks=found, complete=stop == 'exhausted', stop_reason=stop,
               sites=len(keys), solver_calls=calls)
    if verify:
        try:
            sim = sim or Sim(nl, N, goal_out, goal_value, attack_in, key, reduce)
            idx = np.array([[sim.site_index[x] for x in a] for a, _ in found], dtype=np.int64).reshape(len(found), m)
            out = sim.run(idx) if len(found) else np.zeros((0, 1), dtype=np.uint64)
            res['confirmed_by_simulation'] = int(out.any(axis=1).sum()) if len(found) else 0
        except (ValueError, KeyError) as e:
            res['confirmed_by_simulation'] = f'not checked: {e}'
    return res


def stored_path(p):
    """Path written into result files: relative to the repository root when the file is inside it (so stored results
    carry no machine-specific absolute paths), else as given."""
    if not p:
        return p
    try:
        root = os.path.realpath(merge_lint._repo_root())
    except ImportError:
        return p
    ap_ = os.path.realpath(p)
    if os.path.commonpath([root, ap_]) == root:
        return os.path.relpath(ap_, root)
    return p


def summarize(nl, res, N, method, netlist_path=None, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3,
              reduce='full', max_faults=3, runtime_s=None, list_limit=200, copy_re=merge_lint.DEFAULT_COPY_RE, groups=None):
    mem, src = merge_lint.copy_membership(nl, goal_out=goal_out, copy_re=copy_re, groups=groups)
    attacks = res['attacks']
    total = len(attacks)
    net_count = collections.Counter()
    net_cyc = collections.defaultdict(collections.Counter)
    cyc_f = collections.Counter()
    cyc_a = collections.Counter()
    copy_f = collections.Counter()
    copy_a = collections.Counter()
    touched = collections.Counter()
    for a, _ in attacks:
        for t, b in a:
            net_cyc[b][t] += 1
            cyc_f[t] += 1
            copy_f[mem.get(b, 'outside')] += 1
        for b in {b for _, b in a}:
            net_count[b] += 1
        for t in {t for t, _ in a}:
            cyc_a[t] += 1
        cs = {mem.get(b, 'outside') for _, b in a}
        for c in cs:
            copy_a[c] += 1
        touched[len({c.split(':')[0] for c in cs if c not in ('outside', 'merge', 'shared')})] += 1
    nflips = sum(copy_f.values())
    nets = []
    for b, c in sorted(net_count.items(), key=lambda kv: (-kv[1], nl.names.get(kv[0], str(kv[0])))):
        nets.append(dict(net=nl.names.get(b, str(b)), net_id=b, kind='flop_Q' if b in nl.dq else 'gate_output',
                         gate='DFF' if b in nl.dq else nl.drivers[b][1].strip('$_'), copy=mem.get(b, 'outside'),
                         count=c, share=round(c / total, 4) if total else 0.0,
                         cycles={str(t): n for t, n in sorted(net_cyc[b].items())}))
    lst = []
    for a, x in attacks[:list_limit]:
        e = dict(faults=[[nl.names.get(b, str(b)), t] for t, b in a])
        if isinstance(x, dict):
            e['example_input'] = x
        else:
            e['inputs'] = x
        lst.append(e)
    sha = None
    if netlist_path:
        with open(netlist_path, 'rb') as f:
            sha = hashlib.sha256(f.read()).hexdigest()
    out = dict(schema='glitchsat-attack-surface/1', method=method, netlist=stored_path(netlist_path), netlist_sha256=sha, top=nl.top,
               bound=dict(cycles=N, max_faults=max_faults, goal=f'{goal_out} == 0x{goal_value:X} at some cycle < {N}',
                          attacker_input=f'`{attack_in}` free, held constant, != key 0x{key:02X} (other inputs free)', key=key,
                          reduce=reduce, fault_model='single-cycle bit flip of any gate output or flop Q'),
               verdict=res['verdict'], min_faults=res['min_faults'], count=total, complete=res['complete'],
               stop_reason=res['stop_reason'], sites_modelled=res['sites'], runtime_s=runtime_s, copy_source=src,
               nets=nets, cycles={str(t): dict(faults=cyc_f[t], attacks=cyc_a[t]) for t in sorted(cyc_f)},
               copies={c: dict(faults=copy_f[c], share=round(copy_f[c] / nflips, 4) if nflips else 0.0, attacks=copy_a[c])
                       for c in sorted(copy_f)},
               copies_touched={str(k): v for k, v in sorted(touched.items())},
               attacks=lst, attacks_listed=len(lst), note=NOTE.format(n=N))
    for k in ('sets_simulated', 'solver_calls', 'confirmed_by_simulation', 'searched_below'):
        if k in res:
            out[k] = res[k]
    if total > len(lst):
        out['note'] += (f' TRUNCATED LIST: attacks[] holds the first {len(lst)} of {total} minimum attacks in full '
                        '(--list-limit); nets/cycles/copies counts use all of them.')
    if not out['complete']:
        out['note'] += (' INCOMPLETE: the list stops early (' + res['stop_reason'] + '); counts are lower bounds'
                        + (' and the minimum size is not established.' if res['min_faults'] is None else '.'))
    return out


def run(netlist, top, N=6, max_faults=3, method='auto', goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3,
        reduce='full', timeout_s=None, cap=None, list_limit=200, copy_re=merge_lint.DEFAULT_COPY_RE, groups=None):
    GS = engine()
    nl = GS.Netlist(netlist, top)
    if method == 'auto':
        method = 'sat' if GS._Z3_IMPORT_ERROR is None else 'exhaustive'
    t0 = time.time()
    kw = dict(goal_out=goal_out, goal_value=goal_value, attack_in=attack_in, key=key, reduce=reduce)
    if method == 'sat':
        res = enumerate_sat(nl, N, max_faults, timeout_s=timeout_s, cap=cap, **kw)
    else:
        res = exhaustive(nl, N, max_faults, timeout_s=timeout_s, cap=cap, **kw)
    rt = round(time.time() - t0, 3)
    return summarize(nl, res, N, method, netlist, max_faults=max_faults, runtime_s=rt, list_limit=list_limit,
                     copy_re=copy_re, groups=groups, **kw)


def format_text(r, top_n=10):
    lines = [f"{r['top']}: {r['verdict']}  method={r['method']}  min_faults={r['min_faults']}  minimum attacks={r['count']}"
             f"  complete={r['complete']} ({r['stop_reason']})  {r['runtime_s']} s"]
    if r['nets']:
        lines.append(f"  top nets (in how many of the {r['count']} minimum attacks):")
        for n in r['nets'][:top_n]:
            lines.append(f"    {n['count']:6d}  {100 * n['share']:5.1f}%  {n['copy']:8s} {n['kind']:11s} `{n['net']}`  cycles {n['cycles']}")
        lines.append('  per cycle (flips / attacks): ' + ', '.join(f"{t}: {v['faults']}/{v['attacks']}" for t, v in r['cycles'].items()))
        lines.append(f"  per copy (share of flips, copies from {r['copy_source']}): " +
                     ', '.join(f"{c} {100 * v['share']:.1f}%" for c, v in r['copies'].items()))
        lines.append('  attacks by number of copies touched: ' + ', '.join(f'{k}: {v}' for k, v in r['copies_touched'].items()))
    lines.append('  ' + r['note'])
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Attack surface: every minimum-size modelled fault attack within the bound, '
                                             'and how often each net / cycle / copy appears in them.')
    ap.add_argument('netlist')
    ap.add_argument('--top', required=True)
    ap.add_argument('--cycles', type=int, default=6)
    ap.add_argument('--k', type=int, default=3, help='largest attack size searched (default 3)')
    ap.add_argument('--method', choices=['auto', 'sat', 'exhaustive'], default='auto',
                    help='auto = sat when z3 imports, else exhaustive')
    ap.add_argument('--goal-out', default='boot_word')
    ap.add_argument('--goal-value', type=lambda x: int(x, 0), default=0x96)
    ap.add_argument('--attack-input', default='sig')
    ap.add_argument('--key', type=lambda x: int(x, 0), default=0xC3)
    ap.add_argument('--reduce', choices=['none', 'coi', 'full'], default='full')
    ap.add_argument('--timeout-s', type=float, default=None)
    ap.add_argument('--cap', type=int, default=100000, help='stop after this many minimum attacks (default 100000)')
    ap.add_argument('--list-limit', type=int, default=200, help='attacks written out in full (default 200)')
    ap.add_argument('--groups', help='intended decision-bit ownership for the per-copy split, e.g. "0,3,6;1,4,7;2,5"')
    ap.add_argument('--json', metavar='FILE', help='write JSON to FILE ("-" for stdout)')
    a = ap.parse_args(argv)
    r = run(a.netlist, a.top, a.cycles, a.k, a.method, a.goal_out, a.goal_value, a.attack_input, a.key, a.reduce,
            a.timeout_s, a.cap, a.list_limit, groups=merge_lint.parse_groups(a.groups))
    if a.json == '-':
        print(json.dumps(r, indent=2))
    else:
        print(format_text(r))
        if a.json:
            with open(a.json, 'w') as f:
                json.dump(r, f, indent=2)
    return 0 if r['verdict'] != 'INCOMPLETE' else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:   # output piped into head etc.
        sys.exit(0)
