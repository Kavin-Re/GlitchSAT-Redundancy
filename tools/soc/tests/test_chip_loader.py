"""Loader: gate library, flop kinds, clock domains, clock gates, black boxes, x bits. Each behaviour is checked by
simulating the loaded Circuit with the compiled simulator against the expected truth table / waveform."""
import itertools

import pytest
from conftest import cell, netlist


def _sim(ch, cycles, inputs_per_cycle, state=None, flips=None, watch=()):
    from gsoc import sim
    comp = sim.Compiled(ch.circ)
    st = {q: (1 if (state or {}).get(q) else 0) for q in ch.circ.flops}
    return comp.run(1, cycles, st, lambda t: inputs_per_cycle[t], (lambda t: (flips or {}).get(t)), list(watch))


GATES = {
    '$_AND_': lambda a, b: a & b, '$_OR_': lambda a, b: a | b, '$_XOR_': lambda a, b: a ^ b,
    '$_NAND_': lambda a, b: 1 - (a & b), '$_NOR_': lambda a, b: 1 - (a | b), '$_XNOR_': lambda a, b: 1 - (a ^ b),
    '$_ANDNOT_': lambda a, b: a & (1 - b), '$_ORNOT_': lambda a, b: a | (1 - b),
}


@pytest.mark.parametrize('t', sorted(GATES))
def test_two_input_gates(root, t):
    from gsoc import chip
    doc = netlist({'a': ('input', [2]), 'b': ('input', [3]), 'y': ('output', [4])}, {'g': cell(t, A=2, B=3, Y=4)})
    ch = chip.load(doc)
    assert ch.sites == {4}                       # one fault site per cell, whatever it is split into
    for a, b in itertools.product((0, 1), repeat=2):
        assert _sim(ch, 1, [{2: a, 3: b}], watch=[4])[0][4] == GATES[t](a, b)


def test_three_and_four_input_gates(root):
    from gsoc import chip
    fn = {'$_AOI3_': lambda a, b, c: 1 - ((a & b) | c), '$_OAI3_': lambda a, b, c: 1 - ((a | b) & c),
          '$_MUX_': lambda a, b, s: b if s else a, '$_NMUX_': lambda a, b, s: 1 - (b if s else a)}
    for t, f in fn.items():
        pins = ('A', 'B', 'S') if 'MUX' in t else ('A', 'B', 'C')
        doc = netlist({'i': ('input', [2, 3, 4]), 'y': ('output', [5])}, {'g': cell(t, **dict(zip(pins, (2, 3, 4))), Y=5)})
        ch = chip.load(doc)
        for v in itertools.product((0, 1), repeat=3):
            assert _sim(ch, 1, [dict(zip((2, 3, 4), v))], watch=[5])[0][5] == f(*v), (t, v)
    for t, f in {'$_AOI4_': lambda a, b, c, d: 1 - ((a & b) | (c & d)), '$_OAI4_': lambda a, b, c, d: 1 - ((a | b) & (c | d))}.items():
        doc = netlist({'i': ('input', [2, 3, 4, 5]), 'y': ('output', [6])}, {'g': cell(t, A=2, B=3, C=4, D=5, Y=6)})
        ch = chip.load(doc)
        for v in itertools.product((0, 1), repeat=4):
            assert _sim(ch, 1, [dict(zip((2, 3, 4, 5), v))], watch=[6])[0][6] == f(*v), (t, v)


def _flop(t, **extra):
    ports = {'clk': ('input', [2]), 'd': ('input', [3]), 'e': ('input', [4]), 'r': ('input', [5]), 'q': ('output', [6])}
    return netlist(ports, {'ff': cell(t, C=2, D=3, Q=6, **extra)})


def test_flop_kinds(root):
    from gsoc import chip
    d, e, r, q = 3, 4, 5, 6
    seq = [dict(d=1, e=1, r=0), dict(d=0, e=0, r=0), dict(d=0, e=1, r=0), dict(d=1, e=1, r=1), dict(d=1, e=0, r=1), dict(d=1, e=0, r=0)]
    ins = [{3: s['d'], 4: s['e'], 5: s['r']} for s in seq] + [{}]

    def run(t, **extra):
        ch = chip.load(_flop(t, **extra), clock='clk')
        return [row[q] for row in _sim(ch, len(ins), ins, watch=[q])]
    assert run('$_DFF_P_') == [0, 1, 0, 0, 1, 1, 1]
    assert run('$_DFFE_PP_', E=e) == [0, 1, 1, 0, 1, 1, 1]
    assert run('$_DFFE_PN_', E=e) == [0, 0, 0, 0, 0, 1, 1]
    assert run('$_SDFF_PP0_', R=r) == [0, 1, 0, 0, 0, 0, 1]
    assert run('$_SDFF_PP1_', R=r) == [0, 1, 0, 0, 1, 1, 1]
    assert run('$_DFF_PP0_', R=r) == [0, 1, 0, 0, 0, 0, 1]               # async reset: effective at the next edge
    assert run('$_DFF_PN1_', R=r) == [0, 1, 1, 1, 1, 1, 1]               # active-low reset, r=0 most of the time
    assert run('$_SDFFE_PP0P_', R=r, E=e) == [0, 1, 1, 0, 0, 0, 0]       # reset wins over enable
    assert run('$_SDFFCE_PP0P_', R=r, E=e) == [0, 1, 1, 0, 0, 0, 0]      # enable gates the reset: e=0,r=1 holds
    ch = chip.load(_flop('$_DFFE_PN0P_', R=r, E=e), clock='clk')
    assert ch.reset_value[q] is False and ch.info['flops_async_reset'] == 1


