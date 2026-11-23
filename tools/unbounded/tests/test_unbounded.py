"""Tests of the unbounded analysis. Run from ext/unbounded (GLITCHSAT_ROOT = repository root):  python3 -m pytest tests -q
The solver tests use the pure Python SAT solver, so they need no install."""
import glob, itertools, json, os, random, subprocess, sys, time

import pytest

import ic3 as ic3mod, kind, netgen, oracle as omod, sat, unbounded as U
from conftest import ROOT, HERE

pytestmark = pytest.mark.needs_sat
MK = lambda: sat.make_backend('minicdcl')
# minimum flips for goal boot_word == 0x96, known power-up, as recorded for 6 cycles in the repository
EXPECTED_MIN = {n: v[0] for n, v in U.BOUNDED_RECORDED.items()}


def problem(name, **kw):
    rel, top, _ = U.DESIGNS[name]
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        pytest.skip(f'{rel} not in this checkout')
    return U.Problem(path, top, **dict(U.GOALS.get(name, {}), **kw))


# ---------------------------------------------------------------- reference designs
@pytest.mark.parametrize('name', U.CORE)
def test_reference_design_all_methods_agree_and_match_recorded_minimum(name):
    P = problem(name)
    m = EXPECTED_MIN[name]
    for k in range(0, 4):
        r = U.analyse(P, k, 'known', backend='minicdcl')            # raises Disagreement if the methods differ
        assert r['verdict'] == ('PROVED_UNBOUNDED' if k < m else 'ATTACK_FOUND'), (name, k)
        for meth, v in r['methods'].items():
            if v['verdict'] == 'attack':
                assert v['replayed'] is True
            if meth == 'ic3' and v['verdict'] == 'proved':
                assert v['certificate']['ok'] is True
                assert v['invariant_holds_on_all_explicitly_reached_states'] is True
                assert v['plain_induction_with_this_invariant']['verdict'] == 'proved'


@pytest.mark.parametrize('name', ['v0_stored', 'v1_stored', 'v2_apt'])
def test_explicit_bounded_search_matches_recorded_six_cycle_minimum(name):
    P = problem(name)
    assert P.oracle.bounded(3, 6) == EXPECTED_MIN[name]


@pytest.mark.parametrize('name', sorted(set(U.DESIGNS) - set(U.CORE)))
def test_other_designs_proved_below_recorded_minimum_attack_at_it(name):
    """The extra designs: every method proves m-1 flips safe for all time and finds an m-flip attack."""
    P = problem(name)
    m = EXPECTED_MIN[name]
    r = U.analyse(P, m - 1, 'known', backend='minicdcl')
    assert r['verdict'] == 'PROVED_UNBOUNDED', name
    assert r['methods']['ic3']['certificate']['ok'] is True
    r = U.analyse(P, m, 'known', backend='minicdcl', methods=('oracle', 'ic3'))
    assert r['verdict'] == 'ATTACK_FOUND', name
    assert all(v['replayed'] for v in r['methods'].values())


@pytest.mark.parametrize('name', sorted(U.SURFACE))
def test_agrees_with_surface_enumeration(name):
    """ext/surface lists every minimum attack within 6 cycles (its own enumerator). Its minimum must equal the bounded
    and the unbounded minimum here, and its attacks must replay in this tool's simulator with the same input counts."""
    f = os.path.join(U.surface_dir(), U.SURFACE[name])
    if not os.path.isfile(f):
        pytest.skip('ext/surface results not present')
    P = problem(name)
    r = U.surface_crosscheck(P, f, max_attacks=25)
    assert r['consistent'], r
    assert r['surface_complete'] is True and r['surface_min'] == EXPECTED_MIN[name]


def test_free_nongoal_vacuity_is_reported(tmp_path):
    """A design whose goal output is constantly the goal value: no admissible power-up state, so no 'proved'."""
    doc = netgen.random_netlist(random.Random(5), n_flops=1, n_gates=2)
    mod = doc['modules']['t']
    mod['ports']['boot_word']['bits'] = ['0', '0']
    mod['netnames']['boot_word']['bits'] = ['0', '0']
    p = str(tmp_path / 'c.json'); netgen.write(p, doc)
    P = U.Problem(p, 't', goal_value=0, key=0)
    r = U.analyse(P, 1, 'free_nongoal', backend='minicdcl')
    assert r['verdict'] == 'VACUOUS' and r['admissible_power_up_pairs'] == 0


