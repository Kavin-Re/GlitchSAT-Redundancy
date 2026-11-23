"""Module summaries and their composition, symmetry breaking, interval answers, two-core search, CLI."""
import itertools, json, os, subprocess, sys, time
import pytest
import oracle, designs
from gscale import circuit, unroll, reduce as red, cnf, sat, sim, search, modular, symmetry

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'glitchsat_scale.py')


def _min(r):
    return r['hi'] if r['status'] == 'EXACT' else None if r['status'] == 'NO_ATTACK_UP_TO_BOUND' else r['status']


# ---------------------------------------------------------------- modules
@pytest.mark.parametrize('name,want', [('dmr', 2), ('dmrs', 2), ('tmr2', 3), ('par2', 1)])
def test_proxies_through_modules(proxy_problem, name, want):
    P = proxy_problem(name)
    r = search.analyse(P, 3, modules='auto', backend='py')
    assert _min(r) == want and r['lo_by'] == 'modules' and r['modules']
    assert _min(search.analyse(P, 3, modules='none', backend='py')) == want


def test_copies_share_one_summary(proxy_problem):
    """Structurally identical copies and all cycles of a module use one analysed shape (summary reuse)."""
    P = proxy_problem('tmr2')
    U, keep, _ = search.prepare(P)
    A = modular.Abstraction(U, keep, modular.find_modules(P, 'auto'), 3)
    sbox = [I for I in A.inst if I.name[0] in 'ABC']
    assert len(sbox) >= 6 and len({id(I.local) for I in sbox}) == 1


def test_one_flip_summary_is_exact_on_a_small_module(proxy_problem):
    """E1 (error patterns one flip can cause) against brute force over every site and every input of the module."""
    P = proxy_problem('dmrs')
    U, keep, _ = search.prepare(P)
    A = modular.Abstraction(U, keep, modular.find_modules(P, 'auto'), 2)
    L = next(I.local for I in A.inst if I.name.startswith('A@'))
    d = L.dag; W = 1 << L.n_in; mask = (1 << W) - 1
    inw = {n: sum(1 << s for s in range(W) if (s >> j) & 1) for j, n in enumerate(L.inp)}
    v0 = sim.dag_eval(d, inw, mask)
    E = set()
    for a in range(2, len(d)):
        if not d.site[a]: continue
        va = sim.dag_eval(d, inw, mask, {a: mask})
        for s in range(W):
            E.add(sum(1 << i for i, o in enumerate(L.out_nodes) if ((va[o] ^ v0[o]) >> s) & 1))
    assert E - {0} == L.E1 - {0}
    n = len(L.out_nodes)
    assert sum(1 for f in L.facts if f[0] == 'e') == (1 << n) - 1 - len(L.E1 - {0})
    for f in L.facts:                                   # support facts agree with the brute-force set as well
        if f[0] == 'sup': assert not any(all((e >> i) & 1 for i in f[1]) for e in E)


def test_refinement_is_needed_and_converges():
    """Both outputs of the module must be wrong at once. The abstraction first prices that at one flip; realising it
    needs two; the summary fact found for it closes the gap."""
    P, mods = designs.wide_error()
    want = oracle.Oracle(P).min_faults(3)
    assert want == 2
    U, keep, _ = search.prepare(P)
    A = modular.Abstraction(U, keep, mods, 3, eager=False)
    s = sat.Inc(A.e, 'py'); st = {}; ev = []
    got = search.cegar_ascend(P, A, s, 0, 3, lambda *a: ev.append(a), stats=st)
    assert got == 2 and st['refinements'] >= 1 and A.n_facts >= 1
    assert _min(search.analyse(P, 3, modules=mods, backend='py', min_module_sites=1)) == 2


def test_module_lower_bound_never_exceeds_truth(fs, tmp_path):
    """Composition theorem on random problems: for any module partition, the composed formula with no refinement at
    all is satisfiable at the true minimum (so it can never prove a wrong 'no attack')."""
    import random
    from test_scale_core import _random_problem
    rng = random.Random(5); n = 0
    while n < 40:
        P, O, k, want = _random_problem(rng, fs, str(tmp_path / 'n.json'))
        if want in (None, 0): continue
        n += 1
        gates = sorted(P.circ.gates)
        mods = [('m0', {b for b in gates if rng.random() < 0.6})]
        if not mods[0][1]: continue
        U, keep, _ = search.prepare(P)
        A = modular.Abstraction(U, keep, mods, k, eager=rng.random() < 0.5)
        s = sat.Inc(A.e, 'py')
        assert s.solve(A.assume(want)) is True


