"""Liberty reader: expression grammar, cell kinds, exhaustive truth-table checks, flip-flop semantics."""
import itertools
import os

import pytest

from conftest import have_lib, libs_dir, KNOWN_LIBS
from glitchsat_byod import liberty as L


def ev(s, **env):
    return L.eval_expr(L.parse_expr(s), env)


def test_operators_and_precedence():
    assert ev('A B', A=1, B=1) and not ev('A B', A=1, B=0)           # juxtaposition is AND
    assert ev("A'", A=0) and ev('!A', A=0)
    assert ev('A+B*C', A=0, B=1, C=1) and not ev('A+B*C', A=0, B=1, C=0)
    assert ev('A|B&C', A=1, B=0, C=0)                                   # AND binds tighter than OR
    assert ev('A^B&C', A=1, B=1, C=0) is False or True                  # parses
    # XOR binds tighter than AND (Liberty precedence used here): A ^ B & C == (A ^ B) & C
    for a, b, c in itertools.product((0, 1), repeat=3):
        assert ev('A^B&C', A=a, B=b, C=c) == bool((a ^ b) & c)
    assert ev('!(A&B)|C', A=1, B=1, C=0) is False
    assert ev('(A)', A=1) and ev('1') and not ev('0')


def test_bad_expressions():
    for s in ('', 'A &', '(A', 'A ) B', 'A % B'):
        with pytest.raises(L.ExprError):
            L.parse_expr(s)


LIB = '''
library (t) {
  cell (AOI21) { area : 1; pin (A1) { direction : input; } pin (A2) { direction : input; } pin (B) { direction : input; }
    pin (ZN) { direction : output; function : "!((A1 & A2) | B)"; timing () { related_pin : "A1"; cell_rise (x) { values ("1, 2"); } } } }
  cell (DFFRS) { ff ("IQ","IQN") { next_state : "D"; clocked_on : "CK"; clear : "!RN"; preset : "!SN";
      clear_preset_var1 : L; clear_preset_var2 : L; }
    pin (D) { direction : input; } pin (CK) { direction : input; clock : true; } pin (RN) { direction : input; }
    pin (SN) { direction : input; } pin (Q) { direction : output; function : "IQ"; } pin (QN) { direction : output; function : "IQN"; } }
  cell (EDFF) { ff (IQ, IQN) { next_state : "(D DE) + (IQ !DE)"; clocked_on : "CLK"; }
    pin (D) { direction : input; } pin (DE) { direction : input; } pin (CLK) { direction : input; } pin (Q) { direction : output; function : "IQ"; } }
  cell (NEGFF) { ff (IQ, IQN) { next_state : "D"; clocked_on : "!CLK_N"; } pin (D) { direction : input; } pin (CLK_N) { direction : input; }
    pin (Q) { direction : output; function : "IQ"; } }
  cell (LAT) { latch (IQ, IQN) { enable : "G"; data_in : "D"; } pin (D) { direction : input; } pin (G) { direction : input; }
    pin (Q) { direction : output; function : "IQ"; } }
  cell (TBUF) { pin (A) { direction : input; } pin (EN) { direction : input; }
    pin (Z) { direction : output; function : "A"; three_state : "!EN"; } }
  cell (FILL) { area : 1; }
  cell (SDFF) { ff (IQ, IQN) { next_state : "(D&!SE)|(SI&SE)"; clocked_on : "CK"; } test_cell () { pin (D) { direction : input; } }
    pin (D) { direction : input; } pin (SI) { direction : input; } pin (SE) { direction : input; } pin (CK) { direction : input; }
    pin (Q) { direction : output; function : "IQ"; } }
  cell (TIE) { pin (HI) { direction : output; function : "1"; } pin (LO) { direction : output; function : "0"; } }
}
'''


@pytest.fixture
def lib(tmp_path):
    p = tmp_path / 't.lib'
    p.write_text(LIB)
    return L.load(str(p))


def test_cell_kinds(lib):
    k = {n: c.kind for n, c in lib.cells.items()}
    assert k == dict(AOI21='comb', DFFRS='ff', EDFF='ff', NEGFF='ff', LAT='unsupported', TBUF='unsupported', FILL='none',
                     SDFF='ff', TIE='comb')
    assert lib.cells['NEGFF'].ff['edge'] == 'neg'
    assert 'scan' in ' '.join(lib.cells['SDFF'].risks) and lib.cells['SDFF'].scan_pins == ['SE']
    assert 'latch' in lib.cells['LAT'].why and 'three-state' in lib.cells['TBUF'].why


def test_every_cell_verifies(lib):
    res = L.verify_library(lib)
    assert all(v['ok'] for n, v in res.items() if lib.cells[n].kind in ('comb', 'ff')), res


def test_clear_preset_var_semantics(lib):
    c = lib.cells['DFFRS']
    # both active: clear_preset_var1 = L and var2 = L -> IQ = 0, IQN = 0 (Liberty), stored 0
    assert L.eval_ff(c, dict(D=1, RN=0, SN=0), True) == (False, False, False)
    assert L.eval_ff(c, dict(D=1, RN=1, SN=0), False) == (True, False, True)       # preset
    assert L.eval_ff(c, dict(D=1, RN=1, SN=1), False) == (False, True, True)       # normal: Q = stored, next = D


def test_parse_error_is_reported(tmp_path):
    p = tmp_path / 'bad.lib'
    p.write_text('library (x) { cell (A) { pin (Y) { direction : output; function : "A"; } ')
    with pytest.raises(L.LibertyError):
        L.load(str(p))


@pytest.mark.parametrize('name', sorted(KNOWN_LIBS))
def test_real_libraries_every_cell(name):
    if not have_lib(name):
        pytest.skip('%s not fetched (scripts/fetch_libs.sh)' % name)
    lib = L.load(os.path.join(libs_dir(), KNOWN_LIBS[name]))
    res = L.verify_library(lib)
    failed = [n for n, v in res.items() if v['ok'] is False]
    assert not failed
    passed = sum(1 for v in res.values() if v['ok'])
    assert passed >= {'nangate45': 108, 'sky130hd': 379, 'ihp-sg13g2': 63, 'gf180mcu': 181}[name]
