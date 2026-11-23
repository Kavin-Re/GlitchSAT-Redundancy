"""Exhaustive attack-surface tests (no z3). Expected counts are anchored to independent files in the repository:
validation/VALIDATION.md (V0 19 single flips at T=6, V1 exactly `ok`@1, V2 0 singles and 0 of 103,740 pairs at T=6,
182 triples in cycle 1) and research/c6/p12/enum.json (T=4 any-key counts: V0 15, V1 1, V2-stored 182 triples,
V2-apt 3 pairs)."""
import json, math
import numpy as np
import pytest
import attack_surface as AS
import merge_lint

V0, V1, V2 = 'reference/spike_netlists/v0.json', 'reference/spike_netlists/v1.json', 'reference/spike_netlists/v2.json'
V2APT = 'research/c4/b3_inputs/nl/v2_apt033.json'


def nl_of(path, rel, top):
    return merge_lint.engine().Netlist(path(rel), top)


@pytest.mark.parametrize('rel,top,N,m,count', [(V0, 'v0', 6, 1, 19), (V0, 'v0', 4, 1, 15), (V1, 'v1', 6, 1, 1),
                                               (V1, 'v1', 4, 1, 1), (V2APT, 'v2', 4, 2, 3)])
def test_minimum_attack_counts(path, rel, top, N, m, count):
    r = AS.exhaustive(nl_of(path, rel, top), N, 3)
    assert r['verdict'] == 'ATTACK_FOUND' and r['min_faults'] == m and len(r['attacks']) == count and r['complete']


def test_v1_single_attack_is_ok_at_cycle_1(path):
    nl = nl_of(path, V1, 'v1')
    r = AS.exhaustive(nl, 6, 1)
    (faults, n_inputs), = r['attacks']
    assert [(nl.names[b], t) for t, b in faults] == [('ok', 1)] and n_inputs == 255   # all 255 wrong sig values


def test_v2_stored_no_attack_up_to_two_flips_T6(path):
    r = AS.exhaustive(nl_of(path, V2, 'v2'), 6, 2)
    assert r['verdict'] == 'NO_ATTACK_UP_TO_BOUND' and r['complete'] and r['sites'] == 353
    assert r['sets_simulated'] == 1 + 353 + math.comb(353, 2)


def test_v2_stored_182_triples_T4(path):
    r = AS.exhaustive(nl_of(path, V2, 'v2'), 4, 3)
    assert r['min_faults'] == 3 and len(r['attacks']) == 182 and r['complete']


@pytest.mark.slow
def test_v2_stored_182_triples_T6_all_cycles(path):
    nl = nl_of(path, V2, 'v2')
    r = AS.exhaustive(nl, 6, 3)
    assert r['min_faults'] == 3 and len(r['attacks']) == 182 and r['complete']
    assert {t for a, _ in r['attacks'] for t, _ in a} == {1}


def test_recorded_witness_replays(path):
    """results/reproduce/v2_spike_given-netlist_k3.json: faults net ids 72, 78, 85 at cycle 1, sig 3."""
    nl = nl_of(path, V2, 'v2')
    rec = json.load(open(path('results/reproduce/v2_spike_given-netlist_k3.json')))
    sim = AS.Sim(nl, 6)
    idx = np.array([[sim.site_index[(f['cycle'], f['net_id'])] for f in rec['faults']]])
    lanes = sim.run(idx)
    sig = rec['attacker_input_raw']['sig']
    assert (int(lanes[0, sig // 64]) >> (sig % 64)) & 1


@pytest.mark.parametrize('rel,top', [(V0, 'v0'), (V1, 'v1'), (V2, 'v2')])
def test_honest_key_boots_and_no_fault_free_attack(path, rel, top):
    sim = AS.Sim(nl_of(path, rel, top), 6)
    assert sim.honest_boots()
    assert not sim.run(np.zeros((1, 0), dtype=np.int64)).any()


def test_minimum_set_does_not_depend_on_reduction(path):
    nl = nl_of(path, V0, 'v0')
    sets = [{frozenset(a) for a, _ in AS.exhaustive(nl, 6, 2, reduce=red)['attacks']} for red in ('none', 'coi', 'full')]
    assert sets[0] == sets[1] == sets[2] and len(sets[0]) == 19


def test_cap_and_timeout_mark_incomplete(path):
    nl = nl_of(path, V0, 'v0')
    r = AS.exhaustive(nl, 6, 3, cap=5)
    assert len(r['attacks']) == 5 and not r['complete'] and r['stop_reason'] == 'cap'
    r = AS.exhaustive(nl_of(path, V2, 'v2'), 6, 3, timeout_s=0.01, batch=1000)
    assert r['verdict'] == 'INCOMPLETE' and not r['complete'] and r['min_faults'] is None


def test_json_summary_schema(path):
    out = AS.run(path(V2), 'v2', 4, 3, method='exhaustive')
    for k in ('schema', 'method', 'bound', 'verdict', 'min_faults', 'count', 'complete', 'stop_reason', 'nets', 'cycles',
              'copies', 'copies_touched', 'attacks', 'note', 'netlist_sha256'):
        assert k in out
    assert out['method'] == 'exhaustive' and out['count'] == 182 and out['copy_source'] == 'names'
    assert out['copies_touched'] == {'3': 182}
    top = {n['net']: n['count'] for n in out['nets'][:4]}
    assert top == {'c1.m': 44, 'c2.m': 44, 'c0.m': 36, 'word[0]': 36}
    assert sum(v['faults'] for v in out['copies'].values()) == 3 * 182
    json.dumps(out)


def test_cli_exhaustive(path, tmp_path, capsys):
    f = tmp_path / 'o.json'
    assert AS.main([path(V1), '--top', 'v1', '--cycles', '6', '--k', '1', '--method', 'exhaustive', '--json', str(f)]) == 0
    d = json.load(open(f))
    assert d['count'] == 1 and d['nets'][0]['net'] == 'ok' and d['nets'][0]['copy'] == 'merge'


def test_stored_netlist_path_is_repo_relative(path):
    out = AS.run(path(V1), 'v1', 6, 1, method='exhaustive')
    assert out['netlist'] == V1 and not out['netlist'].startswith('/')


def test_truncated_attack_list_is_stated(path):
    out = AS.run(path(V0), 'v0', 6, 1, method='exhaustive', list_limit=5)
    assert out['count'] == 19 and out['attacks_listed'] == 5 and 'TRUNCATED LIST' in out['note']
    full = AS.run(path(V0), 'v0', 6, 1, method='exhaustive')
    assert 'TRUNCATED' not in full['note']


def test_stored_results_have_no_absolute_paths():
    import glob, os
    res = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
    for f in glob.glob(os.path.join(res, '*')):
        with open(f) as fh:
            txt = fh.read()
        assert '/home/' not in txt, f
        if f.endswith('.json') and os.path.basename(f).startswith('surface_'):
            assert not json.loads(txt)['netlist'].startswith('/'), f