def test_find_modules_modes(proxy_problem):
    P = proxy_problem('dmr')
    assert {m[0] for m in modular.find_modules(P, 'prefix')} >= {'A', 'B'}
    isl = modular.find_modules(P, 'islands')
    assert len(isl) >= 2 and all(len(v) > 100 for _, v in isl[:2])
    assert modular.find_modules(P, 'none') == []


# ---------------------------------------------------------------- symmetry
def test_symmetry_found_and_minimum_unchanged():
    for w in (2, 3):
        P, mods = designs.tmr(w)
        U, keep, _ = search.prepare(P)
        syms = symmetry.find(U, keep)
        assert syms and all(symmetry.verify(U, keep, s) for s in syms)
        want = oracle.Oracle(P).min_faults(3)
        assert want == 2
        for k in (1, 2, 3):
            a = search.analyse(P, k, modules='none', backend='py', use_symmetry=True)
            b = search.analyse(P, k, modules='none', backend='py')
            assert _min(a) == _min(b) == (want if k >= want else None) and a['symmetry']['automorphisms'] >= 1


def test_symmetry_breaking_cuts_solutions_but_keeps_every_orbit():
    """Count attacks of the minimum size with and without the constraints: fewer with, and every attack found
    without has itself or its image under a found symmetry among those found with."""
    P, _ = designs.tmr(2)
    U, keep, _ = search.prepare(P)
    syms = symmetry.find(U, keep)

    def all_attacks(breaking):
        M = cnf.Model(U, keep, 2)
        if breaking: symmetry.add_breaking(M, syms)
        s = sat.Inc(M.e, 'py'); out = set()
        while s.solve(M.assume(2)):
            m = s.model()
            fs_ = frozenset(i for i, f in M.F.items() if m[f])
            out.add(fs_)
            M.e.add([-M.F[i] if i in fs_ else M.F[i] for i in M.F])
        return out
    full = all_attacks(False); cut = all_attacks(True)
    assert cut < full
    def orbit(f):
        seen = {f}; todo = [f]
        while todo:
            x = todo.pop()
            for s in syms:
                y = frozenset(s.get(i, i) for i in x)
                if y not in seen: seen.add(y); todo.append(y)
        return seen
    assert all(orbit(f) & cut for f in full)


def test_copies_are_not_swapped_when_goal_reads_one_copy(proxy_problem):
    """In the DMR design the goal reads copy A only, so exchanging the copies is not a symmetry and must not be used.
    (Small symmetries that do exist, e.g. between two output bits with the same goal value at cycle 0, may be.)"""
    P = proxy_problem('dmrs')
    U, keep, _ = search.prepare(P)
    mods = dict(modular.find_modules(P, 'prefix'))
    d = U.dag
    for s in symmetry.find(U, keep):
        assert symmetry.verify(U, keep, s)
        assert not any(d.key[i][1] in mods['A'] and d.key[j][1] in mods['B'] for i, j in s.items())
    assert _min(search.analyse(P, 3, modules='none', backend='py', use_symmetry=True)) == 2
    U2, keep2, _ = search.prepare(designs.tmr(2)[0])
    bad = {min(keep2): max(keep2), max(keep2): min(keep2)}
    assert not symmetry.verify(U2, keep2, bad)


# ---------------------------------------------------------------- intervals, two cores, horizons
def test_interval_is_always_valid(proxy_problem):
    """Whatever the time budget, the answer is a valid interval around the true minimum. A fast machine may finish
    every timed run (EXACT), so the unfinished case is forced with a budget that is already used up (time_s=0):
    that does not depend on how fast the machine is."""
    P = proxy_problem('tmr2s'); true = 3
    seen = set()
    for t in (0, 0.3, 1.0, 3.0):
        r = search.analyse(P, 3, time_s=t, modules='none', backend='py')
        seen.add(r['status'])
        assert r['lo'] <= true and (r['hi'] is None or r['hi'] >= true)
        assert r['status'] in ('EXACT', 'INTERVAL', 'LOWER_BOUND_ONLY')
        if r['hi'] is not None: assert sim.is_attack(P, *r['_witness_raw'])
        assert ('between' in r['text']) == (r['status'] == 'INTERVAL')
        assert r['timed_out'] == (r['status'] != 'EXACT')
        if t == 0:
            assert r['status'] != 'EXACT' and r['timed_out'], 'a used-up budget must give an unfinished answer'
    assert seen - {'EXACT'}, 'expected at least one unfinished answer'
    r = search.analyse(P, 3, modules='none', backend='py')       # no time limit: the exact answer
    assert r['status'] == 'EXACT' and r['lo'] == r['hi'] == true and not r['timed_out']


