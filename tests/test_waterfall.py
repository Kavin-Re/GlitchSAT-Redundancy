"""Pins rows of results/comms/waterfall.csv and re-checks the small parts of
scripts/comms/bsc_channel.py. Numbers are SIMULATED under a random-flip teaching model (not an attacker model, not a
physical error rate); toy design, modelled bit flips. Row checks read the CSV only."""
import csv, json, math, os, sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'comms'))
np = pytest.importorskip('numpy')
import bsc_channel as bc

CSV = os.path.join(ROOT, 'results', 'comms', 'waterfall.csv')
PINS = {  # (design, p): (hits, trials, min_flips, A_dmin, key)
    ('V2-stored', '0.001'): ('172', '2500853760', '3', '80', '0xC7'),
    ('V2-apt', '0.001'): ('200', '67108864', '2', '3', '0x00'),
    ('V0', '0.001'): ('45282', '4194304', '1', '11', '0xC7'),
}
DMIN = {'V0': 1, 'V1': 1, 'V2-stored': 3, 'V2-apt': 2, 'V2e': 3}

def _rows():
    return list(csv.DictReader(open(CSV)))

@pytest.mark.parametrize('k', sorted(PINS))
def test_pinned_row(k):
    r = [x for x in _rows() if (x['design'], x['p']) == k][0]
    assert (r['hits'], r['trials'], r['min_flips'], r['A_dmin'], r['key']) == PINS[k]
    assert r['T'] == '4' and len(r['netlist_sha256']) == 64 and r['label'] == 'SIMULATED'

@pytest.mark.parametrize('d', sorted(DMIN))
def test_low_p_slope_is_min_flips(d):
    s = bc.low_p_slope(_rows(), d)
    assert s is not None and abs(s - DMIN[d]) <= 0.35

def test_csv_consistency():
    rows = _rows(); assert len(rows) == 45
    for r in rows:
        h, n = int(r['hits']), int(r['trials'])
        assert math.isclose(float(r['estimate']), h / n, rel_tol=1e-4)
        assert float(r['ci_lo']) <= h / n <= float(r['ci_hi'])
        assert float(r['ci_hi']) >= float(r['exact_series'])          # truncated series is a lower bound
        assert int(r['plotted']) == int(h >= 20)

def test_clopper_pearson_known_values():
    lo, hi = bc.clopper_pearson(5, 10)
    assert abs(lo - 0.18709) < 1e-4 and abs(hi - 0.81291) < 1e-4
    assert bc.clopper_pearson(0, 100)[0] == 0.0 and abs(bc.clopper_pearson(0, 100)[1] - 0.036217) < 1e-5

def test_enumerator_v0_and_tiny_mc():
    e = bc.enum_design('V0', 'reference/spike_netlists/v0.json', 'v0', 2)
    assert e['A_anykey'] == [0, 15, 999] and e['key'] == '0xC7' and e['A_key'] == [0, 11, 730] and e['N'] == 80
    bc._mc_init(os.path.join(ROOT, e['netlist']), 'v0')
    hits = sum(bc._mc_batch((np.random.SeedSequence([1, i]), 0xC7, 1e-3, 1 << 18)) for i in range(4))
    lo, hi = bc.clopper_pearson(hits, 1 << 20)
    assert lo <= bc.series([0, 11, 730, 23561], 80, 1e-3) <= hi * 1.01

def test_bernoulli_density():
    w = bc.bernoulli_words(np.random.default_rng(7), 64 * 200000, 0.01)
    assert abs(bc.popcount(w) / (64 * 200000) - 0.01) < 3e-4

def test_caption_wording():
    assert 'not an attacker model' in bc.CAPTION and 'not a physical error rate' in bc.CAPTION
    notes = open(os.path.join(ROOT, 'docs', 'comms', 'WATERFALL_NOTES.md')).read()
    assert 'not an attacker model' in notes and '' in notes
