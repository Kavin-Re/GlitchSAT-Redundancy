#!/usr/bin/env python3
"""GlitchSAT unbounded analysis: "no attack with at most k single-cycle flips at ANY time", or an attack.

Methods (each can be run alone; `--method all` runs every one and refuses to print a verdict if they disagree):
    oracle  exhaustive search of every reachable state with a fault budget, plain Python (no solver)
    kind    k-induction with simple-path constraints (SAT)
    ic3     IC3/PDR; a proof is an inductive invariant that is re-checked in a fresh solver (SAT)
Fault model, attacker input, goal and power-up options are those of scripts/glitchsat.py and the GlitchSAT CLI.

    python3 src/unbounded.py check reference/spike_netlists/v2.json --top v2 --k 2
    python3 src/unbounded.py all --out-dir results          # every reference design, k = 0..3

Exit codes: 0 verdict printed (PROVED_UNBOUNDED or ATTACK_FOUND), 2 unknown or vacuous, 3 input error, 4 methods disagree.
"""
import argparse, hashlib, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sat, ts as tsmod, kind, ic3 as ic3mod, oracle as omod

__version__ = '0.1.0'
SCOPE_NOTE = ('UNBOUNDED IN TIME, BOUNDED IN EVERYTHING ELSE: the verdict covers any number of clock cycles, for at most '
              '{k} modelled single-cycle bit flips (gate outputs and flop Q nets{ins}) in total, on this one netlist, with '
              'the attacker input held constant and not equal to the key. It says nothing about more flips, other fault '
              'types (stuck-at, multi-cycle, clock or voltage effects), other netlists of the same RTL, or physical '
              'feasibility. Toy design; modelled faults.')

