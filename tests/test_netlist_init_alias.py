"""Regression: a flop bit that appears at several net names/positions may carry an unknown ('x') init at one alias and a
known 0/1 at another. The parser must use the known value (x yields), and must still reject a flop whose init is x everywhere.
The 14 netlists below were rejected before the fix (28 cells = 14 netlists x T in {3, 6}); they are plain Yosys JSON in the tree,
so this test needs neither z3 nor Yosys."""
import json, os, sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g

GEN = os.path.join(ROOT, 'research', 'c4', 'ver', 'gen')
NAMES = ['crc301', 'crc307', 'crc311', 'crc313', 'crc319', 'crc321', 'rc103', 'rc107', 'rc111', 'rc113', 'rc117', 'rc119', 'rc121', 'rc127']


def expected_init(mod):
    """Independent re-derivation: for every flop Q bit, the known 0/1 found at any alias of that bit (None if only x/z)."""
    qs = set()
    for c in mod['cells'].values():
        if c['type'].startswith('$_DFF'):
            qs.add(c['connections']['Q'][0])
    known, seen_x = {}, set()
    for x in mod['netnames'].values():
        iv = x['attributes'].get('init')
        for i, b in enumerate(reversed(iv or '')):
            bit = x['bits'][i]
            if isinstance(bit, int) and bit in qs:
                if b in '01':
                    assert known.setdefault(bit, b == '1') == (b == '1'), 'conflicting known inits are not expected in these netlists'
                else:
                    seen_x.add(bit)
    return qs, known, seen_x


@pytest.mark.parametrize('name', NAMES)
def test_alias_x_yields_to_known_init(name):
    path = os.path.join(GEN, f'{name}_opt.json')
    top = list(json.load(open(path))['modules'])[0]
    nl = g.Netlist(path, top)                       # raised NetlistError before the fix
    qs, known, seen_x = expected_init(nl.m)
    assert seen_x, 'netlist no longer has an x alias: pick another regression case'
    assert set(nl.qs) == qs
    for q in qs:
        assert nl.init[q] == known.get(q, False)    # known value wins; flops with no init at all stay 0 (unchanged rule)
    assert any(q in known for q in seen_x)          # at least one flop really exercises the alias path


def _tiny(init_a, init_b):
    """one flop, its Q reachable as net `a` and as net `b` (same bit), with the given init strings"""
    return {'modules': {'t': {'ports': {'clk': {'direction': 'input', 'bits': [2]}, 'out': {'direction': 'output', 'bits': [3]}},
            'cells': {'ff': {'type': '$_DFF_P_', 'connections': {'C': [2], 'D': [3], 'Q': [3]}}},
            'netnames': {'a': {'bits': [3], 'attributes': {'init': init_a}}, 'b': {'bits': [3], 'attributes': {'init': init_b}}}}}}


@pytest.mark.parametrize('ia,ib,want', [('x', '1', True), ('1', 'x', True), ('x', '0', False), ('0', 'x', False)])
def test_tiny_alias(tmp_path, ia, ib, want):
    p = tmp_path / 't.json'; p.write_text(json.dumps(_tiny(ia, ib)))
    assert g.Netlist(str(p), 't').init[3] is want


def test_tiny_x_only_still_rejected(tmp_path):
    p = tmp_path / 't.json'; p.write_text(json.dumps(_tiny('x', 'x')))
    with pytest.raises(g.NetlistError, match='unknown'):
        g.Netlist(str(p), 't')
