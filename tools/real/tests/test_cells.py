"""Every Nangate45 cell function: primitive tree == SYNFI docstring == SYNFI CNF clauses, exhaustively."""
import pytest
from glitchsat_real import nangate as ng


def test_all_cells_verified(lib):
    rep = ng.verify_cells(lib)
    assert len(rep) == 98
    assert sum(r['rows_checked'] for r in rep.values()) == 1326
    assert rep['MUX2_X1.Z']['prims'] == 'MUX(S, B, A)'
    assert rep['FA_X1.CO']['inputs'] == ['A', 'B', 'CI']


def test_check_detects_a_wrong_mapping(lib, monkeypatch):
    real = ng.to_prims

    def broken(t):
        p = real(t)
        return ('NOT', p) if p[0] == 'NOT' and p[1][0] == 'AND' else p     # NAND -> AND
    monkeypatch.setattr(ng, 'to_prims', broken)
    with pytest.raises(ng.AdapterError):
        ng.verify_cells(lib, ['NAND2_X1'])


def test_parser_precedence_and_double_negation():
    t = ng.parse_expr('!(!(!((A1 & A2) | B)))')
    assert ng.simplify(t) == ('not', ('or', ('and', ('var', 'A1'), ('var', 'A2')), ('var', 'B')))
    for a in (0, 1):
        for b in (0, 1):
            assert ng.eval_tree(ng.parse_expr('A | B & !A'), dict(A=a, B=b)) == (a | (b & (1 - a)))


def test_unsupported_cells_are_refused(lib):
    doc = {'modules': {'t': {'ports': {}, 'netnames': {}, 'cells': {
        'l': {'type': 'DLH_X1', 'port_directions': {'D': 'input', 'G': 'input', 'Q': 'output'},
              'connections': {'D': [2], 'G': [3], 'Q': [4]}}}}}}
    with pytest.raises(ng.UnsupportedCell):
        ng.convert(doc, 't', lib=lib)


def test_hier_lint_aes_rails():
    import json, os
    from conftest import REAL
    from glitchsat_real import hier_lint
    doc = json.load(open(os.path.join(REAL, 'synfi/examples/aes_cipher_control_rnd_ctr/netlist_aes_cipher_control_flattened_ctr_reg.json')))
    r = hier_lint.lint(doc, 'aes_cipher_control')
    assert r['cross_copy_reads'] == 0
    assert sorted(r['copies']) == ['0', '1', '2'] and all(v['flops'] == 7 for v in r['copies'].values())
    assert r['identical_signatures'] == [['0', '1']]