# name -> (netlist path relative to the repository root, top module, where it comes from)
DESIGNS = {
    'v0_stored': ('reference/spike_netlists/v0.json', 'v0', 'stored reference netlist'),
    'v1_stored': ('reference/spike_netlists/v1.json', 'v1', 'stored reference netlist'),
    'v2_stored': ('reference/spike_netlists/v2.json', 'v2', 'stored reference netlist (68 gates)'),
    'v0_apt':    ('formal/gen/w0.json', 'v0', 'rtl/v0.v, synth.sh plain, apt Yosys 0.33 (copy of results/work)'),
    'v1_apt':    ('formal/gen/w1.json', 'v1', 'rtl/v1.v, synth.sh plain, apt Yosys 0.33 (copy of results/work)'),
    'v2_apt':    ('research/c6/p01/netlists/nl_apt_v2.json', 'v2', 'rtl/v2.v, synth.sh plain, apt Yosys 0.33 (85 gates)'),
    'v2_conda':  ('research/c6/p01/netlists/nl_conda_v2.json', 'v2', 'rtl/v2.v, synth.sh plain, conda Yosys 0.38+92 (83 gates)'),
    'v2e_apt':   ('research/c6/p01/netlists/nl_apt_v2e.json', 'v2e', 'rtl/v2e.v, synth.sh plain, apt Yosys 0.33'),
    'v2e_conda': ('research/c6/p01/netlists/nl_conda_v2e.json', 'v2e', 'rtl/v2e.v, synth.sh plain, conda Yosys 0.38+92'),
    # other small sequential designs found in the repository
    'v2_stored_ok': ('reference/spike_netlists/v2.json', 'v2', 'stored reference netlist, goal boot_ok == 1 instead of the word'),
    'v0_apt033': ('research/c4/b3_inputs/nl/v0_apt033.json', 'v0', 'rtl/v0.v, apt Yosys 0.33 plain flow (B3 inputs)'),
    'v1_apt033': ('research/c4/b3_inputs/nl/v1_apt033.json', 'v1', 'rtl/v1.v, apt Yosys 0.33 plain flow (B3 inputs)'),
    'v2_apt033': ('research/c4/b3_inputs/nl/v2_apt033.json', 'v2', 'rtl/v2.v, apt Yosys 0.33 plain flow (B3 inputs, 93 cells)'),
    'v5_apt033': ('research/c4/b3_inputs/nl/v5_apt033.json', 'v5', 'research/c3/v456/rtl/v5.v, apt Yosys 0.33 plain flow (217 cells, 9 flops)'),
    'v2_flowB': ('validation/nl/v2.json', 'v2', 'rtl/v2.v, validation flow B (flatten, hierarchy stripped)'),
    'v2_inbuf': ('research/c2/reviews/ct/tests/v2_inbuf.json', 'v2', 'V2 with buffers on the shared sig inputs'),
    'v2c04_apt': ('research/c6/p01/netlists/nl_apt_v2c04.json', 'v2c04', 'control design armed state 0x04, apt Yosys 0.33'),
    'v2c04_conda': ('research/c6/p01/netlists/nl_conda_v2c04.json', 'v2c04', 'control design armed state 0x04, conda Yosys 0.38+92'),
    'v2c4d_apt': ('research/c6/p01/netlists/nl_apt_v2c4d.json', 'v2c4d', 'control design armed state 0x4D, apt Yosys 0.33'),
    'v2c4d_conda': ('research/c6/p01/netlists/nl_conda_v2c4d.json', 'v2c4d', 'control design armed state 0x4D, conda Yosys 0.38+92'),
    'v2c5a_apt': ('research/c6/p01/netlists/nl_apt_v2c5a.json', 'v2c5a', 'control design armed state 0x5A, apt Yosys 0.33'),
    'v2c5a_conda': ('research/c6/p01/netlists/nl_conda_v2c5a.json', 'v2c5a', 'control design armed state 0x5A, conda Yosys 0.38+92'),
}
# designs analysed with a goal other than boot_word == 0x96
GOALS = {'v2_stored_ok': dict(goal_out='boot_ok', goal_value=1)}
# the original nine (V0/V1/V2/V2e); the test suite runs every method on these at every budget
CORE = ('v0_stored', 'v1_stored', 'v2_stored', 'v0_apt', 'v1_apt', 'v2_apt', 'v2_conda', 'v2e_apt', 'v2e_conda')
# minimum flips within 6 cycles as recorded in the repository (known power-up, goal boot_word == 0x96)
BOUNDED_RECORDED = {
    'v0_stored': (1, 'results/reproduce_summary.json (spike/given-netlist)'),
    'v1_stored': (1, 'results/reproduce_summary.json (spike/given-netlist)'),
    'v2_stored': (3, 'results/reproduce_summary.json (spike/given-netlist)'),
    'v0_apt': (1, 'results/reproduce_summary.json (rtl/plain)'),
    'v1_apt': (1, 'results/reproduce_summary.json (rtl/plain)'),
    'v2_apt': (2, 'results/reproduce_summary.json (rtl/plain); research/c6/p01/glitchsat_cross.txt'),
    'v2_conda': (3, 'research/c6/p01/glitchsat_cross.txt'),
    'v2e_apt': (3, 'research/c6/p01/glitchsat_cross.txt'),
    'v2e_conda': (3, 'research/c6/p01/glitchsat_cross.txt'),
    'v2_stored_ok': (1, 'docs/NUMBERS.md B2.v2.ok; research/c4/b3/matrix_T6.jsonl (v2, stem_flip, ok)'),
    'v0_apt033': (1, 'research/c4/b3/matrix_T6.jsonl (stem_flip, word)'),
    'v1_apt033': (1, 'research/c4/b3/matrix_T6.jsonl (stem_flip, word)'),
    'v2_apt033': (2, 'research/c4/b3/matrix_T6.jsonl (stem_flip, word); ext/surface/results/surface_v2apt_T6.json'),
    'v5_apt033': (3, 'research/c4/b3/matrix_T6.jsonl (stem_flip, word)'),
    'v2_flowB': (1, 'docs/NUMBERS.md V.flowB; ext/surface/results/surface_v2flowB_T6.json'),
    'v2_inbuf': (1, 'ext/surface/results/surface_v2inbuf_T6.json'),
    'v2c04_apt': (1, 'research/c6/p01/sweep_summary.txt (plain flow)'),
    'v2c04_conda': (1, 'research/c6/p01/sweep_summary.txt (plain flow)'),
    'v2c4d_apt': (2, 'research/c6/p01/sweep_summary.txt (plain flow)'),
    'v2c4d_conda': (3, 'research/c6/p01/sweep_summary.txt (plain flow)'),
    'v2c5a_apt': (3, 'research/c6/p01/sweep_summary.txt (plain flow)'),
    'v2c5a_conda': (3, 'research/c6/p01/sweep_summary.txt (plain flow)'),
}


