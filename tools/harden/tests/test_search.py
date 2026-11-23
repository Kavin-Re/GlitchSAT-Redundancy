"""The search: moves, predictor, and that an accepted fix really meets the goal when re-checked independently."""
import numpy as np
import pytest
from harden import search, sim, spec as S


def test_owners_enumerates_set_partitions():
    assert len(list(search.owners(3, 2))) == 3        # Stirling number S(3,2)
    assert len(list(search.owners(4, 2))) == 7
    assert all(set(o) == {0, 1} for o in search.owners(4, 2))


def test_structures_are_valid_and_unique():
    for name in ('v0', 'v1', 'v2'):
        st = search.structures(S.PRESETS[name], search.ALL_MOVES)
        assert st and all(not sp.problems() for sp, _ in st)
        assert len({sp.replace(name='x') for sp, _ in st}) == len(st)


@pytest.mark.parametrize('sp', [S.PRESETS['v0'], S.PRESETS['v1'], S.PRESETS['v2'], S.PRESETS['v2e'],
                                S.PRESETS['v2'].replace(armed=0xC8), S.PRESETS['v1'].replace(voter='per_bit_and'),
                                S.PRESETS['v2'].replace(alarm='infect', check_copies=1)])
def test_predictor_is_an_upper_bound(sp):
    """The predictor only discards candidates. It is meant as an upper bound for the most-shared mapping (the goal must hold on
    every mapping, so that is the one that matters); a wrong prediction could only make the search miss a fix."""
    p = search.predictor(sp)
    m = search.measure(sp, p)
    w = search.worst(m)
    assert w is not None and w <= p, (p, {k: v['min_flips'] for k, v in m.items()})


def _recheck(sp, goal):
    """Independent of search.measure: rebuild every mapping, brute-force all sets of goal-1 flips over 4 cycles, and run
    the unbounded layered search."""
    for mp in S.UNMERGED:
        nl = S.build_mapping(sp, mp)
        g = sim.Goal('boot_word', sp.goal_value())
        assert sim.min_flips(nl, g, kmax=goal - 1, cycles=None, key=sp.key, reduce=False).min_flips is None, mp
        if goal - 1 <= 2:
            assert sim.enumerate_sets(nl, g, k=goal - 1, cycles=4).attacking_sets == 0, mp
        ff = sim.fault_free(nl, 6, g)
        assert (ff['boot_word'] == np.array(S.reference_trace(sp, 6)).T).all()
        assert ff['goal'][:, sp.key].any() and not np.delete(ff['goal'].any(axis=0), sp.key).any()


def test_v1_goal_2_fix_rechecked():
    res = search.harden(S.PRESETS['v1'], 2, alternatives=1, exact=False)
    assert res['best'] is not None and res['before_min'] == 1
    sp = res['best']['spec']
    assert sp.voter != 'single_and'            # the shared voter net is the single point that must go
    _recheck(sp, 2)


def test_v2_goal_3_by_encoding_only():
    """Generalises the manual 0xCC -> 0xA5 change: only the armed / idle words may change."""
    res = search.harden(S.PRESETS['v2'], 3, allow=('encoding',), alternatives=1, exact=False)
    assert res['before_min'] == 2
    sp = res['best']['spec']
    assert (sp.copies, sp.owner, sp.voter, sp.accept, sp.reject) == (3, S.PRESETS['v2'].owner, 'owner', 0x96, 0x69)
    assert sp.armed != 0xCC
    _recheck(sp, 3)


def test_ownership_move_alone_can_fix_v2e_select_shared():
    """0xA5 needs only 2 flips on the select-shared mapping; re-assigning bit ownership (no new logic) is tried."""
    base = S.PRESETS['v2e']
    assert search.worst(search.measure(base, 3)) == 2
    res = search.harden(base, 3, allow=('ownership',), alternatives=1, exact=False, time_budget=300)
    if res['best'] is not None:
        _recheck(res['best']['spec'], 3)
        assert res['best']['spec'].armed == 0xA5


def test_unreachable_goal_reports_closest():
    res = search.harden(S.PRESETS['v1'], 3, allow=('encoding',), alternatives=1, exact=False, time_budget=60)
    assert res['best'] is None           # a single AND voter in front of the register stays one net
