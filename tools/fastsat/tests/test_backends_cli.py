"""Backend selection, the DIMACS and PySAT adapters (with stand-ins: no native solver is needed), time limits, CLI."""
import json, os, subprocess, sys, importlib
import pytest
import glitchsat_sat as S

TESTS = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(os.path.dirname(TESTS), 'scripts', 'glitchsat_sat.py')


def v2(root): return os.path.join(root, 'reference', 'spike_netlists', 'v2.json')


def run_cli(*args, env=None):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run([sys.executable, CLI] + list(args), capture_output=True, text=True, env=e)


@pytest.fixture
def fake_pysat(monkeypatch):
    for m in [m for m in sys.modules if m == 'pysat' or m.startswith('pysat.')]:
        monkeypatch.delitem(sys.modules, m)
    monkeypatch.syspath_prepend(os.path.join(TESTS, 'fake_pysat'))
    import pysat.solvers as ps
    ps.Solver.delay_s = 0.0
    yield ps
    for m in [m for m in sys.modules if m == 'pysat' or m.startswith('pysat.')]:
        sys.modules.pop(m, None)


def test_auto_backend_without_pysat_is_the_bundled_solver(root):
    try:
        import pysat.solvers  # noqa: F401
        pytest.skip('python-sat is installed here')
    except ImportError:
        pass
    assert S.backend_kind('auto') == 'py'
    r = S.run_check(v2(root), 'v2', 3, 6)
    assert r['backend'] == 'sat:minicdcl' and r['min_faults'] == 3
    assert r['design'] == 'reference/spike_netlists/v2.json'
    with pytest.raises(S.NetlistError, match='python-sat is not installed'):
        S.run_check(v2(root), 'v2', 1, 6, backend='pysat:cadical')


def test_dimacs_backend(root, tmp_path, monkeypatch):
    wrapper = tmp_path / 'fakesolver'
    wrapper.write_text(f'#!/bin/sh\nexec {sys.executable} {os.path.join(TESTS, "dimacs_solver.py")} "$@"\n')
    wrapper.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    nl = S.gs.Netlist(v2(root), 'v2')
    v, info, res = S.solve(nl, 6, 3, backend='dimacs:fakesolver')
    assert v == 'ATTACK_FOUND' and len(res['faults']) == 3 and info['backend'] == 'fakesolver' and info['minimum_proved']
    assert S.solve(nl, 6, 2, backend='dimacs:fakesolver')[0] == 'NO_ATTACK_UP_TO_BOUND'
    with pytest.raises(S.NetlistError, match='not found on PATH'):
        S.solve(nl, 6, 2, backend='dimacs:no_such_solver_binary')


def test_dimacs_out_file_is_a_valid_instance(root, tmp_path):
    import minicdcl
    nl = S.gs.Netlist(v2(root), 'v2')
    for k, expect in ((2, False), (3, True)):
        p = tmp_path / f'k{k}.cnf'
        S.solve(nl, 6, k, backend='py', dimacs_out=str(p))
        n, cls = minicdcl.parse_dimacs(p.read_text())
        s = minicdcl.Solver(n)
        for c in cls: s.add_clause(c)
        assert s.solve() is expect


def test_pysat_adapter_with_stand_in(root, fake_pysat):
    nl = S.gs.Netlist(v2(root), 'v2')
    assert S.backend_kind('auto') == 'pysat'
    for b, name in (('auto', 'cadical195'), ('cadical', 'cadical195'), ('pysat:g4', 'glucose4'), ('cd19', 'cadical195')):
        v, info, res = S.solve(nl, 6, 3, backend=b)
        assert v == 'ATTACK_FOUND' and len(res['faults']) == 3 and info['backend'] == name
    rows, info, found = S.sweep(nl, 6, 3, backend='cadical')
    assert [r['verdict'] for r in rows] == ['NO_ATTACK_UP_TO_BOUND'] * 3 + ['ATTACK_FOUND']
    with pytest.raises(S.NetlistError, match='no solver'):
        S.solve(nl, 6, 1, backend='pysat:nosuchsolver')


def test_pysat_time_limit_runs_in_a_child_process(root, fake_pysat):
    nl = S.gs.Netlist(v2(root), 'v2')
    v, info, res = S.solve(nl, 6, 3, backend='cadical', timeout_ms=60000)      # finishes: same answer through the child
    assert v == 'ATTACK_FOUND' and len(res['faults']) == 3 and info['backend'] == 'cadical195' and info['minimum_proved']
    fake_pysat.Solver.delay_s = 5.0                                             # solver "hangs": killed at the limit
    v, info, res = S.solve(nl, 6, 3, backend='cadical', timeout_ms=300)
    assert v == 'UNKNOWN_TIMEOUT' and res is None
    rows, info, found = S.sweep(nl, 6, 3, backend='cadical', timeout_ms=300)
    assert rows == [dict(k=0, verdict='UNKNOWN_TIMEOUT', solve_s=rows[0]['solve_s'])] and found is None
    fake_pysat.Solver.delay_s = 0.0
    rows, info, found = S.sweep(nl, 6, 3, backend='cadical', timeout_ms=60000)
    assert [r['verdict'] for r in rows] == ['NO_ATTACK_UP_TO_BOUND'] * 3 + ['ATTACK_FOUND'] and len(found['faults']) == 3


