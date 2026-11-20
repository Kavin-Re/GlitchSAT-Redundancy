"""Pins rows of results/comms/distance_sweep.csv and the generator's functional check.
The pinned numbers are MEASURED minimum modelled flips (product CLI, stem rule, T=6, yosys 0.33 flow plain); bounded, toy design.
Row checks read the CSV only; test_remeasure_stored re-runs one codebook when yosys, iverilog and the product CLI are available."""
import csv, os, shutil, subprocess, sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'comms'))
import distance_sweep as ds

CSV = os.path.join(ROOT, 'results', 'comms', 'distance_sweep.csv')
PINS = {  # codebook: (d_to_accept, copies_touched_by_xor, min_flops, min_all, min_all_struct)
    'F0_96_stored': ('4', '3', '4', '2', '3'),
    'CC_96': ('4', '3', '4', '3', '3'),
    '69_96_complement': ('8', '3', '>6', '3', '3'),
    '2B_95': ('6', '3', '6', '3', '3'),
    'fam_d2': ('2', '3', '2', '2', '2'),
    'Bvar_one_copy': ('8', '1', '3', '1', '1'),
    'ctrl_one_copy_grouping': ('4', '1', '4', '1', '1'),
}

def _rows():
    return {r['codebook']: r for r in csv.DictReader(open(CSV))}

@pytest.mark.parametrize('name', sorted(PINS))
def test_pinned_row(name):
    r = _rows()[name]
    assert (r['d_to_accept'], r['copies_touched_by_xor'], r['min_flops'], r['min_all'], r['min_all_struct']) == PINS[name]
    assert r['T'] == '6' and len(r['netlist_sha256']) == 64

def test_csv_shape_and_honesty():
    rows = _rows()
    assert len(rows) >= 13
    for r in rows.values():
        assert 'safe' not in ' '.join(r.values()).lower().replace("not 'safe'", '')
        if r['status'].startswith('measured'):   # all-nets never above flops-only (site superset)
            f, a = r['min_flops'], r['min_all']
            assert not a.startswith('>') and a != 'unknown'
            assert int(a) <= int(f.lstrip('>'))
        else:   # negative controls: rejected before any solver run, no numbers
            assert r['status'].startswith('rejected_by_functional_check') and r['min_flops'] == r['min_all'] == ''
    assert sum(1 for r in rows.values() if not r['status'].startswith('measured')) == 2

def test_rule_and_distance_helpers():
    assert ds.pop(0xF0 ^ 0x96) == 4 and ds.pop(0x69 ^ 0x96) == 8
    assert ds.rule(0xF0, 0xCC, 0x96, 0x69, ds.DEFAULT_GROUPING) == 3
    assert ds.rule(0xF0, 0xCC, 0x96, 0x69, '00000000') == 1
    assert ds.copies_touched(0x96 ^ 0x49, 0x96, ds.DEFAULT_GROUPING) == 1
    with pytest.raises(ValueError):
        ds.gen_verilog(0xF0, 0x96, 0x69, 0xCC, grouping='3021')

@pytest.mark.skipif(not shutil.which('iverilog'), reason='iverilog not installed')
def test_generator_functional_check(tmp_path):
    def chk(n, I, W, B, C):
        p = tmp_path / (n + '.v'); p.write_text(ds.gen_verilog(I, W, B, C))
        return ds.functional_check(str(p), W, workdir=str(tmp_path))[0]
    assert chk('good', 0xF0, 0x96, 0x69, 0xCC)            # honest key boots, wrong keys never, power-up not accepted
    assert chk('onestep', 0x69, 0x96, 0x69, None)
    assert not chk('neg_fail_eq_accept', 0xF0, 0x96, 0x96, 0xCC)   # wrong keys would boot
    assert not chk('neg_idle_eq_accept', 0x96, 0x96, 0x69, 0xCC)   # power-up accepted

def test_generated_matches_template_semantics():
    v = ds.gen_verilog(0xF0, 0x96, 0x69, 0xCC)
    for s in ("initial st = 8'hF0", "sel = {m1,m0,m2,m1,m0,m2,m1,m0}", "8'hF0: st <= 8'hCC;", "8'hCC: st <= word;", "boot_ok = (st == 8'h96)"):
        assert s in v

def _cli():
    exe = shutil.which('faultbound-wt')
    if exe: return exe
    try:
        import faultbound_wt  # noqa: F401
        return sys.executable + ' -m faultbound_wt.cli'
    except ImportError:
        return None

@pytest.mark.skipif(not (shutil.which('yosys') and shutil.which('iverilog') and _cli()), reason='needs yosys, iverilog and the product CLI')
def test_remeasure_stored(tmp_path):
    if b'Yosys 0.33' not in subprocess.run(['yosys', '-V'], capture_output=True, timeout=60).stdout:
        pytest.skip('pinned numbers are for yosys 0.33')
    out = tmp_path / 'o.csv'
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/comms/distance_sweep.py'), '--out', str(out), '--work', str(tmp_path / 'w'),
                    '--cli', _cli(), '--only', 'F0_96_stored', 'NEG_idle_equals_accept'], check=True, timeout=600)
    got = {r['codebook']: r for r in csv.DictReader(open(out))}
    want = _rows()
    for k in ('min_flops', 'min_all', 'min_all_struct', 'netlist_sha256'):
        assert got['F0_96_stored'][k] == want['F0_96_stored'][k]
    assert got['NEG_idle_equals_accept']['status'].startswith('rejected_by_functional_check')
