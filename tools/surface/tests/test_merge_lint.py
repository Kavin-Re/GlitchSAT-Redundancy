import json
import merge_lint as ML

V1, V2 = 'reference/spike_netlists/v1.json', 'reference/spike_netlists/v2.json'


def run(path, rel, top, **kw):
    return ML.lint(ML.load(path(rel), top), netlist_path=path(rel), **kw)


def test_v1_flags_ok_shared_by_both_copies(path):
    r = run(path, V1, 'v1')
    assert r['mode'] == 'names' and r['verdict'] == 'merged'
    ok = [s for s in r['single_points'] if s['net'] == 'ok']
    assert ok and ok[0]['copies'] == ['c1', 'c2'] and ok[0]['kind'] == 'merge' and ok[0]['first']
    assert ok[0]['decision_bits_reached'] == list(range(8))


def test_v2_stored_copies_separate(path):
    r = run(path, V2, 'v2')
    assert r['mode'] == 'names' and r['verdict'] == 'separate'
    assert r['single_points'] == [] and r['shared_nets'] == [] and r['merge_points'] == []
    assert sorted(r['copies']) == ['c0', 'c1', 'c2']
    assert r['identical_copies'] == [['c0', 'c1', 'c2']]   # replicas: fragile under structural hashing
    assert {b['bit']: b['owners'] for b in r['decision_bits']} == {0: ['c0'], 1: ['c1'], 2: ['c2'], 3: ['c0'], 4: ['c1'],
                                                                     5: ['c2'], 6: ['c0'], 7: ['c1']}


def test_v2_stored_structural_mode_recovers_rtl_ownership(path):
    """rtl/v2.v: sel = {m1,m0,m2,m1,m0,m2,m1,m0}, i.e. c0 owns bits 0,3,6, c1 1,4,7, c2 2,5."""
    r = run(path, V2, 'v2', mode='structural', expected_copies=3)
    assert r['structural_groups'] == [[0, 3, 6], [1, 4, 7], [2, 5]] and r['verdict'] == 'separate'


def test_flattened_v2_flow_b_is_merged(path):
    """validation/nl/v2.json (synth -flatten, names gone): VALIDATION.md records 4 single flips that succeed."""
    r = run(path, 'validation/nl/v2.json', 'v2', expected_copies=3)
    assert r['mode'] == 'structural' and r['verdict'] == 'merged' and r['structural_groups'] == [list(range(8))]
    assert run(path, 'validation/nl/v2.json', 'v2')['verdict'] == 'single_group'


def test_given_groups_on_flattened_netlist(path):
    r = run(path, 'validation/nl/v2.json', 'v2', groups=[[0, 3, 6], [1, 4, 7], [2, 5]])
    assert r['verdict'] == 'merged' and r['shared_nets']


def test_lint_is_instant(path):
    assert run(path, V2, 'v2')['runtime_s'] < 1.0


def test_cli_json(path, capsys):
    assert ML.main([path(V1), '--top', 'v1', '--json', '-']) == 0
    d = json.loads(capsys.readouterr().out)
    assert d['schema'] == 'glitchsat-merge-lint/1' and d['verdict'] == 'merged'
