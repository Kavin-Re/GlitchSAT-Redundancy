"""bench.py agreement/timing table against z3 (with a stubbed z3 runner: z3 is not installed here), and the
ext/surface exhaustive oracle on the small reference designs (skipped when ext/surface is not next to ext/fastsat)."""
import os, sys
import pytest


def test_bench_z3_table_with_stubbed_runner(root, monkeypatch, capsys):
    import bench
    monkeypatch.setattr(bench, 'z3_available', lambda: True)
    # stand-in for scripts/glitchsat.py check: the real minimum of V1 is 1; at k=2 it reports a wrong minimum, at k=3 a timeout
    fake = {1: dict(verdict='ATTACK_FOUND', min=1, s=0.5), 2: dict(verdict='ATTACK_FOUND', min=2, s=0.5),
            3: dict(verdict='UNKNOWN_TIMEOUT', min=None, s=9.0)}
    monkeypatch.setattr(bench, 'run_z3', lambda d, k, t: fake[k])
    monkeypatch.setattr(sys, 'argv', ['bench.py', '--set', 'core', '--only', 'v1 spike', '--backend', 'py',
                                      '--k', '1', '2', '3', '--z3', '--per-k'])
    with pytest.raises(SystemExit) as e:
        bench.main()
    out = capsys.readouterr().out
    assert e.value.code == 1                                    # a disagreement must fail the run
    assert '| design | gates/flops | T | k | SAT verdict | SAT s | z3 verdict | z3 s | agree |' in out
    assert '| v1 spike | 58/8 | 6 | 1 | ATTACK min 1 |' in out and '| yes |' in out
    assert '| DIFFERENT |' in out and 'n/a (no verdict on one side)' in out
    assert 'agreement with z3: 1 equal, 1 DIFFERENT, 1 not comparable' in out


SMALL = [('reference/spike_netlists/v0.json', 'v0', 6, 1), ('reference/spike_netlists/v1.json', 'v1', 6, 1),
         ('reference/spike_netlists/v2.json', 'v2', 4, 3), ('validation/nl/v2.json', 'v2', 6, 1),
         ('research/c2/reviews/ct/tests/v2_inbuf.json', 'v2', 6, 1), ('research/c4/b3_inputs/nl/v2_apt033.json', 'v2', 6, 2)]


@pytest.mark.parametrize('rel,top,T,expect', SMALL, ids=[f'{t}:{r.split("/")[0]}:T{T}' for r, t, T, _ in SMALL])
def test_surface_oracle_small(root, rel, top, T, expect):
    pytest.importorskip('numpy')
    import verify_surface as V
    if not os.path.isfile(os.path.join(V.SURFACE, 'scripts', 'attack_surface.py')):
        pytest.skip('ext/surface not found (set GLITCHSAT_SURFACE)')
    V.A.update(backend='py', timeout=120, k=3)
    r = V.cell((dict(path=rel, top=top, ports={'sig': ('input', 8), 'boot_word': ('output', 8)}), T))
    assert r['status'] == 'ok', r
    assert r['sat_min'] == r['oracle_min'] == expect and r['witness_in_oracle_set'] is True


def test_bench_z3_table_sweep_path_and_sat_timeout(root, monkeypatch, capsys):
    """Without --per-k the SAT time is the budget's solve time inside the sweep; a SAT-side timeout is 'not comparable'."""
    import bench
    monkeypatch.setattr(bench, 'z3_available', lambda: True)
    monkeypatch.setattr(bench, 'run_z3', lambda d, k, t: dict(verdict='NO_ATTACK_UP_TO_BOUND' if k < 3 else 'ATTACK_FOUND',
                                                               min=3 if k == 3 else None, s=2.0))
    monkeypatch.setattr(sys, 'argv', ['bench.py', '--set', 'core', '--only', 'v2 spike T=12', '--backend', 'py',
                                      '--k', '1', '2', '3', '--z3'])
    with pytest.raises(SystemExit) as e:
        bench.main()
    out = capsys.readouterr().out
    assert e.value.code == 0
    assert '| v2 spike T=12 | 68/8 | 12 | 2 | none |' in out and '| v2 spike T=12 | 68/8 | 12 | 3 | ATTACK min 3 |' in out
    assert 'none 2.0s | none 2.0s | min 3 2.0s | yes/yes/yes |' in out          # z3 columns of the main table
    assert 'agreement with z3: 3 equal, 0 DIFFERENT, 0 not comparable' in out
    # SAT side without a verdict: the cell is reported as not comparable, never as agreement
    a = type('A', (), dict(k=[1], per_k=False))()
    row = dict(name='x', gates=1, flops=1, T=4, sweep=[dict(verdict='NO_ATTACK_UP_TO_BOUND', solve_s=0.1),
                                                      dict(verdict='UNKNOWN_TIMEOUT', solve_s=5.0)],
               per_k={1: dict(verdict='UNKNOWN_TIMEOUT', min=None, z3=dict(verdict='ATTACK_FOUND', min=1, s=1.0), agree=None)})
    t = bench.fmt_z3_table([row], a)
    assert '| x | 1/1 | 4 | 1 | UNKNOWN_TIMEOUT | timeout | ATTACK min 1 | 1.0 | n/a (no verdict on one side) | - |' in t