def test_repository_reproduce_summary_is_consistent_with_unbounded_minimum():
    """Read results/reproduce_summary.json directly: an attack within 6 cycles must also be an unbounded attack, and
    here the unbounded minimum equals the 6-cycle minimum on every row."""
    path = os.path.join(ROOT, 'results', 'reproduce_summary.json')
    if not os.path.isfile(path):
        pytest.skip('results/reproduce_summary.json not in this checkout')
    rows = json.load(open(path))['rows']
    name = {('v0', 'spike/given-netlist'): 'v0_stored', ('v1', 'spike/given-netlist'): 'v1_stored',
            ('v2', 'spike/given-netlist'): 'v2_stored', ('v0', 'rtl/plain'): 'v0_apt', ('v1', 'rtl/plain'): 'v1_apt',
            ('v2', 'rtl/plain'): 'v2_apt'}
    seen = 0
    for r in rows:
        n = name.get((r['design'], r['netlist']))
        if n is None:
            continue
        seen += 1
        m = EXPECTED_MIN[n]
        assert (r['verdict'] == 'ATTACK_FOUND') == (r['k'] >= m), r
        if r['verdict'] == 'ATTACK_FOUND':
            assert r['min_faults'] == m
    assert seen >= 12


def test_honest_key_boots():
    for name in ('v0_stored', 'v1_stored', 'v2_stored'):
        assert U.honest_boots(problem(name), 'minicdcl') == dict(solver=True, simulator=True)


# ---------------------------------------------------------------- power-up and scope options
def test_power_up_assumptions_v2_stored():
    P = problem('v2_stored')
    assert U.analyse(P, 0, 'arbitrary', backend='minicdcl')['verdict'] == 'ATTACK_FOUND'       # may power up accepting
    assert U.analyse(P, 0, 'free_nongoal', backend='minicdcl')['verdict'] == 'PROVED_UNBOUNDED'
    r = U.analyse(P, 1, 'free_nongoal', backend='minicdcl')
    assert r['verdict'] == 'ATTACK_FOUND'
    assert all(v.get('replayed', True) for v in r['methods'].values())


def test_scope_options_goal_flag_and_input_sites():
    rel, top, _ = U.DESIGNS['v2_stored']
    path = os.path.join(ROOT, rel)
    P = U.Problem(path, top, goal_out='boot_ok', goal_value=1)
    assert U.analyse(P, 0, backend='minicdcl')['verdict'] == 'PROVED_UNBOUNDED'
    assert U.analyse(P, 1, backend='minicdcl')['verdict'] == 'ATTACK_FOUND'
    P = U.Problem(path, top, input_sites=True)
    assert U.analyse(P, 0, backend='minicdcl')['verdict'] == 'PROVED_UNBOUNDED'
    assert U.analyse(P, 1, backend='minicdcl')['verdict'] == 'ATTACK_FOUND'
    P = U.Problem(path, top, goal_mask=0x0F)
    lo = min(k for k in range(4) if U.analyse(P, k, backend='minicdcl')['verdict'] == 'ATTACK_FOUND')
    assert 1 <= lo <= 3


# ---------------------------------------------------------------- induction: what fails and what fixes it
def test_plain_k_induction_is_inconclusive_simple_path_and_invariant_fix_it():
    P = problem('v2_stored')
    T = P.ts(2)
    plain = kind.k_induction(T, MK, max_depth=8, simple_path=False)
    assert plain['verdict'] == 'unknown' and len(plain['step_failures']) == 9
    assert plain['step_failures'][-1]['repeats_a_state']             # the counterexample idles in one state
    sp = kind.k_induction(T, MK, max_depth=8, simple_path=True)
    assert sp['verdict'] == 'proved' and sp['depth'] <= 4
    r = ic3mod.ic3(T, MK)
    assert r['verdict'] == 'proved'
    strengthened = kind.k_induction(T, MK, max_depth=0, simple_path=False, invariant=r['invariant'])
    assert strengthened['verdict'] == 'proved' and strengthened['depth'] == 0


def test_certificate_check_rejects_wrong_invariants():
    P = problem('v2_stored')
    T = P.ts(2)
    inv = ic3mod.ic3(T, MK)['invariant']
    assert ic3mod.check_certificate(T, inv, MK)['ok'] is True
    h = T.h_pos + 1
    no_goal = [c for c in inv if c != [-h]]
    assert ic3mod.check_certificate(T, no_goal, MK)['ok'] is False                  # no longer excludes "goal seen"
    weak = [[-h]]
    assert ic3mod.check_certificate(T, weak, MK)['inductive'] is False              # safe but not inductive
    q0 = T.q_pos[0] + 1
    lit = -q0 if P.nl.init[T.qs[0]] else q0
    assert ic3mod.check_certificate(T, inv + [[lit]], MK)['init'] is False          # false at power-up


def test_attack_budget_is_respected_and_minimal():
    P = problem('v2_apt')
    r = U.analyse(P, 2, backend='minicdcl')
    for v in r['methods'].values():
        assert v['verdict'] == 'attack' and v.get('flips_used', v.get('min_faults')) == 2


