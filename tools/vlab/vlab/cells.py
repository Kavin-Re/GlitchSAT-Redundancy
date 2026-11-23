"""Boolean functions and timing arcs of the sky130_fd_sc_hd cells that appear in the
placed V1/V2 netlists (layout/v_designs/out_patched/*_pnr.v).

The boolean expressions are the library's documented cell functions. They are written so the
SAME text evaluates three ways:
  * on Python big-integers  (bit-parallel: 256 lanes = all values of `sig`),      NOT = `^ALL`
  * on numpy boolean arrays (one lane per candidate),                              NOT = np.logical_not
  * on a plain 0/1 int      (single scalar, used by the event-driven timing sim),  NOT = `lambda a: a^1`

This table is cross-checked in tests against the independent engine netlist behaviour
(reference/spike_netlists/{v1,v2}.json via a Yosys-JSON evaluator) over all 256 `sig` values,
so a wrong cell row cannot pass silently.  This is SOURCED from the sky130 PDK cell documentation.
"""
import re

_PREFIX = "sky130_fd_sc_hd__"

# base name (drive-strength suffix stripped) -> (output pin, boolean expression over input pins)
COMB = {
    "inv":     ("Y", "N(A)"),
    "clkbuf":  ("X", "A"),
    "buf":     ("X", "A"),
    "nand2":   ("Y", "N(A & B)"),
    "nand3":   ("Y", "N(A & B & C)"),
    "nand4":   ("Y", "N(A & B & C & D)"),
    "nand2b":  ("Y", "N(N(A_N) & B)"),
    "nand3b":  ("Y", "N(N(A_N) & B & C)"),
    "nand4bb": ("Y", "N(N(A_N) & N(B_N) & C & D)"),
    "nor2":    ("Y", "N(A | B)"),
    "nor4":    ("Y", "N(A | B | C | D)"),
    "nor4bb":  ("Y", "N(A | B | N(C_N) | N(D_N))"),
    "and2":    ("X", "A & B"),
    "and4":    ("X", "A & B & C & D"),
    "o21a":    ("X", "(A1 | A2) & B1"),
    "o21ai":   ("Y", "N((A1 | A2) & B1)"),
    "a21o":    ("X", "(A1 & A2) | B1"),
    "a21bo":   ("X", "(A1 & A2) | N(B1_N)"),
    "a21boi":  ("Y", "N((A1 & A2) | N(B1_N))"),
    "a22o":    ("X", "(A1 & A2) | (B1 & B2)"),
    "a2bb2oi": ("Y", "N((N(A1_N) & N(A2_N)) | (B1 & B2))"),
    "mux2":    ("X", "(A1 & S) | (A0 & N(S))"),
}
FLOP = {"dfxtp": dict(clk="CLK", d="D", q="Q")}     # positive-edge D flip-flop, no reset/scan
PHYSICAL_ONLY = ("fill", "decap", "tapvpwrvgnd")    # no signal pins; ignored
POWER_PINS = ("VPWR", "VGND", "VPB", "VNB")


def base(master):
    if not master.startswith(_PREFIX):
        raise ValueError("not a sky130_fd_sc_hd cell: %r" % master)
    return re.sub(r"_\d+$", "", master[len(_PREFIX):])


def kind(master):
    b = base(master)
    if b in FLOP:
        return "flop"
    if b in PHYSICAL_ONLY:
        return "physical"
    if b in COMB:
        return "comb"
    raise ValueError("cell %r has no entry in vlab.cells (refusing to guess)" % master)


def input_pins(master):
    _out, expr = COMB[base(master)]
    return sorted(set(re.findall(r"[A-Z][A-Z0-9_]*", expr)) - {"N"})


def output_pin(master):
    return COMB[base(master)][0]


_code = {}


def evaluate(master, pins, NOT):
    """Evaluate the cell on {pin: value}; NOT is the complement for the value type in use."""
    b = base(master)
    c = _code.get(b)
    if c is None:
        c = _code[b] = compile(COMB[b][1], "<cell %s>" % b, "eval")
    env = dict(pins)
    env["N"] = NOT
    return eval(c, {"__builtins__": {}}, env)


def truth_table(master):
    ins = input_pins(master)
    tt = []
    for x in range(1 << len(ins)):
        v = {p: (x >> i) & 1 for i, p in enumerate(ins)}
        tt.append(evaluate(master, v, lambda a: a ^ 1) & 1)
    return tuple(tt)