# finished exhaustive enumeration of every minimum attack within a bound (ext/surface/results), per design
SURFACE = {'v0_stored': 'surface_v0_T6.json', 'v1_stored': 'surface_v1_T6.json', 'v2_stored': 'surface_v2_T6.json',
           'v2_apt033': 'surface_v2apt_T6.json', 'v2_flowB': 'surface_v2flowB_T6.json', 'v2_inbuf': 'surface_v2inbuf_T6.json'}


def surface_dir():
    d = os.environ.get('GLITCHSAT_SURFACE_RESULTS')
    if d:
        return d
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'surface', 'results')


def surface_crosscheck(P, path, max_attacks=None):
    """Compare with one ext/surface result (every minimum attack within its cycle bound, found by its own exhaustive
    enumerator). Checks: (1) its minimum equals the explicit bounded minimum here for the same bound; (2) every listed
    attack, replayed in this tool's own simulator, reaches the goal for exactly the number of wrong inputs it lists."""
    d = json.load(open(path))
    T, kmax = d['bound']['cycles'], d['bound']['max_faults']
    by_name = {}
    for b, nm in P.nl.names.items():
        by_name.setdefault(nm, b)
    inputs = list(P.oracle.input_values())
    atk = d.get('attacks', [])[:max_attacks] if max_attacks else d.get('attacks', [])
    bad = []
    for a in atk:
        fs = [(t, by_name[nm] if nm in by_name else int(nm)) for nm, t in a['faults']]   # unnamed nets are listed by id
        n = sum(1 for x in inputs if any(P.oracle.simulate(P.onet.init_state, x, fs, T)[0]))
        if n != a['inputs']:
            bad.append(dict(faults=a['faults'], listed_inputs=a['inputs'], replayed_inputs=n))
    here = P.oracle.bounded(kmax, T)
    return dict(file=os.path.basename(path), cycles=T, max_faults=kmax, surface_min=d.get('min_faults'),
                surface_count=d.get('count'), surface_complete=d.get('complete'), explicit_bounded_min_here=here,
                attacks_replayed=len(atk), replay_mismatches=bad,
                consistent=(here == d.get('min_faults')) and not bad)


class Disagreement(Exception):
    pass


def sha16(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]