# ---------------------------------------------------------------- random netlists: three methods and brute force
def naive_bounded(P, kmax, cycles):
    """Every placement of <= kmax flips in `cycles` cycles, one at a time, with the single-run simulator."""
    o = P.oracle
    slots = [(t, b) for t in range(cycles) for b in o.sites]
    for k in range(kmax + 1):
        for fs in itertools.combinations(slots, k):
            for inp in o.input_values():
                hits, _ = o.simulate(o.net.init_state, inp, fs, cycles)
                if any(hits):
                    return k
    return None


def test_random_netlists_methods_agree(tmp_path):
    rng = random.Random(2026)
    verdicts = set()
    for it in range(60):
        doc = netgen.random_netlist(rng, n_flops=rng.randint(1, 4), n_gates=rng.randint(2, 9))
        p = str(tmp_path / 'n.json'); netgen.write(p, doc)
        P = U.Problem(p, 't', goal_value=rng.randrange(4), key=rng.randrange(4), input_sites=rng.random() < 0.3)
        for k in range(3):
            for im in ('known', 'arbitrary', 'free_nongoal'):
                r = U.analyse(P, k, im, backend='minicdcl', timeout_s=60)
                assert r['verdict'] != 'UNKNOWN'
                verdicts.add((im, r['verdict']))
    assert len(verdicts) == 6                                         # both outcomes seen under every power-up option


def test_random_netlists_explicit_search_against_one_run_at_a_time_brute_force(tmp_path):
    rng = random.Random(77)
    for it in range(25):
        doc = netgen.random_netlist(rng, n_flops=rng.randint(1, 3), n_gates=rng.randint(2, 5))
        p = str(tmp_path / 'n.json'); netgen.write(p, doc)
        P = U.Problem(p, 't', goal_value=rng.randrange(4), key=rng.randrange(4))
        nb = naive_bounded(P, 2, 3)
        assert P.oracle.bounded(2, 3) == nb
        unb = P.oracle.unbounded(2)['min_faults']
        if nb is not None:
            assert unb is not None and unb <= nb                      # more time never makes an attack more expensive
        # a tiny machine has few states: 40 cycles cover every loop-free run, so the two numbers must be equal
        assert P.oracle.bounded(2, 40) == unb


# ---------------------------------------------------------------- backends
def test_pysat_adapter_and_core_paths_with_stand_in(monkeypatch):
    """Exercises sat.PySATBackend and the unsat-core branches of IC3 against tests/fake_pysat (NOT the real package)."""
    monkeypatch.syspath_prepend(os.path.join(HERE, 'fake_pysat'))
    for m in [m for m in sys.modules if m == 'pysat' or m.startswith('pysat.')]:
        monkeypatch.delitem(sys.modules, m)
    import pysat.solvers
    if 'fake_pysat' not in pysat.solvers.__file__:
        pytest.skip('real python-sat is installed; the stand-in is not needed')
    b = sat.make_backend('pysat')
    assert b.name == 'pysat:cadical153' and b.has_core
    b.add([1, 2]); b.add([-1, 2])
    assert b.solve([-2]) is False and b.core() == [-2]
    assert b.solve([3]) is True and b.val(2)
    P = problem('v2_stored')
    assert U.analyse(P, 2, backend='pysat')['verdict'] == 'PROVED_UNBOUNDED'
    assert U.analyse(P, 3, backend='pysat')['verdict'] == 'ATTACK_FOUND'
    with pytest.raises(sat.BackendError):
        sat.make_backend('pysat:nosuchsolver')


def test_missing_optional_backends_give_one_line_errors():
    for name, mod in (('z3', 'z3'),):
        try:
            __import__(mod)
        except ImportError:
            with pytest.raises(sat.BackendError):
                sat.make_backend(name)
    with pytest.raises(sat.BackendError):
        sat.make_backend('nonsense')


@pytest.mark.parametrize('backend', ['pysat:cadical153', 'pysat:glucose4', 'z3'])
def test_real_optional_backends_when_installed(backend):
    """Runs only where python-sat / z3-solver are really installed (not on the machine these files were written on)."""
    try:
        b = sat.make_backend(backend)
    except sat.BackendError as e:
        pytest.skip(str(e))
    if 'fake_pysat' in getattr(sys.modules.get('pysat.solvers'), '__file__', '') and backend.startswith('pysat'):
        pytest.skip('stand-in module, not python-sat')
    for name in ('v1_stored', 'v2_stored', 'v2_apt', 'v2e_apt'):
        P = problem(name)
        for k in range(4):
            r = U.analyse(P, k, backend=backend)
            assert r['verdict'] == ('PROVED_UNBOUNDED' if k < EXPECTED_MIN[name] else 'ATTACK_FOUND')


