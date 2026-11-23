"""Slicing is exact, the reset analysis is sound, and the chip-level referee agrees with the search."""
import os
import random

import pytest
from conftest import cell, netlist

REF = {'v0': 1, 'v1': 1, 'v2': 3}          # minimum faults of the repository's reference designs at 6 cycles


def _goal(cycles=6, **kw):
    g = dict(id='boot', hit=['boot_word=0x96'], attacker=dict(port='sig', differs_from=0xC3), cycles=cycles, kmax=3)
    g.update(kw)
    return g


@pytest.mark.parametrize('name', sorted(REF))
def test_reference_designs_same_minimum_as_engine_question(root, name):
    """The loader + slicer path gives the documented minimum of the reference designs, and the same answer as
    gscale's own reading of the same file (which does no explicit slicing)."""
    from gsoc import chip, slicer, gscale
    G = gscale()
    path = os.path.join(root, 'reference', 'spike_netlists', name + '.json')
    ch = chip.load(path, name, clock='clk')
    b = slicer.build(ch, _goal())
    o = G.search.analyse(b.P, 3, backend='py')
    assert o['status'] == 'EXACT' and o['hi'] == REF[name]
    P0 = G.spec.load_problem(path, name, 6)
    o0 = G.search.analyse(P0, 3, backend='py')
    assert (o0['status'], o0['hi']) == (o['status'], o['hi'])


def _with_ballast(root, name, extra_flops=40):
    """The reference design plus logic that cannot reach the goal: a shift register fed by an extra input, and a
    deep chain in FRONT of the check (so that it is in the cone but beyond the horizon)."""
    import json
    doc = json.load(open(os.path.join(root, 'reference', 'spike_netlists', name + '.json')))
    m = doc['modules'][name]
    mx = max(b for x in m['netnames'].values() for b in x['bits'] if isinstance(b, int)) + 10
    clk = m['ports']['clk']['bits'][0]
    m['ports']['junk'] = dict(direction='input', bits=[mx])
    m['netnames']['junk'] = dict(bits=[mx], attributes={}, hide_name=0)
    prev = mx
    for i in range(extra_flops):
        q = mx + 1 + i
        m['cells']['ballast%d' % i] = cell('$_DFF_P_', C=clk, D=prev, Q=q)
        m['netnames']['ballast%d' % i] = dict(bits=[q], attributes={}, hide_name=0)
        prev = q
    m['ports']['junk_o'] = dict(direction='output', bits=[prev])
    return doc


@pytest.mark.parametrize('name', ['v0', 'v2'])
def test_slice_drops_unrelated_logic_and_keeps_the_answer(root, name):
    from gsoc import chip, slicer, gscale
    G = gscale()
    ch = chip.load(_with_ballast(root, name), name, clock='clk')
    b = slicer.build(ch, _goal())
    assert b.info['chip_flops'] - b.info['slice_flops'] == 40
    assert not any('ballast' in ch.circ.name(x) for x in b.P.sites)
    o = G.search.analyse(b.P, 3, backend='py')
    assert o['status'] == 'EXACT' and o['hi'] == REF[name]


def test_slice_equals_whole_circuit_on_random_small_designs(root):
    """Exactness of the horizon cut: for random sequential circuits the sliced problem (T small, deep logic cut) and
    the unsliced problem (every net kept by giving the slicer a goal that is the same but with the cut disabled
    through a long horizon prefix) have the same minimum for every prefix length."""
    from gsoc import chip, slicer, gscale
    G = gscale()
    rnd = random.Random(7)
    for trial in range(12):
        n_in, n_ff, n_g = 3, 5, 14
        nets = list(range(2, 2 + n_in))
        ffq = list(range(10, 10 + n_ff))
        cells = {}
        avail = nets + ffq
        nid = 100
        for i in range(n_g):
            t = rnd.choice(['$_AND_', '$_OR_', '$_XOR_', '$_NAND_', '$_MUX_', '$_NOT_'])
            a, b2, s = rnd.choice(avail), rnd.choice(avail), rnd.choice(avail)
            y = nid; nid += 1
            if t == '$_NOT_': cells['g%d' % i] = cell(t, A=a, Y=y)
            elif t == '$_MUX_': cells['g%d' % i] = cell(t, A=a, B=b2, S=s, Y=y)
            else: cells['g%d' % i] = cell(t, A=a, B=b2, Y=y)
            avail.append(y)
        for i, q in enumerate(ffq):
            cells['f%d' % i] = cell('$_DFF_P_', C=1, D=rnd.choice(avail[n_in:]), Q=q)
        out = [avail[-1], avail[-2]]
        doc = netlist({'clk': ('input', [1]), 'i': ('input', nets), 'o': ('output', out)}, cells)
        ch = chip.load(doc, clock='clk')
        for T in (1, 2, 3):
            g = dict(id='g', hit=['o=3'], cycles=T, kmax=2)
            b = slicer.build(ch, g)
            o = G.search.analyse(b.P, 2, backend='py', modules='none')
            # reference: brute force over all fault sets of size <= 2 on the WHOLE circuit with the compiled simulator
            from gsoc import sim
            comp = sim.Compiled(ch.circ)
            sites = sorted(ch.sites)
            cand = [(t, s) for t in range(T) for s in sites]
            best = None
            import itertools
            for k in range(0, 3):
                for fs in itertools.combinations(cand, k):
                    # all input sequences: 3 inputs x T cycles as lanes
                    L = 1 << (n_in * T)
                    def ins(t, L=L):
                        d = {}
                        for j, nb in enumerate(nets):
                            bit = t * n_in + j
                            w = 0
                            for lane in range(L):
                                if (lane >> bit) & 1: w |= 1 << lane
                            d[nb] = w
                        return d
                    fl = {}
                    for t, s in fs: fl.setdefault(t, {})[s] = (1 << L) - 1
                    tr = comp.run(L, T, {}, ins, lambda t: fl.get(t), out)
                    if any(row[out[0]] & row[out[1]] for row in tr):
                        best = k; break
                if best is not None: break
            got = o['hi'] if o['status'] == 'EXACT' else None
            assert got == best, (trial, T, got, best, o['status'])