def test_interval_reports_both_ends():
    B = search.Bounds(4); B.raise_lo(2, 'x'); B.lower_hi(4, ({}, []), 'y')
    assert B.status() == 'INTERVAL'
    o = dict(status='INTERVAL', lo=2, hi=4, k=4, cycles=5)
    assert 'between 2 and 4 flips' in search.describe(o)
    B.lower_hi(7, None, 'z'); assert B.hi == 4
    B2 = search.Bounds(3); B2.lower_hi(5, None, 'z'); assert B2.hi is None      # above the asked budget: ignored


@pytest.mark.parametrize('mode', ['race', 'cubes'])
def test_two_workers_agree(proxy_problem, mode):
    for name, want in (('dmrs', 2), ('par2', 1)):
        r = search.analyse(proxy_problem(name), 3, workers=2, mode=mode, modules='none' if mode == 'cubes' else 'auto', backend='py')
        assert _min(r) == want
    P, _ = designs.tmr(3)
    assert search.analyse(P, 1, workers=2, mode=mode, modules='none', backend='py')['status'] == 'NO_ATTACK_UP_TO_BOUND'


def test_cubes_cover_everything(root, fs):
    nl = fs.gs.Netlist(os.path.join(root, 'reference', 'spike_netlists', 'v2.json'), 'v2')
    P = circuit.engine_problem(nl, 6); U, keep, _ = search.prepare(P)
    M = cnf.Model(U, keep, 3)
    sv = search.pick_split(M, 3)
    assert len(sv) == 3 and len(set(sv)) == 3
    pool = search.CubePool(M, 'py', 2)
    try:
        assert pool.solve(M.assume(2))[0] is False and pool.cubes_solved == 8
        r, m = pool.solve(M.assume(3))
        assert r is True and sim.is_attack(P, *M.witness(m))
    finally:
        pool.close()


def test_deepen_equals_separate_runs(root, fs):
    nl = fs.gs.Netlist(os.path.join(root, 'reference', 'spike_netlists', 'v2.json'), 'v2')
    r = search.deepen(circuit.engine_problem(nl, 6), 3, backend='py')
    for row in r['rows']:
        one = search.analyse(circuit.engine_problem(nl, row['cycles']), 3, modules='none', backend='py')
        assert row['proved'] and row['min_faults'] == _min(one)
    assert [x['min_faults'] for x in r['rows']] == [None, None, 3, 3, 3, 3]


# ---------------------------------------------------------------- CLI
def _run(args, root):
    env = dict(os.environ, GLITCHSAT_ROOT=root)
    return subprocess.run([sys.executable, SCRIPT] + args, capture_output=True, text=True, env=env, timeout=300)


def test_cli_check_and_generic_options(root, tmp_path, proxies):
    v2 = os.path.join(root, 'reference', 'spike_netlists', 'v2.json')
    out = tmp_path / 'o.json'
    p = _run(['check', v2, '--top', 'v2', '--k', '3', '--cycles', '6', '--backend', 'py', '--out', str(out)], root)
    assert p.returncode == 0 and 'smallest attack uses 3 flip' in p.stdout and 'BOUNDED' in p.stdout
    r = json.loads(out.read_text())
    assert r['status'] == 'EXACT' and r['lo'] == r['hi'] == 3 and len(r['witness']['faults']) == 3
    p = _run(['check', v2, '--top', 'v2', '--k', '2', '--cycles', '6', '--backend', 'py', '--workers', '2'], root)
    assert p.returncode == 0 and 'NO_ATTACK_UP_TO_BOUND' in p.stdout
    p = _run(['check', v2, '--top', 'v2', '--k', '3', '--cycles', '6', '--backend', 'py', '--goal', 'boot_ok=1'], root)
    assert p.returncode == 0 and 'uses 1 flip' in p.stdout
    p = _run(['check', v2, '--top', 'nope', '--k', '1'], root); assert p.returncode == 3
    p = _run(['check', v2, '--top', 'v2', '--goal', 'nope=1'], root); assert p.returncode == 3
    p = _run(['deepen', v2, '--top', 'v2', '--k', '3', '--cycles', '4', '--backend', 'py'], root)
    assert p.returncode == 0 and p.stdout.count('minimum 3 flip') == 2
    path, top, pr = proxies['dmr']
    p = _run(['sizes', path, '--top', top, '--k', '2', '--cycles', '4', '--goal-out', 'gout', '--goal-value', '0x17c', '--key', '1'], root)
    z = json.loads(p.stdout)
    assert z['time']['fault_vars'] > 10 * z['struct']['fault_vars'] and z['modules']['instances'] > 0


