"""Pins rows of results/comms/burst.csv and checks the burst event engine of
scripts/comms/burst_sweep.py (z3) against its z3-free brute force. All numbers are SIMULATED: modelled burst events
(one event = all state flops, or one copy group, inverted in one cycle; or a whole-design rail event) on toy netlists,
bounded by T=6. Not a real overclock or voltage glitch. 'none' = no attack with any subset of that kind's events within T."""
import csv, json, os, shutil, sys
import pytest
pytest.importorskip('z3', reason='z3-solver is not installed: pip install z3-solver')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'comms'))
import burst_sweep as bs

CSV = os.path.join(ROOT, 'results', 'comms', 'burst.csv')
PINS = {  # codebook: (random flops-only [plain], burst flops_all, flops_group, rail_1to0, rail_0to1), same on plain and struct
    '69_96_complement': ('>6', '1', '3', 'none', 'none'),
    'C3_3C_complement': ('>6', '1', '3', 'none', 'none'),
    'A5_5A_complement': ('>6', '1', '3', 'none', 'none'),
    'F0_96_stored': ('4', '1', '3', 'none', 'none'),
    '2B_95': ('6', '1', '3', 'none', 'none'),
    '00_1F_F8_E7': ('5', 'none', 'none', 'none', 'none'),
    'F0_96_B3C': ('4', 'none', 'none', 'none', 'none'),
    'A5_A6_BBE': ('2', 'none', 'none', 'none', 'none'),
    'F0_96_BDF': ('3', 'none', '1', 'none', 'none'),
    '00_FF_C01_B02': ('>6', '1', '3', 'none', '1'),
    'FF_00_CFE_BFD': ('>6', '1', '3', '1', 'none'),
}


def _rows():
    return list(csv.DictReader(open(CSV)))


@pytest.mark.parametrize('name', sorted(PINS))
def test_pinned_row(name):
    rs = [r for r in _rows() if r['codebook'] == name]
    assert [r['flow'] for r in rs] == ['plain', 'struct']
    for r in rs:
        assert (r['random_min_flops'], r['burst_flops_all'], r['burst_flops_group'], r['burst_rail_1to0'], r['burst_rail_0to1']) == PINS[name]
        assert r['T'] == '6' and len(r['netlist_sha256']) == 64


def test_complement_pair_breaks_with_one_event():
    r = [r for r in _rows() if r['codebook'] == '69_96_complement' and r['flow'] == 'plain'][0]
    assert r['burst_flops_all'] == '1' and r['random_min_flops'] == '>6' and r['witness_flops_all'].startswith('flops_all@')
    assert r['quadrant'] == 'random-robust / burst-fragile'


def test_csv_checks_and_honesty():
    rows = _rows()
    assert len(rows) == 2 * len(bs.codebooks())
    quads = {r['quadrant'] for r in rows}
    assert len(quads) == 4          # every cell of the 2x2 table is populated
    for r in rows:
        assert r['bf_agree'] == 'yes' and r['reduce_none_agree'] == 'yes'
        if (r['codebook'], r['flow']) == ('2B_95_BEB', 'struct'):   # known: the any-net control timed out ('unknown'), row stays flagged
            assert r['control_any_net'] == 'unknown' and r['control_flop_flip'] == r['random_min_flops'] and r['status'].startswith('ENGINE_CHECK_FAILED')
        else:
            assert r['status'] == 'measured' and r['control_agree'] == 'yes'
        assert r['label'].startswith('SIMULATED')
        text = ' '.join(r.values()).lower()
        assert 'safe' not in text and 'secure' not in text
        for k in bs.BURST_KINDS:    # predicted and measured are separate columns; pred_match is derived from them
            assert r['pred_' + k] in ('1', '2', '3', 'none')
        assert (r['pred_match'] == 'yes') == all(r['burst_' + k] == r['pred_' + k] for k in bs.BURST_KINDS)