class Problem:
    """One netlist with one goal: holds the engine netlist (solver path) and the oracle (explicit path)."""
    def __init__(self, path, top, goal_out='boot_word', goal_value=0x96, goal_mask=None, attack_in='sig', key=0xC3,
                 input_sites=False):
        self.path, self.top = path, top
        self.kw = dict(goal_out=goal_out, goal_value=goal_value, goal_mask=goal_mask, attack_in=attack_in, key=key,
                       input_sites=input_sites)
        self.gs = tsmod.load_engine()
        self.nl = self.gs.Netlist(path, top)
        self.onet = omod.Net(path, top)
        self.oracle = omod.Oracle(self.onet, **self.kw)
        # the two readers may order flops and input bits differently: translate by net id
        self.o_q = {q: i for i, q in enumerate(self.onet.qs)}
        self.o_in = {b: i for i, b in enumerate(self.onet.in_bits)}
        self._blocked = None

    def ts(self, k, init_mode='known', honest=False):
        blocked = self.nongoal_blocked() if init_mode == 'free_nongoal' else None
        return tsmod.TS(self.nl, k, init_mode=init_mode, honest=honest, init_blocked=blocked, **self.kw)

    def nongoal_blocked(self):
        """(state, input) pairs excluded from power-up under 'free_nongoal': the fault-free run from there shows the
        goal at some time. Computed by the explicit simulator; in TS bit order."""
        if self._blocked is None:
            T = tsmod.TS(self.nl, 0, **self.kw)
            out = []
            for inp in self.oracle.input_values():
                for s in self.oracle.fault_free_accepting(inp):
                    out.append((self.to_ts_state(T, s), self.to_ts_input(T, inp)))
            self._blocked = out
        return self._blocked

    def to_ts_state(self, T, s):
        return sum(1 << i for i, q in enumerate(T.qs) if (s >> self.o_q[q]) & 1)

    def to_ts_input(self, T, x):
        return sum(1 << i for i, b in enumerate(T.in_bits) if (x >> self.o_in[b]) & 1)

    def from_ts(self, T, flops, inp):
        s = sum(1 << self.o_q[q] for i, q in enumerate(T.qs) if (flops >> i) & 1)
        x = sum(1 << self.o_in[b] for i, b in enumerate(T.in_bits) if (inp >> i) & 1)
        return s, x

    def replay(self, T, trace):
        """Run a solver-found attack through the explicit simulator. True when the goal value really shows up."""
        if trace['cycles'] == 0:
            return False
        s, x = self.from_ts(T, trace['init_state'], trace['input'])
        hits, _ = self.oracle.simulate(s, x, trace['faults'], trace['cycles'])
        return bool(hits[-1]) or any(hits)

    def describe(self, faults):
        return [dict(cycle=t, net=self.nl.names.get(b, str(b)), net_id=b,
                     kind='flop_Q' if b in self.nl.dq else ('gate_output' if b in self.nl.drivers else 'input'))
                for t, b in faults]


def _admissible_init(P, T, trace, init_mode):
    """The trace's first state is an allowed power-up state under init_mode (checked with the explicit simulator)."""
    s, x = P.from_ts(T, trace['init_state'], trace['input'])
    return s in P.oracle.init_states(x, init_mode)


def run_oracle(P, k, init_mode):
    o = P.oracle
    t0 = time.time()
    r = o.unbounded(k, init_mode)
    out = dict(method='explicit reachability (exhaustive, no solver)', seconds=round(time.time() - t0, 3),
               reachable_state_input_pairs=r['reachable_pairs'])
    if r['min_faults'] is None:
        out['verdict'] = 'proved'
        out['note'] = ('fixed point reached: the listed number of (flop state, input) pairs is everything reachable with '
                       f'<= {k} flips, and none of them, with any remaining flips, shows the goal')
    else:
        w = r['witness']
        hits, _ = o.simulate(w['init_state'], w['input'], w['faults'], w['cycles'])
        out.update(verdict='attack', min_faults=r['min_faults'], faults=P.describe(w['faults']), cycles=w['cycles'],
                   attacker_input=P.onet.unpack_input(w['input']), init_state=w['init_state'], replayed=bool(hits[-1]))
    return out, r


def run_kind(P, k, init_mode, backend, deadline, simple_path=True, max_depth=40):
    T = P.ts(k, init_mode)
    r = kind.k_induction(T, lambda: sat.make_backend(backend), max_depth=max_depth, simple_path=simple_path, deadline=deadline)
    tr = r.pop('trace', None)
    fails = r.pop('step_failures')
    r['step_failed_at_depths'] = len(fails)
    if fails and not simple_path:
        f = fails[-1]
        r['last_step_counterexample'] = dict(depth=f['depth'], start_flops='0x%X' % f['start_flops'], start_used=f['start_used'],
                                             repeats_a_state=f['repeats_a_state'])
    if tr:
        r.update(faults=P.describe(tr['faults']), flips_used=len(tr['faults']), cycles=tr['cycles'],
                 replayed=P.replay(T, tr) and _admissible_init(P, T, tr, init_mode))
    return r