def test_cli_time_limit_gives_interval_exit_2(root, proxies):
    path, top, pr = proxies['tmr2s']
    p = _run(['check', path, '--top', top, '--k', '3', '--cycles', '4', '--goal-out', 'gout', '--goal-value', '0x37c', '--key', '1',
              '--backend', 'py', '--modules', 'none', '--time-s', '0.5'], root)
    assert p.returncode in (0, 2)
    if p.returncode == 2: assert 'not proved' in p.stdout or 'UNDECIDED' in p.stdout


def test_external_dimacs_solver_backend(root, proxy_problem, fs):
    """The dimacs:<binary> path with the bundled solver wrapped as a DIMACS command (any real solver is used the same way)."""
    wrap = os.path.join(os.path.dirname(os.path.dirname(fs.__file__)), 'tests', 'dimacs_solver.py')
    if not os.access(wrap, os.X_OK): pytest.skip('dimacs wrapper of ext/fastsat not executable')
    r = search.analyse(proxy_problem('par2'), 2, modules='auto', backend='dimacs:' + wrap)
    assert _min(r) == 1


def test_partial_model_from_external_solver_is_refused(tmp_path, fs):
    """A solver that leaves variables out of its 'v' lines (CaDiCaL 3 does without --modelalllits=true) must not be
    read as "those variables are false"."""
    fake = tmp_path / 'fakesolver'
    fake.write_text('#!/bin/sh\necho "s SATISFIABLE"\necho "v 1 0"\nexit 10\n'); fake.chmod(0o755)
    e = fs.Encoding(); a = e.new_var(); b = e.new_var(); e.add([a, b])
    s = sat.Inc(e, 'dimacs:' + str(fake))
    with pytest.raises(RuntimeError, match='without 2 of 3 variables'):
        s.solve([])


def test_hierarchy_choice_prefers_the_narrow_copy():
    """Two S-box-like blocks under one generate scope g[0]: the chooser must take g[0].A and g[0].B (8 outputs each),
    not g[0] as a whole, because a module that contains both copies hides exactly the redundancy."""
    b = designs.B(); sig = b.inp('sig', 4)
    outs = []
    for cp in 'AB':
        x = [b.ff(s, name='x%s%d' % (cp, i)) for i, s in enumerate(sig)]
        lvl = x
        for d in range(6):
            lvl = [b.g('XOR' if (d + i) % 2 else 'AND', lvl[i], lvl[(i + 1) % 4]) for i in range(4)]
            for i, y in enumerate(lvl): b.c.cell[y] = '$flatten\\g[0].%s.$abc$%d' % (cp, y)
        outs.append([b.ff(y, name='y%s%d' % (cp, i)) for i, y in enumerate(lvl)])
    neq = None
    for p, q in zip(*outs):
        d = b.g('XOR', p, q, name='chk%d' % p); neq = d if neq is None else b.g('OR', neq, d, name='chkor%d' % d)
    ok = b.g('NOT', neq, name='ok')
    P = circuit.Problem(b.c, 4, [(ok, True), (outs[0][0], True)], label='h')
    names = sorted(m[0] for m in modular.find_modules(P, 'auto', min_sites=8))
    assert names == ['g[0].A', 'g[0].B']
    want = oracle.Oracle(P).min_faults(2, limit=400000)
    r = search.analyse(P, 2, modules='auto', backend='py')
    assert want != 'limit' and _min(r) == want
