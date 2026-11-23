"""Static checks of the Verilog text (no simulator needed): Verilog-2005 subset, synchronous resets only, every flop
has a power-up value, constants equal the ones the model derives from FIPS 202, state codes equal model/spec.py."""
import glob, os, re
import pytest
from model import keccak as K
from model import spec as S
from model.variants import VARIANTS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RTL = sorted(glob.glob(os.path.join(HERE, 'rtl', '*.v')))
TOPS = sorted(glob.glob(os.path.join(HERE, 'rtl', 'tops', '*.v')))
GEN_TB = sorted(glob.glob(os.path.join(HERE, 'tb', 'gen', '*.v')))

# IEEE 1364-2005 reserved words (Annex B) that a port or signal name could collide with
V2005_KEYWORDS = set('''always and assign automatic begin buf bufif0 bufif1 case casex casez cell cmos config deassign default
defparam design disable edge else end endcase endconfig endfunction endgenerate endmodule endprimitive endspecify endtable
endtask event for force forever fork function generate genvar highz0 highz1 if ifnone incdir include initial inout input
instance integer join large liblist library localparam macromodule medium module nand negedge nmos nor noshowcancelled not
notif0 notif1 or output parameter pmos posedge primitive pull0 pull1 pulldown pullup pulsestyle_onevent pulsestyle_ondetect
rcmos real realtime reg release repeat rnmos rpmos rtran rtranif0 rtranif1 scalared showcancelled signed small specify
specparam strong0 strong1 supply0 supply1 table task time tran tranif0 tranif1 tri tri0 tri1 triand trior trireg unsigned
use uwire vectored wait wand weak0 weak1 while wire wor xnor xor'''.split())
SV_ONLY = ['logic', 'always_ff', 'always_comb', 'always_latch', 'typedef', 'enum', 'struct', 'interface', 'package',
           'import', 'unique', 'priority', 'bit', 'byte', 'int', 'shortint', 'longint', 'assert', 'property', 'expect',
           'final', 'chandle', 'string']


def strip_comments(t):
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    return re.sub(r'//[^\n]*', '', t)


def strip_strings(t):
    return re.sub(r'"[^"\n]*"', '""', t)


@pytest.mark.parametrize('path', RTL + TOPS + GEN_TB, ids=os.path.basename)
def test_verilog_2005_subset(path):
    t = strip_strings(strip_comments(open(path).read()))
    words = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', t))
    assert not (words & set(SV_ONLY)), f'SystemVerilog keywords: {words & set(SV_ONLY)}'
    assert not re.search(r"(?<![\w])'[01xzXZ]\b", t), 'SystemVerilog unsized fill literal'
    assert '++' not in t and '+=' not in t and '::' not in t
    assert not re.search(r'\$clog2|\$bits|\$countones|\$onehot', t)


@pytest.mark.parametrize('path', RTL + TOPS, ids=os.path.basename)
def test_synchronous_only_and_no_latches(path):
    t = strip_comments(open(path).read())
    assert 'negedge' not in t
    for m in re.finditer(r'always\s*@\s*\(([^)]*)\)', t):
        sens = m.group(1).strip()
        assert sens in ('posedge clk', '*'), f'sensitivity list {sens!r}: only `posedge clk` or `*` allowed'
    assert not re.search(r'\binitial\b[^;]*#', t), 'delays in initial'


@pytest.mark.parametrize('path', RTL + TOPS, ids=os.path.basename)
def test_no_identifier_is_a_verilog_keyword_misuse(path):
    t = strip_comments(open(path).read())
    for m in re.finditer(r'\b(input|output)\s+(?:wire|reg)?\s*(?:\[[^\]]*\])?\s*([A-Za-z_][A-Za-z0-9_]*)', t):
        assert m.group(2) not in V2005_KEYWORDS, f'port name {m.group(2)} is a Verilog keyword'


@pytest.mark.parametrize('path', [p for p in RTL if 'keccak_round' not in p and 'sb_cmp' not in p], ids=os.path.basename)
def test_every_register_has_a_power_up_value(path):
    t = strip_comments(open(path).read())
    regs = re.findall(r'\breg\s*(?:\[[^\]]*\])?\s*([A-Za-z_]\w*)\s*;', t)
    regs += re.findall(r'\breg\s*(?:\[[^\]]*\])?\s*([A-Za-z_]\w*)\s*;\s*initial', t)
    comb = {'rdata'}                  # combinational output reg of secboot_mmio (always @(*))
    for r in set(regs) - comb:
        assert re.search(rf'\binitial\s+{r}\s*=', t), f'register {r} has no initial value'


def test_keccak_round_constants_match_fips202_algorithms():
    t = open(os.path.join(HERE, 'rtl', 'sb_keccak_round.v')).read()
    rho = re.search(r'localparam \[25\*6-1:0\] RHO = \{([^}]*)\}', t).group(1)
    vals = [int(x.split("'d")[1]) for x in rho.replace('\n', ' ').split(',')]
    assert len(vals) == 25
    assert list(reversed(vals)) == [o % 64 for o in K.RHO]       # lane 0 in the low bits = last in the list
    rcs = dict((int(a), int(b, 16)) for a, b in re.findall(r"5'd(\d+):\s*rc64 = 64'h([0-9A-Fa-f]+);", t))
    assert rcs == {i: K.RC64[i] for i in range(24)}
    assert re.search(r"default:\s*rc64 = 64'h0+;", t)


def test_state_codes_and_mubi_values_match_spec():
    t = open(os.path.join(HERE, 'rtl', 'secboot_core.v')).read()
    for n, v in S.STATES.items():
        assert re.search(rf"localparam \[7:0\] S_{n}\s*=\s*8'h{v:02X};", t), n
    assert f"MUBI4_TRUE  = 4'h{S.MUBI4_TRUE:X}" in t and f"MUBI4_FALSE = 4'h{S.MUBI4_FALSE:X}" in t
    assert '(* fsm_encoding = "none" *) reg [7:0] st;' in t


def test_pad_constant_matches_model():
    t = open(os.path.join(HERE, 'rtl', 'sb_hash.v')).read()
    assert "PAD   = (ONE_R << (R - 1)) | 3'b110" in t
    assert K.pad_block(1088) == (1 << 1087) | 0b110


@pytest.mark.parametrize('v', VARIANTS, ids=lambda v: v.name)
def test_wrapper_has_one_attacker_input_and_one_goal_output(v):
    t = strip_comments(open(os.path.join(HERE, 'rtl', 'tops', f'{v.top}.v')).read())
    hdr = re.search(rf'module {v.top}\s*\((.*?)\);', t, flags=re.S).group(1)
    ports = re.findall(r'\b(input|output)\s+wire\s*(\[[^\]]*\])?\s*(\w+)', hdr)
    assert [(d, n) for d, _, n in ports] == [('input', 'clk'), ('input', 'sig'), ('output', v.goal_port)]
    assert ports[1][1] == '[7:0]' and ports[2][1] == f'[{v.goal_width - 1}:0]'
    assert ".rst(1'b0), .start(1'b1), .blk_valid(1'b1)" in t