def test_time_limit_of_bundled_solver_gives_unknown(proxies):
    path, top, p = proxies['tmr2s']
    nl = S.gs.Netlist(path, top)
    v, info, res = S.solve(nl, p['cycles'], 2, backend='py', timeout_ms=200, collapse=False,
                           goal_out=p['goal_out'], goal_value=p['goal_value'], key=p['key'])
    assert v == 'UNKNOWN_TIMEOUT' and res is None


def test_cli_check_json_and_exit_codes(root, tmp_path):
    out = tmp_path / 'r.json'
    r = run_cli('check', v2(root), '--top', 'v2', '--k', '3', '--cycles', '6', '--backend', 'py', '--out', str(out))
    assert r.returncode == 0 and 'ATTACK_FOUND' in r.stdout and 'min faults: 3' in r.stdout and 'BOUNDED, NOT UNBOUNDED' in r.stdout
    d = json.load(open(out))
    assert d['backend'] == 'sat:minicdcl' and d['min_faults'] == 3 and d['verdict'] == 'ATTACK_FOUND'
    r = run_cli('check', v2(root), '--top', 'v2', '--k', '2', '--cycles', '6', '--backend', 'py', '--amk', 'counter', '--card', 'seqcounter', '--no-collapse', '--fault-enc', 'relax', '--reduce', 'none')
    assert r.returncode == 0 and 'NO_ATTACK_UP_TO_BOUND' in r.stdout
    for bad in (['--k', '-1', '--cycles', '6'], ['--k', '1', '--cycles', '0'], ['--k', '1', '--cycles', '6', '--goal-out', 'nope'],
                ['--k', '1', '--cycles', '6', '--goal-value', '0x1FF'], ['--k', '1', '--cycles', '6', '--backend', 'dimacs:no_such_binary_x']):
        r = run_cli('check', v2(root), '--top', 'v2', *bad)
        assert r.returncode == 3 and r.stderr.startswith('error:'), bad
    assert run_cli('check', str(tmp_path / 'missing.json'), '--top', 'v2', '--k', '1', '--cycles', '6').returncode == 3
    assert run_cli('--version').returncode == 0 and run_cli('check', '--help').returncode == 0


def test_cli_timeout_exit_2(proxies):
    path, top, p = proxies['tmr2s']
    r = run_cli('check', path, '--top', top, '--k', '2', '--cycles', '4', '--goal-out', 'gout', '--goal-value', hex(p['goal_value']), '--key', '1',
                '--backend', 'py', '--no-collapse', '--timeout-ms', '200')
    assert r.returncode == 2 and 'UNKNOWN_TIMEOUT' in r.stdout and 'NO_ATTACK' not in r.stdout


def test_cli_sweep_and_cnf(root, tmp_path):
    out = tmp_path / 's.json'
    r = run_cli('sweep', v2(root), '--top', 'v2', '--k', '4', '--cycles', '6', '--backend', 'py', '--out', str(out))
    assert r.returncode == 0
    d = json.load(open(out))
    assert [x['verdict'] for x in d['rows']] == ['NO_ATTACK_UP_TO_BOUND'] * 3 + ['ATTACK_FOUND'] * 2
    assert d['rows'][3]['min_faults'] == 3 and d['rows'][4].get('implied_by') == 3 and len(d['faults']) == 3
    r = run_cli('cnf', v2(root), '--top', 'v2', '--k', '3', '--cycles', '6')
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d['model']['sites_modelled'] == 353 and d['cnf_total']['vars'] > d['cnf_circuit']['vars'] > 0


def test_malformed_netlists_fail_loudly(tmp_path):
    base = {'ports': {'clk': {'direction': 'input', 'bits': [2]}, 'sig': {'direction': 'input', 'bits': [3]}, 'boot_word': {'direction': 'output', 'bits': [5]}},
            'netnames': {}}
    def mk(cells, name):
        p = tmp_path / name
        p.write_text(json.dumps({'modules': {'t': dict(base, cells=cells)}}))
        return str(p)
    und = mk({'g': {'type': '$_AND_', 'connections': {'A': [3], 'B': [9], 'Y': [5]}}}, 'undriven.json')
    xin = mk({'g': {'type': '$_AND_', 'connections': {'A': [3], 'B': ['x'], 'Y': [5]}}}, 'x.json')
    uns = mk({'g': {'type': '$_NAND_', 'connections': {'A': [3], 'B': [3], 'Y': [5]}}}, 'nand.json')
    for p, msg in ((und, 'undriven'), (xin, 'x/z'), (uns, 'unsupported cell')):
        with pytest.raises(S.NetlistError, match=msg):
            S.solve(S.gs.Netlist(p, 't'), 2, 1, backend='py', goal_value=1, key=0)
        assert run_cli('check', p, '--top', 't', '--k', '1', '--cycles', '2', '--goal-value', '1', '--key', '0', '--backend', 'py').returncode == 3