def run_ic3(P, k, init_mode, backend, deadline, reach=None):
    T = P.ts(k, init_mode)
    mk = lambda: sat.make_backend(backend)
    r = ic3mod.ic3(T, mk, deadline=deadline)
    tr = r.pop('trace', None)
    inv = r.pop('invariant', None)
    if tr:
        r.update(faults=P.describe(tr['faults']), flips_used=len(tr['faults']), cycles=tr['cycles'],
                 replayed=P.replay(T, tr) and _admissible_init(P, T, tr, init_mode))
    if inv is not None:
        seen, uniq = set(), []
        for c in inv:
            key = tuple(sorted(c))
            if key not in seen:
                seen.add(key); uniq.append(c)
        inv = uniq
        r['invariant_clauses'] = len(inv)
        r['invariant'] = [' | '.join(T.lit_name(l) for l in c) for c in inv]
        r['certificate'] = ic3mod.check_certificate(T, inv, mk, deadline=deadline)
        ind = kind.k_induction(T, mk, max_depth=0, simple_path=False, invariant=inv, deadline=deadline)
        r['plain_induction_with_this_invariant'] = dict(verdict=ind['verdict'], depth=ind['depth'], seconds=ind['seconds'])
        if reach is not None:      # every state the explicit search reached must satisfy every clause
            bad = 0
            for inp, cost in reach.items():
                xi = P.to_ts_input(T, inp)
                for s, c in cost.items():
                    si = P.to_ts_state(T, s)
                    for used in range(c, k + 1):
                        if not all(T.state_holds(cl, si, xi, used) for cl in inv):
                            bad += 1
            r['invariant_holds_on_all_explicitly_reached_states'] = (bad == 0)
    return r


def analyse(P, k, init_mode='known', methods=('oracle', 'kind', 'ic3'), backend='auto', timeout_s=600, plain_depth=0):
    """Run the chosen methods for one budget and one power-up assumption. Raises Disagreement if verdicts differ."""
    res = dict(init=init_mode, methods={})
    reach = None
    if init_mode == 'free_nongoal':
        # non-vacuity: at least one (power-up state, input) pair must be admissible, else "proved" would mean nothing
        n_in = sum(1 for _ in P.oracle.input_values())
        adm = (1 << len(P.onet.qs)) * n_in - len(P.nongoal_blocked())
        res['admissible_power_up_pairs'] = adm
        if adm == 0:
            res.update(verdict='VACUOUS', seconds={}, note='no power-up state is admissible under free_nongoal')
            return res
    if 'oracle' in methods:
        try:
            res['methods']['oracle'], raw = run_oracle(P, k, init_mode)
            reach = raw['reach'] if raw['min_faults'] is None else None
        except omod.OracleError as e:
            res['methods']['oracle'] = dict(verdict='unknown', reason=str(e))
    if 'kind' in methods:
        res['methods']['k_induction_simple_path'] = run_kind(P, k, init_mode, backend, time.time() + timeout_s)
    if plain_depth:
        r = run_kind(P, k, init_mode, backend, time.time() + timeout_s, simple_path=False, max_depth=plain_depth)
        r['method'] = 'k-induction without simple-path constraints (shown for comparison; not used for the verdict)'
        res['plain_k_induction'] = r
    if 'ic3' in methods:
        res['methods']['ic3'] = run_ic3(P, k, init_mode, backend, time.time() + timeout_s, reach)
    vs = {m: r['verdict'] for m, r in res['methods'].items()}
    decided = {v for v in vs.values() if v != 'unknown'}
    problems = []
    if len(decided) > 1:
        problems.append(f'methods disagree: {vs}')
    for m, r in res['methods'].items():
        if r['verdict'] == 'attack' and r.get('replayed') is False:
            problems.append(f'{m}: attack trace does not replay in the simulator')
        if r['verdict'] == 'attack' and r.get('flips_used', r.get('min_faults', 0)) > k:
            problems.append(f'{m}: attack uses more than {k} flips')
        cert = r.get('certificate')
        if cert is not None and cert.get('ok') is not True:
            problems.append(f'{m}: invariant failed its independent re-check: {cert}')
        if r.get('invariant_holds_on_all_explicitly_reached_states') is False:
            problems.append(f'{m}: invariant excludes a state the explicit search reached')
    if problems:
        raise Disagreement('; '.join(problems) + f' (k={k}, init={init_mode})')
    v = decided.pop() if decided else 'unknown'
    res['verdict'] = {'proved': 'PROVED_UNBOUNDED', 'attack': 'ATTACK_FOUND', 'unknown': 'UNKNOWN'}[v]
    res['seconds'] = {m: r.get('seconds') for m, r in res['methods'].items()}
    return res


