"""Random small netlists and goals: minimum flips from the SAT backend == exhaustive minimum, for every encoder option."""
import random
import pytest
import glitchsat_sat as S
import bruteforce, netgen

CFGS = [dict(), dict(collapse=False), dict(card='seqcounter', reduce='none'), dict(fault_enc='relax'),
        dict(fault_enc='relax', collapse=False, reduce='coi'), dict(card='seqcounter', fault_enc='relax')]


def one_case(rng, path):
    doc, meta = netgen.random_netlist(rng, *rng.choice([(10, 3, 3), (14, 4, 4), (6, 2, 4)]))
    netgen.write(doc, path)
    try:
        nl = S.gs.Netlist(path, 't')
    except S.NetlistError:
        return None
    T = rng.randint(1, 4); k = rng.randint(0, 3)
    key = rng.randrange(1 << meta['w_sig'])
    ref = bruteforce.Ref(path, 't')
    cand = list(range(1 << meta['w_out'])); rng.shuffle(cand)
    gv = cand[0]
    if rng.random() < 0.7:                         # prefer goals that are not reached without faults (non-trivial minimum)
        for c in cand:
            if not ref.attack_exists(T, 0, c, key)[0]:
                gv = c; break
    m, _, complete = ref.min_faults(T, k, gv, key)
    assert complete
    for cfg in CFGS:
        v, info, res = S.solve(nl, T, k, backend='py', goal_value=gv, key=key, **cfg)
        got = len(res['faults']) if res else None
        assert got == m and (v == 'ATTACK_FOUND') == (m is not None), (cfg, got, m, doc, T, k, gv, key)
        if res:
            assert ref.witness_ok(T, res['faults'], res['inputs'], gv, key)
            assert info['minimum_proved'] is True
    rows, info, found = S.sweep(nl, T, k, backend='py', goal_value=gv, key=key)
    assert [r['verdict'] == 'ATTACK_FOUND' for r in rows] == [m is not None and m <= j for j in range(k + 1)]
    return m


@pytest.mark.parametrize('seed', [11, 12, 13])
def test_fuzz(seed, tmp_path, root):
    rng = random.Random(seed); hist = {}
    for _ in range(250):
        m = one_case(rng, str(tmp_path / 'n.json'))
        hist[m] = hist.get(m, 0) + 1
    assert hist.get(1, 0) > 20 and hist.get(2, 0) > 3 and hist.get(None, 0) > 20      # the sample is not trivial


def test_dominated_site_lemma(tmp_path, root):
    """Direct check of the fault-collapsing lemma for single faults: whatever a dominated flip achieves is achieved by
    no flip or by the dominator flip (per input value, for the goal at any cycle)."""
    rng = random.Random(77); checked = 0
    path = str(tmp_path / 'n.json')
    for _ in range(200):
        doc, meta = netgen.random_netlist(rng, 12, 4, 3)
        netgen.write(doc, path)
        try:
            nl = S.gs.Netlist(path, 't')
        except S.NetlistError:
            continue
        T = rng.randint(2, 4)
        goal_bits = nl.ports['boot_word']['bits']
        dom = S.dominated_sites(nl, T, goal_bits, nl.coi_and_dist(goal_bits))
        ref = bruteforce.Ref(path, 't')
        for gv in range(1 << meta['w_out']):
            base = ref.run(T, [], gv)
            for (t, b), (t2, h) in dom.items():
                assert ref.run(T, [(t, b)], gv) & ~(base | ref.run(T, [(t2, h)], gv)) == 0
                checked += 1
    assert checked > 500
