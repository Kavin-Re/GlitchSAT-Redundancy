"""Pins rows of results/comms/decoder_variants.csv and re-runs the functional benches.
Pinned numbers are MEASURED minimum modelled flips (product CLI --synth-sweep, stem rule, T=6, k<=4, yosys 0.33);
bounded, toy designs, no general claim about ECC. Row checks read the CSV only."""
import csv, os, shutil, subprocess
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, 'results', 'comms', 'decoder_variants.csv')
COLS = ['design', 'goal', 'sites', 'min_flips', 'k_max', 'T', 'yosys', 'flow', 'netlist_sha256', 'gates', 'flops', 'predicted']
PLAIN = {  # (design, goal, sites): measured min on flow 'plain'
    ('v2', 'boot_word==0x96', 'flops'): '4', ('v2', 'boot_word==0x96', 'all'): '2',
    ('v2e', 'boot_word==0x96', 'flops'): '4', ('v2e', 'boot_word==0x96', 'all'): '3',
    ('v2_secded', 'boot_word==0x96', 'flops'): '3', ('v2_secded', 'boot_word==0x96', 'all'): '2',
    ('v2c', 'boot_word==0x96', 'flops'): '4', ('v2c', 'boot_word==0x96', 'all'): '2',
    ('v2_secded', 'boot_ok==1', 'flops'): '3', ('v2c', 'boot_ok==1', 'flops'): '4',
    ('v2_secded', 'boot_ok==1', 'all'): '1', ('v2c', 'boot_ok==1', 'all'): '1',
}

def _rows():
    return list(csv.DictReader(open(CSV)))

def test_shape():
    rows = _rows()
    assert list(rows[0].keys()) == COLS and len(rows) == 144
    for r in rows:
        assert r['T'] == '6' and r['k_max'] == '4' and len(r['netlist_sha256']) == 64
        assert r['min_flips'] == 'unknown' or r['min_flips'].lstrip('>').isdigit()
        assert 'safe' not in ' '.join(r.values()).lower()

@pytest.mark.parametrize('key', sorted(PLAIN))
def test_plain_pins(key):
    r = [x for x in _rows() if (x['design'], x['goal'], x['sites']) == key and x['flow'] == 'plain']
    assert len(r) == 1 and r[0]['min_flips'] == PLAIN[key]
    if r[0]['predicted']:   # every pre-registered plain-flow prediction matched in this run
        assert r[0]['predicted'] == r[0]['min_flips']

def test_all_nets_never_above_flops_and_decoder_rows():
    idx = {(r['design'], r['goal'], r['flow'], r['sites']): r['min_flips'] for r in _rows()}
    for (d, g, f, s), v in idx.items():
        if s == 'all':
            assert int(v) <= int(idx[(d, g, f, 'flops')])
        if g == 'boot_word==0x96':   # in all 9 flows: the corrector costs one flop flip less, the checker changes nothing
            assert idx[(d, g, f, 'flops')] == ('3' if d == 'v2_secded' else '4')
            if s == 'all' and d in ('v2_secded', 'v2c'):
                assert v == idx[('v2', g, f, 'all')]

@pytest.mark.skipif(shutil.which('iverilog') is None, reason='iverilog not installed')
@pytest.mark.parametrize('top', ['v2_secded', 'v2c'])
def test_functional_bench(top, tmp_path):
    out = str(tmp_path / 'tb.out')
    subprocess.run(['iverilog', '-g2005', '-o', out, os.path.join(ROOT, 'tb', f'tb_{top}.v'), os.path.join(ROOT, 'rtl', f'{top}.v')], check=True, timeout=120)
    r = subprocess.run(['vvp', '-n', out], capture_output=True, text=True, timeout=300)
    assert 'FUNC_PASS' in r.stdout and 'FAIL' not in r.stdout.replace('FUNC_FAIL', '')
    triple = [l for l in r.stdout.splitlines() if 'triple' in l][0]
    assert triple.endswith('8 of 280' if top == 'v2_secded' else '0 of 280')   # SIMULATED: the corrector completes 3-flop errors