def test_prediction_rules_are_arithmetic():
    assert 0x69 ^ 0xFF == 0x96
    assert bs.group_masks() == [0x49, 0x92, 0x24]
    assert bs.pred_flops_all(0x69, None, 0x96, 0x69) == '1'
    assert bs.pred_flops_all(0xF0, 0xCC, 0x96, 0x69) == '1'      # the stored fail word is the complement of accept
    assert bs.pred_flops_all(0xF0, 0xCC, 0x96, 0x3C) == 'none'
    assert bs.pred_flops_group(0xF0, 0xCC, 0x96, 0xDF) == '1' and bs.pred_flops_group(0x69, None, 0x96, 0x69) == '3'
    assert bs.pred_flops_group(0x00, 0xF8, 0x1F, 0xE7) == 'none'
    assert bs.pred_rail(0xFF, 1) == '1' and bs.pred_rail(0xFF, 0) == 'none' and bs.pred_rail(0x00, 0) == '1'


def _tiny(tmp_path):
    """Hand-written netlist, no yosys: two hold flops (word = 0b10 at power-up), one unused inverter, 8-bit sig."""
    dff = lambda b: {'type': '$_DFF_P_', 'connections': {'C': [2], 'D': [b], 'Q': [b]}}
    doc = {'modules': {'t': {
        'ports': {'clk': {'direction': 'input', 'bits': [2]}, 'sig': {'direction': 'input', 'bits': list(range(3, 11))},
                  'boot_word': {'direction': 'output', 'bits': [11, 12]}},
        'cells': {'f0': dff(11), 'f1': dff(12), 'n': {'type': '$_NOT_', 'connections': {'A': [11], 'Y': [13]}}},
        'netnames': {'st': {'bits': [11, 12], 'attributes': {'init': '10'}}, 'n': {'bits': [13], 'attributes': {}},
                     'sig': {'bits': list(range(3, 11)), 'attributes': {}}}}}}
    p = tmp_path / 'tiny.json'
    p.write_text(json.dumps(doc))
    return bs.gs.Netlist(str(p), 't')


@pytest.mark.parametrize('goal,expect', [
    (1, {'flops_all': '1', 'flops_group': '2', 'rail_1to0': 'none', 'rail_0to1': 'none'}),   # 10 -> 01: complement
    (3, {'flops_all': 'none', 'flops_group': '1', 'rail_1to0': 'none', 'rail_0to1': '1'}),
    (0, {'flops_all': 'none', 'flops_group': '1', 'rail_1to0': '1', 'rail_0to1': 'none'}),
])
def test_engine_against_brute_force_on_tiny_netlist(tmp_path, goal, expect):
    nl = _tiny(tmp_path)
    for kind in bs.BURST_KINDS:
        evs = bs.events(nl, kind, masks=[1, 2])
        bf = bs.BF(nl, 4, evs, goal)
        cells = {bs.z3_min(nl, 4, evs, goal, simp=s)[0] for s in (True, False)}   # with and without simplification (--reduce none)
        assert cells == {expect[kind]} == {bf.search_min()}
        e = bf.enum_min(3)
        assert e == expect[kind] or (e == '>3' and expect[kind] == 'none')


def test_remeasure_complement_pair(tmp_path):
    if not (shutil.which('yosys') and shutil.which('iverilog')):
        pytest.skip('yosys/iverilog not available')
    v = tmp_path / 'c.v'
    v.write_text(bs.ds.gen_verilog(0x69, 0x96, 0x69))
    ok, msg = bs.ds.functional_check(str(v), 0x96, workdir=str(tmp_path))
    assert ok, msg
    j = str(tmp_path / 'c_plain.json')
    bs.ds.synth_plain(str(v), 'v2', j)
    nl = bs.gs.Netlist(j, 'v2')
    evs = bs.events(nl, 'flops_all')
    assert bs.z3_min(nl, 6, evs, 0x96, simp=False)[0] == '1' == bs.BF(nl, 6, evs, 0x96).search_min()
    assert bs.BF(nl, 6, bs.events(nl, 'flip_flop'), 0x96).enum_min(2) == '>2'      # two random flop flips are not enough
    g = bs.events(nl, 'flops_group')
    assert bs.z3_min(nl, 6, g, 0x96)[0] == '3' == bs.BF(nl, 6, g, 0x96).search_min()