def honest_boots(P, backend):
    """Sanity (non-vacuity): with input == key and no flips the goal IS reached, by the solver path and the simulator."""
    T = P.ts(0, 'known', honest=True)
    r = kind.k_induction(T, lambda: sat.make_backend(backend), max_depth=20, simple_path=True)
    x = P.onet.input_value({P.kw['attack_in']: P.kw['key']})
    hits, _ = P.oracle.simulate(P.onet.init_state, x, [], 20)
    return dict(solver=(r['verdict'] == 'attack'), simulator=any(hits))


def report(P, name, origin, k, scopes, backend, root=None):
    T = P.ts(k)
    main = scopes[0]
    return dict(
        label='MEASURED', tool=f'ext/unbounded/src/unbounded.py {__version__}', design=name, origin=origin,
        netlist=os.path.relpath(P.path, root) if root else P.path, netlist_sha256_16=sha16(P.path), top=P.top,
        max_faults=k, verdict=main['verdict'], verdict_init=main['init'],
        scope=dict(time='any number of clock cycles (unbounded)', max_faults=k,
                   fault_model='single-cycle bit flip of any gate output or flop Q net' + (' or input net' if P.kw['input_sites'] else ''),
                   count_rule='stem (one flipped net = one fault, whatever its fan-out)',
                   attacker_input=f"`{P.kw['attack_in']}` free, held constant, != key 0x{P.kw['key']:02X}",
                   goal=f"{P.kw['goal_out']} == 0x{P.kw['goal_value']:X}" + (f" on mask 0x{P.kw['goal_mask']:X}" if P.kw['goal_mask'] is not None else '') + ' at some cycle',
                   init='known = flops power up at their netlist init value; arbitrary = any power-up state; '
                        'free_nongoal = any power-up state from which the fault-free run never shows the goal'),
        note=SCOPE_NOTE.format(k=k, ins=' and input nets' if P.kw['input_sites'] else ''),
        netlist_stats=dict(P.nl.stats(), **T.stats()), backend=backend, backends_available=sat.available_backends(),
        python=sys.version.split()[0], scopes=scopes)