def _fake_engine(tmp_path, body):
    """A stand-in repository root whose scripts/glitchsat.py writes a result file like the real engine."""
    d = tmp_path / 'fakeroot' / 'scripts'
    d.mkdir(parents=True)
    (d / 'glitchsat.py').write_text('import json, sys, time\na = sys.argv\nout = a[a.index("--out") + 1]\n' + body)
    return str(tmp_path / 'fakeroot')


def test_run_z3_reads_engine_result_file(root, tmp_path, monkeypatch):
    import bench
    fr = _fake_engine(tmp_path, 'k = int(a[a.index("--k") + 1])\n'
                      'assert a[a.index("--goal-value") + 1] == "0x96" and a[a.index("--key") + 1] == "0xc3"\n'
                      'json.dump(dict(verdict="ATTACK_FOUND" if k >= 3 else "NO_ATTACK_UP_TO_BOUND", min_faults=3 if k >= 3 else None,'
                      ' runtime_s=dict(solve_and_minimize=0.25)), open(out, "w"))\n')
    monkeypatch.setattr(bench, 'ROOT', fr)
    d = dict(name='v2', path=os.path.join(root, 'reference/spike_netlists/v2.json'), top='v2', T=6)
    r = bench.run_z3(d, 3, 10)
    assert r['verdict'] == 'ATTACK_FOUND' and r['min'] == 3 and r['s'] == 0.25
    assert bench.run_z3(d, 2, 10)['verdict'] == 'NO_ATTACK_UP_TO_BOUND'


def test_run_z3_crash_and_hang_are_not_verdicts(root, tmp_path, monkeypatch):
    import bench
    d = dict(name='v2', path=os.path.join(root, 'reference/spike_netlists/v2.json'), top='v2', T=6)
    monkeypatch.setattr(bench, 'ROOT', _fake_engine(tmp_path / 'a', 'sys.exit(4)\n'))
    r = bench.run_z3(d, 1, 5)
    assert r['verdict'].startswith('ERROR(exit 4') and r['min'] is None
    monkeypatch.setattr(bench, 'ROOT', _fake_engine(tmp_path / 'b', 'time.sleep(60)\n'))
    r = bench.run_z3(d, 1, -29.5)                    # outer limit = timeout + 30 s = 0.5 s
    assert r['verdict'] == 'TIMEOUT(outer)' and r['min'] is None


def test_surface_recorded_results(root):
    """Every minimum recorded in ext/surface/results/surface_*.json (exhaustive, complete) equals the SAT minimum, and
    the SAT witness is one of the recorded minimum attacks."""
    import verify_surface as V
    if not os.path.isdir(os.path.join(V.SURFACE, 'results')):
        pytest.skip('ext/surface not found (set GLITCHSAT_SURFACE)')
    V.A.update(backend='py', timeout=120, k=3)
    rows = V.recorded_surface()
    assert len(rows) >= 8
    assert all(r['status'] == 'ok' for r in rows), [r for r in rows if r['status'] != 'ok']
    got = {os.path.basename(r['source']): r['sat'] for r in rows}
    assert got['surface_v2_T6.json'] == ['ATTACK_FOUND', 3] and got['surface_v2_T6_k2.json'] == ['NO_ATTACK_UP_TO_BOUND', None]
    assert got['surface_v2apt_T6.json'] == ['ATTACK_FOUND', 2] and got['surface_v0_T6.json'] == ['ATTACK_FOUND', 1]
    assert sum(1 for r in rows if r.get('witness_in_recorded_set')) == sum(1 for r in rows if r['recorded'][0] == 'ATTACK_FOUND')


def test_r20_parameters_match_recorded_runs(root):
    """bench.R20 (used by the cloud run on freshly synthesised netlists) has the goal, key and horizon of the recorded
    z3 runs in research/c3/r20/out/*.json, so the agreement table there compares like with like."""
    import glob, json, re
    import bench
    stem_of = {'dmr': 'sbox_dmr'}
    seen = set()
    for f in sorted(glob.glob(os.path.join(root, 'research', 'c3', 'r20', 'out', '*_k[0-9].json'))):
        b = os.path.basename(f)
        if b.startswith('sc_') or b.startswith('keymem'):
            continue                                  # horizon sweeps and the custom-synth key_mem run are not in bench.R20
        stem = stem_of.get(b.rsplit('_k', 1)[0], b.rsplit('_k', 1)[0])
        d = json.load(open(f))
        top, go, gv, key, T = bench.R20[stem]
        g = re.match(r'(\w+) == (0x[0-9A-Fa-f]+) at some cycle < (\d+)', d['bound']['goal'])
        assert d['top'] == top and g.group(1) == go and int(g.group(2), 16) == gv and int(g.group(3)) == T == d['bound']['cycles'], f
        assert int(re.search(r'key (0x[0-9A-Fa-f]+)', d['bound']['attacker_input']).group(1), 16) == key, f
        seen.add(stem)
    assert seen == set(bench.R20)