def test_sdffce_holds_when_enable_low(root):
    from gsoc import chip
    ch = chip.load(_flop('$_SDFFCE_PP0P_', R=5, E=4), clock='clk')
    rows = _sim(ch, 3, [{3: 1, 4: 1, 5: 0}, {3: 0, 4: 0, 5: 1}, {}], watch=[6])
    assert [r[6] for r in rows] == [0, 1, 1]
    ch = chip.load(_flop('$_SDFFE_PP0P_', R=5, E=4), clock='clk')
    rows = _sim(ch, 3, [{3: 1, 4: 1, 5: 0}, {3: 0, 4: 0, 5: 1}, {}], watch=[6])
    assert [r[6] for r in rows] == [0, 1, 0]


def test_second_clock_gets_free_tick_and_async_reset_ignores_it(root):
    from gsoc import chip
    ports = {'clk': ('input', [2]), 'clk2': ('input', [3]), 'd': ('input', [4]), 'rn': ('input', [5]), 'q': ('output', [6, 7])}
    doc = netlist(ports, {'a': cell('$_DFF_P_', C=2, D=4, Q=6), 'b': cell('$_DFF_PN0_', C=3, D=4, R=5, Q=7),
                          'c': cell('$_DFF_P_', C=2, D=4, Q=8)}, names={'q8': [8]})
    ch = chip.load(doc, clock='clk')
    assert ch.info['flops_off_reference_clock'] == 1 and ch.info['flops_on_free_tick_clocks'] == 1
    tick = [b for b, why in ch.free.items() if why.startswith('tick:')]
    assert len(tick) == 1
    tk = tick[0]
    rows = _sim(ch, 5, [{4: 1, 5: 1, tk: 0}, {4: 1, 5: 1, tk: 1}, {4: 1, 5: 1, tk: 0}, {4: 1, 5: 0, tk: 0}, {}], watch=[6, 7])
    assert [r[6] for r in rows] == [0, 1, 1, 1, 1]         # reference clock: loads every cycle
    assert [r[7] for r in rows] == [0, 0, 1, 1, 0]         # loads only when its clock ticks; reset needs no tick


def test_clock_gate_is_modelled_exactly(root):
    from gsoc import chip
    ports = {'clk': ('input', [2]), 'en': ('input', [3]), 'd': ('input', [4]), 'q': ('output', [7])}
    doc = netlist(ports, {'lat': cell('$_DLATCH_N_', E=2, D=3, Q=5), 'gate': cell('$_AND_', A=5, B=2, Y=6),
                          'ff': cell('$_DFF_P_', C=6, D=4, Q=7), 'ref': cell('$_DFF_P_', C=2, D=4, Q=8),
                          'ref2': cell('$_DFF_P_', C=2, D=4, Q=9)}, names={'x': [8, 9]})
    ch = chip.load(doc, clock='clk')
    assert list(ch.info['clock_gates_modelled']) and ch.info['flops_on_free_tick_clocks'] == 0
    assert not [1 for why in ch.free.values() if why.startswith('tick:')]
    rows = _sim(ch, 4, [{3: 0, 4: 1}, {3: 1, 4: 1}, {3: 0, 4: 0}, {}], watch=[7])
    assert [r[7] for r in rows] == [0, 0, 1, 1]            # loads exactly in the cycle whose enable is 1


def test_blackbox_and_x_become_free_values(root):
    from gsoc import chip
    ports = {'clk': ('input', [2]), 'a': ('input', [3]), 'y': ('output', [6, 7])}
    mem = dict(type='$mem_v2', parameters={'SIZE': '100000', 'WIDTH': '1000', 'MEMID': '\\m'},
               connections={'RD_ADDR': [3], 'RD_DATA': [4], 'WR_DATA': [3]},
               port_directions={'RD_ADDR': 'input', 'RD_DATA': 'output', 'WR_DATA': 'input'})
    doc = netlist(ports, {'m': mem, 'g': cell('$_AND_', A=4, B=3, Y=6), 'h': cell('$_OR_', A='x', B=3, Y=7)})
    ch = chip.load(doc, clock='clk')
    assert ch.info['blackboxes']['m']['words'] == 32 and ch.info['memory_bits_blackboxed'] == 32 * 8
    assert ch.free[4] == 'blackbox:m' and ch.info['x_readers'] == 1
    assert 4 not in ch.sites and ch.sites == {6, 7}        # free values are not fault sites; cells are


def test_rejects_hierarchy_and_double_drivers(root):
    from gsoc import chip
    doc = netlist({'a': ('input', [2]), 'y': ('output', [3])}, {'g': cell('$_NOT_', A=2, Y=3), 'h': cell('$_NOT_', A=2, Y=3)})
    with pytest.raises(chip.ChipError):
        chip.load(doc)
    doc = netlist({'a': ('input', [2]), 'y': ('output', [3])}, {'u': cell('sub', A=2, Y=3)})
    doc['modules']['sub'] = dict(attributes={}, ports={}, cells={}, netnames={})
    with pytest.raises(chip.ChipError):
        chip.load(doc)