# ---------------------------------------------------------------- CLI and stored results
def run_cli(*args):
    env = dict(os.environ, GLITCHSAT_ROOT=ROOT)
    return subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), 'src', 'unbounded.py'), *args],
                          capture_output=True, text=True, env=env)


def test_cli_verdicts_and_exit_codes(tmp_path):
    nl = os.path.join(ROOT, 'reference', 'spike_netlists', 'v2.json')
    out = str(tmp_path / 'r.json')
    r = run_cli('check', nl, '--top', 'v2', '--k', '2', '--backend', 'minicdcl', '--out', out)
    assert r.returncode == 0 and 'PROVED_UNBOUNDED' in r.stdout and 'UNBOUNDED IN TIME, BOUNDED IN EVERYTHING ELSE' in r.stdout
    d = json.load(open(out))
    assert d['label'] == 'MEASURED' and d['verdict'] == 'PROVED_UNBOUNDED' and d['scope']['max_faults'] == 2
    r = run_cli('check', nl, '--top', 'v2', '--k', '3', '--backend', 'minicdcl', '--method', 'ic3')
    assert r.returncode == 0 and 'ATTACK_FOUND' in r.stdout
    assert run_cli('check', nl, '--top', 'nosuch', '--k', '1').returncode == 3
    assert run_cli('check', str(tmp_path / 'missing.json'), '--top', 'v2', '--k', '1').returncode == 3
    assert run_cli('check', nl, '--top', 'v2', '--k', '-1').returncode == 3
    assert run_cli('--help').returncode == 0


def test_stored_result_files_match_expected_table():
    files = sorted(glob.glob(os.path.join(os.path.dirname(HERE), 'results', 'v*_k*.json')))
    if not files:
        pytest.skip('no stored results')
    assert len(files) == 4 * len(U.DESIGNS)
    for f in files:
        d = json.load(open(f))
        m = EXPECTED_MIN[d['design']]
        assert d['label'] == 'MEASURED'
        assert d['verdict'] == ('PROVED_UNBOUNDED' if d['max_faults'] < m else 'ATTACK_FOUND'), f
        known = d['scopes'][0]
        assert known['init'] == 'known' and len({v['verdict'] for v in known['methods'].values()}) == 1
        path = os.path.join(ROOT, d['netlist'])
        if os.path.isfile(path):
            assert U.sha16(path) == d['netlist_sha256_16'], 'netlist changed since the result was recorded'
    s = json.load(open(os.path.join(os.path.dirname(HERE), 'results', 'summary.json')))
    assert s['problems'] == [] and all(c['consistent'] for c in s['consistency'])


def test_no_solver_needed_for_the_explicit_method():
    P = problem('v2_stored')
    r = U.analyse(P, 2, methods=('oracle',))
    assert r['verdict'] == 'PROVED_UNBOUNDED' and r['methods']['oracle']['reachable_state_input_pairs'] > 1000


# ---------------------------------------------------------------- hard dependency on ext/fastsat
def test_fastsat_dependency_is_the_one_that_produced_the_stored_results():
    path, h, same = sat.minicdcl_info()
    assert os.path.basename(os.path.dirname(os.path.dirname(path))) == 'fastsat' or os.environ.get('GLITCHSAT_MINICDCL_DIR')
    assert same, (f'{path} has sha256 {h}, but results/ were produced with {sat.MINICDCL_SHA256}: '
                  're-run `unbounded.py all` and update MINICDCL_SHA256')
    for f in glob.glob(os.path.join(os.path.dirname(HERE), 'results', 'v*_k*.json')):
        d = json.load(open(f))
        assert d['backend'] == 'minicdcl' and d['verdict_init'] == 'known' and 'scope' in d and d['note'], f


def test_suite_refuses_to_run_without_fastsat(tmp_path):
    import shutil
    dst = tmp_path / 'unbounded'
    shutil.copytree(os.path.dirname(HERE), dst, ignore=shutil.ignore_patterns('results', '__pycache__', '.pytest_cache'))
    env = {k: v for k, v in os.environ.items() if k not in ('GLITCHSAT_MINICDCL_DIR', 'GLITCHSAT_ALLOW_NO_FASTSAT')}
    env['GLITCHSAT_ROOT'] = ROOT
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--collect-only', str(dst / 'tests')],
                       env=env, capture_output=True, text=True, cwd=str(tmp_path))
    if os.path.isfile(os.path.join(ROOT, 'scripts', 'minicdcl.py')):
        pytest.skip('repository itself provides scripts/minicdcl.py')
    assert r.returncode == 3 and 'requires ext/fastsat' in (r.stdout + r.stderr), r.stdout + r.stderr


def test_stored_results_have_no_absolute_paths():
    for f in glob.glob(os.path.join(os.path.dirname(HERE), 'results', '*')):
        if os.path.isfile(f):
            assert '/home/' not in open(f).read(), f
