"""Boolean functions of the sky130_fd_sc_hd cells that occur in the placed netlists.

The table is written by hand from the library's documented functions and is CHECKED against the transistor-level PDK
subcircuits shipped in the repository (switchlevel.py, tests/test_cells_and_mapping.py): every row below is compared with a
switch-level evaluation of the cell's transistor netlist on all input combinations.

Expressions use N(x) for NOT so that the same text evaluates on Python integers (bit-parallel lanes) and on numpy
boolean arrays.
"""
import re

# base name (drive strength stripped) -> (output pin, expression over input pins)
COMB = {
    "inv":      ("Y", "N(A)"),
    "clkinv":   ("Y", "N(A)"),
    "buf":      ("X", "A"),
    "clkbuf":   ("X", "A"),
    "nand2":    ("Y", "N(A & B)"),
    "nand3":    ("Y", "N(A & B & C)"),
    "nand4":    ("Y", "N(A & B & C & D)"),
    "nand2b":   ("Y", "N(N(A_N) & B)"),
    "nand3b":   ("Y", "N(N(A_N) & B & C)"),
    "nand4bb":  ("Y", "N(N(A_N) & N(B_N) & C & D)"),
    "nor2":     ("Y", "N(A | B)"),
    "nor4":     ("Y", "N(A | B | C | D)"),
    "nor4bb":   ("Y", "N(A | B | N(C_N) | N(D_N))"),
    "and2":     ("X", "A & B"),
    "and4":     ("X", "A & B & C & D"),
    "o21a":     ("X", "(A1 | A2) & B1"),
    "o21ai":    ("Y", "N((A1 | A2) & B1)"),
    "a21o":     ("X", "(A1 & A2) | B1"),
    "a21bo":    ("X", "(A1 & A2) | N(B1_N)"),
    "a21boi":   ("Y", "N((A1 & A2) | N(B1_N))"),
    "a22o":     ("X", "(A1 & A2) | (B1 & B2)"),
    "a2bb2oi":  ("Y", "N((N(A1_N) & N(A2_N)) | (B1 & B2))"),
    "mux2":     ("X", "(A1 & S) | (A0 & N(S))"),
}
FLOP = {"dfxtp": dict(clk="CLK", d="D", q="Q")}          # positive-edge D flip-flop, no reset
PHYSICAL_ONLY = ("fill", "decap", "tapvpwrvgnd")         # no signal pins
POWER_PINS = ("VPWR", "VGND", "VPB", "VNB")
_PREFIX = "sky130_fd_sc_hd__"


def base(master):
    """sky130_fd_sc_hd__nand4bb_1 -> nand4bb"""
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
    raise ValueError("cell %r has no function in shotmodel.cells (refusing to guess)" % master)


def input_pins(master):
    out, expr = COMB[base(master)]
    return sorted(set(re.findall(r"[A-Z][A-Z0-9_]*", expr)) - {"N"})


def output_pin(master):
    return COMB[base(master)][0]


_code = {}


def evaluate(master, pins, NOT):
    """Evaluate the cell on a dict pin -> value; NOT is the complement operator for the value type in use."""
    b = base(master)
    c = _code.get(b)
    if c is None:
        c = _code[b] = compile(COMB[b][1], "<cell %s>" % b, "eval")
    env = dict(pins)
    env["N"] = NOT
    return eval(c, {"__builtins__": {}}, env)


def truth_table(master):
    """tuple of output bits, index = sum(pin_i << i) over input_pins(master) in sorted order."""
    ins = input_pins(master)
    tt = []
    for x in range(1 << len(ins)):
        v = {p: (x >> i) & 1 for i, p in enumerate(ins)}
        tt.append(evaluate(master, v, lambda a: a ^ 1) & 1)
    return tuple(tt)