def cmd_all(args):
    root = sat.find_repo_root()
    if not root:
        print('repository root not found (need scripts/glitchsat.py); set GLITCHSAT_ROOT', file=sys.stderr); return 3
    os.makedirs(args.out_dir, exist_ok=True)
    backend = sat.make_backend(args.backend).name
    rows, bad = [], []
    for name, (rel, top, origin) in DESIGNS.items():
        if args.only and name not in args.only.split(','):
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            print(f'{name}: netlist {rel} not found, skipped'); continue
        P = Problem(path, top, **GOALS.get(name, {}))
        hb = honest_boots(P, args.backend)
        t0 = time.time()
        b6 = P.oracle.bounded(min(args.kmax, 3), 6)
        b6_s = round(time.time() - t0, 3)
        mins = {}
        for k in range(args.kmax + 1):
            scopes = []
            for init_mode in args.inits.split(','):
                try:
                    r = analyse(P, k, init_mode, methods=tuple(args.methods.split(',')), backend=args.backend, timeout_s=args.timeout,
                                plain_depth=args.plain_depth if init_mode == 'known' else 0)
                except Disagreement as e:
                    print('INCONSISTENT', name, e); bad.append(f'{name}: {e}'); continue
                scopes.append(r)
                if r['verdict'] == 'ATTACK_FOUND':
                    mins.setdefault(init_mode, k)
                rows.append(dict(design=name, k=k, init=init_mode, verdict=r['verdict'], seconds=r['seconds'],
                                 **({'plain_k_induction': r['plain_k_induction']['verdict']} if 'plain_k_induction' in r else {})))
                print(f"{name:10s} k={k} init={init_mode:12s} {r['verdict']:16s} " +
                      ' '.join(f"{m}={v['verdict']}/{v.get('seconds')}s" for m, v in r['methods'].items()), flush=True)
            if not scopes:
                continue
            d = report(P, name, origin, k, scopes, backend, root)
            d['honest_key_boots_fault_free'] = hb
            json.dump(d, open(os.path.join(args.out_dir, f'{name}_k{k}.json'), 'w'), indent=1)
        # consistency with the bounded numbers of the repository
        rec = BOUNDED_RECORDED.get(name)
        unb = mins.get('known')
        chk = dict(design=name, unbounded_min_known_init=unb if unb is not None else f'>{args.kmax}',
                   explicit_min_within_6_cycles=b6 if b6 is not None else f'>{args.kmax}', explicit_bounded_seconds=b6_s,
                   recorded_min_within_6_cycles=rec[0] if rec else None, recorded_source=rec[1] if rec else None,
                   honest_key_boots=hb)
        chk['consistent'] = (unb == b6) and (rec is None or rec[0] == b6) and hb['solver'] and hb['simulator']
        sf = os.path.join(surface_dir(), SURFACE[name]) if name in SURFACE else None
        if sf and os.path.isfile(sf):
            chk['surface'] = surface_crosscheck(P, sf)
            chk['consistent'] = chk['consistent'] and chk['surface']['consistent'] and chk['surface']['surface_min'] == unb
        if not chk['consistent']:
            bad.append(f'{name}: bounded/unbounded mismatch {chk}')
        rows.append(dict(consistency=chk))
        print(f"{name:10s} unbounded min {chk['unbounded_min_known_init']}, 6-cycle min (explicit) {chk['explicit_min_within_6_cycles']}, "
              f"recorded {chk['recorded_min_within_6_cycles']}: {'consistent' if chk['consistent'] else 'MISMATCH'}", flush=True)
    summary = dict(label='MEASURED', tool=f'ext/unbounded/src/unbounded.py {__version__}', backend=backend,
                   backends_available=sat.available_backends(), python=sys.version.split()[0], kmax=args.kmax,
                   inits=args.inits.split(','), problems=bad,
                   rows=[r for r in rows if 'consistency' not in r], consistency=[r['consistency'] for r in rows if 'consistency' in r])
    suffix = '' if backend == 'minicdcl' else '_' + backend.replace(':', '_')
    json.dump(summary, open(os.path.join(args.out_dir, f'summary{suffix}.json'), 'w'), indent=1)
    print('problems:', bad if bad else 'none')
    return 4 if bad else 0


def cmd_compare(args):
    """Every (design, k, init) cell present in two or more summaries must have the same decided verdict."""
    cells = {}
    for f in args.summaries:
        d = json.load(open(f))
        for r in d['rows']:
            cells.setdefault((r['design'], r['k'], r['init']), {})[f'{f} ({d["backend"]})'] = r['verdict']
    shared = {c: v for c, v in cells.items() if len(v) > 1}
    bad = {c: v for c, v in shared.items() if len({x for x in v.values() if x in ('PROVED_UNBOUNDED', 'ATTACK_FOUND')}) > 1}
    unknown = {c: v for c, v in shared.items() if 'UNKNOWN' in v.values()}
    print(f'cells in more than one file: {len(shared)}; disagreements: {len(bad)}; with an UNKNOWN somewhere: {len(unknown)}')
    for c, v in sorted(bad.items()):
        print('  DISAGREE', c, v)
    for c, v in sorted(unknown.items()):
        print('  unknown ', c, v)
    return 4 if bad else 0