def test_reset_state_three_valued(root):
    from gsoc import chip, sim
    # q1: sync reset to 1; q2: no reset, fed by q1 (known one cycle later); q3: no reset, fed by an input (unknown);
    # q4: toggles during reset (never settles -> must be reported unknown by the widening)
    ports = {'clk': ('input', [1]), 'rst': ('input', [2]), 'a': ('input', [3]), 'o': ('output', [10, 11, 12, 13])}
    cells = {'f1': cell('$_SDFF_PP1_', C=1, D=3, R=2, Q=10), 'f2': cell('$_DFF_P_', C=1, D=10, Q=11),
             'f3': cell('$_DFF_P_', C=1, D=3, Q=12), 'n': cell('$_NOT_', A=13, Y=14), 'f4': cell('$_DFF_P_', C=1, D=14, Q=13)}
    doc = netlist(ports, cells)
    doc['modules']['t']['netnames']['tog'] = dict(bits=[13], attributes={'init': '0'}, hide_name=0)
    ch = chip.load(doc, clock='clk')
    st, info = sim.reset_state(ch, {2: True}, cycles=4)
    assert st[10] is True and st[11] is True and st[12] is None
    assert st[13] is None                      # 0,1,0,1,...: depends on the reset length, so it is unknown
    assert info['flops_known'] == 2 and info['flops_unknown'] == 2


def test_unknown_start_values_are_free_in_the_search(root):
    """A flop with an unknown start value may start at 1: a goal that reads it is reachable with 0 faults, and the
    chip-level replay uses the value the solver chose."""
    from gsoc import chip, sim, slicer, gscale
    G = gscale()
    ports = {'clk': ('input', [1]), 'rst': ('input', [2]), 'o': ('output', [10])}
    doc = netlist(ports, {'f': cell('$_DFFE_PP_', C=1, D=10, E=2, Q=10)})
    ch = chip.load(doc, clock='clk')
    st, _ = sim.reset_state(ch, {2: True}, cycles=4)
    assert st[10] is None
    b = slicer.build(ch, dict(id='g', hit=['o=1'], cycles=2, kmax=1), dict(port='rst', active=1), st)
    o = G.search.analyse(b.P, 1, backend='py')
    assert o['status'] == 'EXACT' and o['hi'] == 0
    r = slicer.replay_on_chip(ch, b, sim.Compiled(ch.circ), o['_witness_raw'], st)
    assert r['ok']
    # with a known start value 0 the same goal needs one fault
    b = slicer.build(ch, dict(id='g', hit=['o=1'], cycles=2, kmax=1), dict(port='rst', active=1), {10: False})
    o = G.search.analyse(b.P, 1, backend='py')
    assert o['hi'] == 1


def test_hold_needs_as_many_flips_as_cycles_on_a_wire(root):
    from gsoc import chip, slicer, gscale
    G = gscale()
    doc = netlist({'clk': ('input', [1]), 'a': ('input', [2]), 'o': ('output', [5])},
                  {'g': cell('$_AND_', A=2, B='0', Y=5), 'f': cell('$_DFF_P_', C=1, D=2, Q=6)}, names={'q': [6]})
    ch = chip.load(doc, clock='clk')
    for hold in (1, 2, 3):
        b = slicer.build(ch, dict(id='g', hit=['o=1'], hold=hold, cycles=4, kmax=3))
        o = G.search.analyse(b.P, 3, backend='py')
        assert o['hi'] == hold


def test_compiled_simulator_agrees_with_gscale_replay(root):
    from gsoc import chip, slicer, sim, gscale
    G = gscale()
    path = os.path.join(root, 'reference', 'spike_netlists', 'v2.json')
    ch = chip.load(path, 'v2', clock='clk')
    b = slicer.build(ch, _goal())
    comp = sim.Compiled(ch.circ)
    rnd = random.Random(3)
    sites = sorted(ch.sites)
    sig = ch.circ.ports['sig'][1]
    for _ in range(200):
        faults = [(rnd.randrange(6), rnd.choice(sites)) for _ in range(rnd.randrange(0, 4))]
        faults = list(dict.fromkeys(faults))
        ins = {x: bool(rnd.getrandbits(1)) for x in sig}
        a = G.sim.replay(b.P, ins, faults)
        c = slicer.replay_on_chip(ch, b, comp, (ins, faults), None)
        assert (a['hit'] is not None and a['neq_ok']) == c['ok']
        if c['ok']:
            assert a['hit'] == c['hit_cycle']
