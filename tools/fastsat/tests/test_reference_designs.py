"""V0/V1/V2 stored netlists: recorded results (results/reproduce) and the repository's own exhaustive simulator
(validation/netsim.py, fixed to sig/boot_word/0x96/0xC3)."""
import glob, itertools, json, os, sys
import pytest
import glitchsat_sat as S

EXPECT_MIN = {'v0': 1, 'v1': 1, 'v2': 3}          # reference/spike_netlists at 6 cycles (results/reproduce, docs/NUMBERS.md)


def spike(root, d):
    return os.path.join(root, 'reference', 'spike_netlists', f'{d}.json')


@pytest.fixture(scope='module')
def netsim(root):
    sys.path.insert(0, os.path.join(root, 'validation'))
    import netsim
    return netsim


@pytest.mark.parametrize('d', ['v0', 'v1', 'v2'])
def test_minimum_matches_recorded(d, root):
    nl = S.gs.Netlist(spike(root, d), d)
    for k in range(4):
        v, info, res = S.solve(nl, 6, k, backend='py')
        if k >= EXPECT_MIN[d]:
            assert v == 'ATTACK_FOUND' and len(res['faults']) == EXPECT_MIN[d] and info['minimum_proved']
        else:
            assert v == 'NO_ATTACK_UP_TO_BOUND' and res is None
    assert S.honest_boots(nl, 6) is True


def test_every_reproduce_row_with_a_stored_netlist(root):
    n = 0
    for f in sorted(glob.glob(os.path.join(root, 'results', 'reproduce', '*given-netlist*.json'))):
        d = json.load(open(f))
        r = S.run_check(os.path.join(root, d['netlist_json']), d['top'], d['bound']['max_faults'], d['bound']['cycles'], backend='py')
        assert r['verdict'] == d['verdict'] and r.get('min_faults') == d.get('min_faults'), f
        assert r['bound'] == d['bound'] and r['netlist'] == d['netlist'] and r['note'] == d['note']
        assert r['honest_key_boots_fault_free'] == d['honest_key_boots_fault_free']
        assert r['design_sha256_16'] == d['design_sha256_16'] and r['synth_flow'] == d['synth_flow']
        assert r['model']['sites_total'] == d['model']['sites_total'] and r['model']['sites_modelled'] == d['model']['sites_modelled']
        assert set(d) - set(r) == set() and set(r) - set(d) == {'backend'}        # same result fields, plus "backend"
        assert r['backend'] == 'sat:minicdcl' and r['tool'] == 'glitchsat_sat.py'
        if 'faults' in d:
            assert set(d['faults'][0]) == set(r['faults'][0]) and set(d['explanation']) == set(r['explanation'])
        n += 1
    assert n == 12


@pytest.mark.parametrize('d', ['v0', 'v1', 'v2'])
def test_against_validation_netsim_exhaustive_k1(d, root, netsim):
    """Exhaustive over every (cycle, site) and all 255 wrong sig values with validation/netsim.py."""
    net = netsim.Net(spike(root, d), d); T = 6
    assert netsim.attacks(net, T, {}) == 0                                    # k=0: no attack
    one = any(netsim.attacks(net, T, {t: {b}}) for t in range(T) for b in net.sites)
    assert one == (EXPECT_MIN[d] == 1)
    nl = S.gs.Netlist(spike(root, d), d)
    v, info, res = S.solve(nl, T, 3, backend='py')
    f = {}
    for t, b in res['faults']: f.setdefault(t, set()).add(b)
    lanes = netsim.lane_list(netsim.attacks(net, T, f))                       # the SAT witness replays on netsim
    assert res['inputs']['sig'] in lanes and len(res['faults']) == EXPECT_MIN[d]


def test_v2_exhaustive_k2_T4_netsim(root, netsim):
    """V2, 4 cycles: all 46056 fault pairs x 255 sig values find nothing (validation/k2_v2.log), SAT agrees; and at k=3
    the SAT witness replays, so the minimum at T=4 is exactly 3."""
    net = netsim.Net(spike(root, 'v2'), 'v2'); T = 4
    pairs = [(t, b) for t in range(T) for b in net.sites]
    cnt = 0
    for c in itertools.combinations(pairs, 2):
        f = {}
        for t, b in c: f.setdefault(t, set()).add(b)
        assert netsim.attacks(net, T, f) == 0
        cnt += 1
    assert cnt == 46056
    nl = S.gs.Netlist(spike(root, 'v2'), 'v2')
    assert S.solve(nl, T, 2, backend='py')[0] == 'NO_ATTACK_UP_TO_BOUND'
    v, info, res = S.solve(nl, T, 3, backend='py')
    assert v == 'ATTACK_FOUND' and len(res['faults']) == 3


def test_other_goal_port_numbers_md_b2(root):
    """docs/NUMBERS.md B2.v2.ok: V2 with goal boot_ok == 1 needs 1 flip."""
    r = S.run_check(spike(root, 'v2'), 'v2', 1, 6, goal_out='boot_ok', goal_value=1, backend='py')
    assert r['verdict'] == 'ATTACK_FOUND' and r['min_faults'] == 1