def cmd_check(args):
    try:
        P = Problem(args.netlist, args.top, goal_out=args.goal_out, goal_value=args.goal_value, goal_mask=args.goal_mask,
                    attack_in=args.attack_in, key=args.key, input_sites=args.input_sites)
        methods = ('oracle', 'kind', 'ic3') if args.method == 'all' else (args.method,)
        r = analyse(P, args.k, args.init, methods=methods, backend=args.backend, timeout_s=args.timeout,
                    plain_depth=args.plain_depth)
    except Disagreement as e:
        print('INCONSISTENT (no verdict):', e, file=sys.stderr); return 4
    except (omod.OracleError, tsmod.TSError, sat.BackendError, OSError, KeyError) as e:
        print('error:', e, file=sys.stderr); return 3
    except Exception as e:
        if type(e).__name__ in ('NetlistError', 'UnsupportedCell'):
            print('error:', e, file=sys.stderr); return 3
        raise
    d = report(P, os.path.basename(args.netlist), 'given netlist', args.k, [r], sat.make_backend(args.backend).name)
    print(f"{args.top}: {r['verdict']}  (<= {args.k} flips, any number of cycles, init {args.init})")
    for m, v in r['methods'].items():
        extra = ''
        if v['verdict'] == 'attack':
            extra = '  flips: ' + ', '.join(f"{f['net']}@{f['cycle']}" for f in v['faults'])
        elif m == 'ic3' and v['verdict'] == 'proved':
            extra = f"  invariant: {v['invariant_clauses']} clauses, re-check ok={v['certificate']['ok']}"
        elif m == 'k_induction_simple_path' and v['verdict'] == 'proved':
            extra = f"  inductive at depth {v['depth']}"
        print(f"  {m:26s} {v['verdict']:8s} {v.get('seconds')} s{extra}")
    print(d['note'])
    if args.out:
        json.dump(d, open(args.out, 'w'), indent=1)
    return 0 if r['verdict'] in ('PROVED_UNBOUNDED', 'ATTACK_FOUND') else 2


def main(argv=None):
    ap = argparse.ArgumentParser(prog='unbounded.py', description=__doc__.split('\n\n')[0],
                                 epilog='exit codes: 0 verdict printed; 2 unknown; 3 input error; 4 methods disagree (no verdict)')
    ap.add_argument('--version', action='version', version=f'GlitchSAT unbounded analysis {__version__}')
    sp = ap.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('check', help='one netlist, one budget')
    c.add_argument('netlist'); c.add_argument('--top', required=True); c.add_argument('--k', type=int, required=True)
    c.add_argument('--init', choices=['known', 'arbitrary', 'free_nongoal'], default='known')
    c.add_argument('--method', choices=['all', 'oracle', 'kind', 'ic3'], default='all')
    c.add_argument('--goal-out', default='boot_word'); c.add_argument('--goal-value', type=lambda s: int(s, 0), default=0x96)
    c.add_argument('--goal-mask', type=lambda s: int(s, 0), default=None)
    c.add_argument('--attack-in', default='sig'); c.add_argument('--key', type=lambda s: int(s, 0), default=0xC3)
    c.add_argument('--input-sites', action='store_true', help='input nets are fault sites too')
    c.add_argument('--out', help='write the JSON report here')
    a = sp.add_parser('all', help='every reference design, k = 0..kmax, one JSON per design and budget')
    a.add_argument('--out-dir', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results'))
    a.add_argument('--kmax', type=int, default=3); a.add_argument('--only', help='comma-separated design names')
    a.add_argument('--inits', default='known,arbitrary,free_nongoal')
    a.add_argument('--methods', default='oracle,kind,ic3', help='comma-separated subset of oracle,kind,ic3 (default all three)')
    cp = sp.add_parser('compare', help='compare verdicts of two or more summary JSON files (e.g. minicdcl vs pysat vs z3)')
    cp.add_argument('summaries', nargs='+')
    for p in (c, a):
        p.add_argument('--backend', default='auto', help='auto, minicdcl, pysat, pysat:NAME, z3 (default auto)')
        p.add_argument('--timeout', type=float, default=600, help='seconds per solver method (default 600)')
        p.add_argument('--plain-depth', type=int, default=0, help='also run k-induction WITHOUT simple-path constraints up to this depth')
    args = ap.parse_args(argv)
    if args.cmd == 'compare':
        return cmd_compare(args)
    if args.k < 0 if args.cmd == 'check' else args.kmax < 0:
        print('error: budget must be >= 0', file=sys.stderr); return 3
    try:
        return cmd_check(args) if args.cmd == 'check' else cmd_all(args)
    except sat.BackendError as e:
        print('error:', e, file=sys.stderr); return 3


if __name__ == '__main__':
    sys.exit(main())
