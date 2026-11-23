"""z3 enumeration path: skipped when z3 is not installed. Compares with the exhaustive reference."""
import pytest
z3 = pytest.importorskip('z3')
import attack_surface as AS
import merge_lint

CASES = [('reference/spike_netlists/v0.json', 'v0', 6, 1, 19), ('reference/spike_netlists/v1.json', 'v1', 6, 1, 1),
         ('reference/spike_netlists/v2.json', 'v2', 4, 3, 182), ('research/c4/b3_inputs/nl/v2_apt033.json', 'v2', 4, 2, 3)]


@pytest.mark.parametrize('rel,top,N,m,count', CASES)
def test_sat_matches_exhaustive(path, rel, top, N, m, count):
    nl = merge_lint.engine().Netlist(path(rel), top)
    st = AS.enumerate_sat(nl, N, 3, cap=100000)
    ex = AS.exhaustive(nl, N, 3)
    assert st['min_faults'] == m and st['complete'] and len(st['attacks']) == count
    assert {frozenset(a) for a, _ in st['attacks']} == {frozenset(a) for a, _ in ex['attacks']}
    assert st['confirmed_by_simulation'] == count


def test_sat_no_attack_v2_k2(path):
    nl = merge_lint.engine().Netlist(path('reference/spike_netlists/v2.json'), 'v2')
    st = AS.enumerate_sat(nl, 6, 2)
    assert st['verdict'] == 'NO_ATTACK_UP_TO_BOUND' and st['complete']


def test_sat_cap(path):
    nl = merge_lint.engine().Netlist(path('reference/spike_netlists/v0.json'), 'v0')
    st = AS.enumerate_sat(nl, 6, 3, cap=5)
    assert len(st['attacks']) == 5 and not st['complete'] and st['stop_reason'] == 'cap'


def test_sat_cli_json(path, tmp_path):
    f = tmp_path / 'o.json'
    AS.main([path('reference/spike_netlists/v1.json'), '--top', 'v1', '--k', '1', '--method', 'sat', '--json', str(f)])
    import json
    d = json.load(open(f))
    assert d['method'] == 'sat' and d['count'] == 1 and d['complete'] and d['attacks'][0]['faults'] == [['ok', 1]]
