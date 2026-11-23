"""The exhaustive simulator: agreement with brute force, with ext/surface, with validation/netsim.py, and with itself."""
import importlib, itertools, os, sys
import numpy as np
import pytest
from harden import sim, spec as S
from harden.netlist import Netlist, Builder


def test_min_flips_equals_brute_force_v0_reference():
    nl = S.build_mapping(S.PRESETS['v0'], 'select-shared')
    r = sim.min_flips(nl, kmax=2, cycles=4)
    assert r.min_flips == 1
    assert sim.enumerate_sets(nl, k=1, cycles=4).attacking_sets > 0


@pytest.mark.parametrize('armed', [0xCC, 0xC8])
def test_min_flips_equals_brute_force_v2_bounded(armed):
    """Every set of exactly k (cycle, site) pairs over 3 cycles, no site reduction, against the layered search."""
    sp = S.PRESETS['v2'].replace(armed=armed)
    nl = S.build_mapping(sp, 'select-shared')
    r = sim.min_flips(nl, kmax=2, cycles=3)
    for k in (1, 2):
        e = sim.enumerate_sets(nl, k=k, cycles=3)
        expect_attack = r.min_flips is not None and r.min_flips <= k
        assert (e.attacking_sets > 0) == expect_attack, (k, r.min_flips, e.attacking_sets)


def test_reduction_keeps_the_minimum():
    for name in ('v0', 'v1', 'v2'):
        for mp in S.UNMERGED:
            nl = S.build_mapping(S.PRESETS[name], mp)
            a = sim.min_flips(nl, kmax=3, cycles=None, reduce=True)
            b = sim.min_flips(nl, kmax=3, cycles=None, reduce=False)
            assert a.min_flips == b.min_flips, (name, mp)


def test_unbounded_is_not_above_bounded():
    nl = S.build_mapping(S.PRESETS['v2'], 'mux-shared')
    a = sim.min_flips(nl, kmax=3, cycles=None).min_flips
    for T in (2, 4, 6):
        b = sim.min_flips(nl, kmax=3, cycles=T).min_flips
        assert b is None or a <= b


def test_witness_replays_and_is_minimal():
    nl = S.build_mapping(S.PRESETS['v2'], 'select-shared')
    r = sim.min_flips(nl, kmax=3, cycles=None)
    w = r.witness
    assert w['replayed'] and len(w['flip_bits']) == r.min_flips
    assert sim.replay(nl, sim.Goal(), w['input'], w['flip_bits'], w['cycles_used'])
    assert not sim.replay(nl, sim.Goal(), w['input'], w['flip_bits'][1:], w['cycles_used'])


def test_extra_cell_types_match_plain_python():
    """$_NAND_ ... $_BUF_ (written by some Yosys flows) in the numpy simulator and in the plain replay."""
    nl = Netlist('t')
    nl.ports['clk'] = ('input', [2])
    sig = list(range(3, 11))
    nl.ports['sig'] = ('input', sig)
    types = ['$_NAND_', '$_NOR_', '$_XNOR_', '$_ANDNOT_', '$_ORNOT_', '$_BUF_', '$_MUX_', '$_AND_', '$_OR_', '$_XOR_']
    y = 20
    outs = []
    for i, t in enumerate(types):
        a, b, s = sig[i % 8], sig[(i + 3) % 8], sig[(i + 5) % 8]
        nl.gates[y] = (t, a, None if t == '$_BUF_' else b, s if t == '$_MUX_' else None)
        outs.append(y)
        y += 1
    nl.ports['boot_word'] = ('output', outs[:8])
    ff = sim.fault_free(nl, 1, sim.Goal('boot_word', 0))
    for v in range(256):
        bits = {sig[i]: (v >> i) & 1 for i in range(8)}
        exp = 0
        for i, o in enumerate(outs[:8]):
            t, a, b, s = nl.gates[o]
            A, B, Sx = bits[a], bits.get(b, 0), bits.get(s, 0)
            val = {'$_NAND_': 1 - (A & B), '$_NOR_': 1 - (A | B), '$_XNOR_': 1 - (A ^ B), '$_ANDNOT_': A & (1 - B), '$_ORNOT_': A | (1 - B),
                   '$_BUF_': A, '$_MUX_': B if Sx else A, '$_AND_': A & B}[t]
            exp |= val << i
        assert ff['boot_word'][0][v] == exp
        assert sim.replay(nl, sim.Goal('boot_word', exp), v, [], 1)


def test_stored_netlists_against_ext_surface(repo, surface):
    """Same minimum as the exhaustive enumerator of ext/surface (6 and 4 cycles) on stored Yosys netlists."""
    import attack_surface
    for rel, top, T, expect in (('reference/spike_netlists/v0.json', 'v0', 6, 1),
                                ('research/c2/e2_variance/baseline_netlists/apt0.33_v2.json', 'v2', 6, 2),
                                ('validation/nl/v2.json', 'v2', 6, 1)):
        if not os.path.isfile(repo(rel)):
            pytest.skip(rel + ' missing')
        mine = sim.min_flips(Netlist.load(repo(rel), top), kmax=3, cycles=T).min_flips
        theirs = attack_surface.run(repo(rel), top, N=T, max_faults=3, method='exhaustive')['min_faults']
        assert mine == theirs == expect, (rel, mine, theirs)


@pytest.mark.slow
def test_stored_v2_three_flips_against_ext_surface(repo, surface):
    import attack_surface
    rel = 'reference/spike_netlists/v2.json'
    mine = sim.min_flips(Netlist.load(repo(rel), 'v2'), kmax=3, cycles=4).min_flips
    theirs = attack_surface.run(repo(rel), 'v2', N=4, max_faults=3, method='exhaustive')['min_faults']
    assert mine == theirs == 3


def test_witness_confirmed_by_validation_netsim(repo):
    """A witness from this simulator, re-run in the repository's independent simulator validation/netsim.py."""
    sys.path.insert(0, repo('validation'))
    try:
        netsim = importlib.import_module('netsim')
    finally:
        sys.path.pop(0)
    for rel, top in (('research/c2/e2_variance/baseline_netlists/apt0.33_v2.json', 'v2'), ('reference/spike_netlists/v1.json', 'v1')):
        if not os.path.isfile(repo(rel)):
            pytest.skip(rel + ' missing')
        nl = Netlist.load(repo(rel), top)
        r = sim.min_flips(nl, kmax=3, cycles=6)
        w = r.witness
        faults = {}
        for t, b in w['flip_bits']:
            faults.setdefault(t, set()).add(b)
        net = netsim.Net(repo(rel), top)
        hit = netsim.attacks(net, 6, faults)
        assert (hit >> w['input']) & 1, rel
        # and one flip fewer does not work for that input in netsim either (minimality of this witness)
        if len(w['flip_bits']) > 1:
            t0, b0 = w['flip_bits'][0]
            f2 = {t: set(x) for t, x in faults.items()}
            f2[t0].discard(b0)
            assert not (netsim.attacks(net, 6, f2) >> w['input']) & 1


def test_fault_free_equals_description_for_every_mapping():
    for name, sp in S.PRESETS.items():
        ref = np.array(S.reference_trace(sp, 6)).T
        for mp in S.MAPPINGS:
            ff = sim.fault_free(S.build_mapping(sp, mp), 6, sim.Goal('boot_word', sp.goal_value()))
            assert (ff['boot_word'] == ref).all(), (name, mp)
