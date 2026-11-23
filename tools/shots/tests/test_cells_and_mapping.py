"""Cell functions against the PDK transistor netlists; placed cells against the netlist; netlist against the RTL."""
import random
import re

import pytest

from shotmodel import cells, design as dsg, equiv, paths, switchlevel

ROOT = paths.repo_root()
SUBS = switchlevel.read_subckts(ROOT / paths.SPICE)
MASTERS = sorted({m for _, (_t, _d, nl, _n) in paths.DESIGNS.items()
                  for m in re.findall(r"sky130_fd_sc_hd__\w+", open(ROOT / nl).read())})
DESIGNS = {d: dsg.Design(d) for d in paths.DESIGNS}


@pytest.mark.parametrize("master", [m for m in MASTERS if cells.kind(m) == "comb"])
def test_comb_cell_matches_transistors(master):
    ins = cells.input_pins(master)
    assert switchlevel.comb_truth_table(SUBS[master], ins, cells.output_pin(master)) == cells.truth_table(master)


def test_flop_is_positive_edge_d_flop():
    rnd = random.Random(7)
    seq, c = [(0, 0), (1, 0), (0, 0)], 0
    for _ in range(1500):
        if rnd.random() < 0.5:
            c ^= 1
            seq.append((c, seq[-1][1]))
        else:
            seq.append((seq[-1][0], rnd.randint(0, 1)))
    got = switchlevel.flop_trace(SUBS["sky130_fd_sc_hd__dfxtp_1"], seq)
    q = 0
    for i, (cc, _d) in enumerate(seq):
        if i > 0 and seq[i - 1][0] == 0 and cc == 1:
            q = seq[i - 1][1]                      # D just before the rising edge
        if i >= 2:
            assert got[i] == q, i


def test_every_used_cell_is_known():
    for m in MASTERS:
        assert cells.kind(m) in ("comb", "flop", "physical")
    with pytest.raises(ValueError):
        cells.kind("sky130_fd_sc_hd__xor2_1")      # not in the table: must refuse, not guess


@pytest.mark.parametrize("d", list(paths.DESIGNS))
def test_placement_geometry(d):
    D = DESIGNS[d]
    x0, y0, x1, y1 = D.die
    row_y = {round(y, 3) for y, _ in D.rows}
    for c in D.all_cells:
        assert x0 <= c.x and c.x + c.w <= x1 and y0 <= c.y and c.y + c.h <= y1
        assert round(c.y, 3) in row_y and abs(c.h - 2.72) < 1e-9
    ov = D.overlaps()
    if d in ("v1", "v2"):
        assert ov == []                            # the two LVS-matching layouts are legal placements
    else:
        # MEASURED defect of the repo's hand-pinned variants: 2 or 3 pinned compare cells sit on top of a tap cell.
        assert 1 <= len(ov) <= 3 and all(a.startswith("TAP_") and b[:3] in ("c0/", "c1/", "c2/") for a, b in ov)
    assert len(D.flops) == 8 and len(D.clkbufs) == 3
    assert D.n == (35 if D.top == "v1" else 36)
    copies = {c.name.split("/")[0] for c in D.logic if "/" in c.name}
    assert copies == ({"c1", "c2"} if D.top == "v1" else {"c0", "c1", "c2"})


@pytest.mark.parametrize("d", list(paths.DESIGNS))
def test_netlist_equals_rtl_exhaustively(d):
    D = DESIGNS[d]
    assert equiv.check_transition(D) == dict(cases=65536, mismatches=0)
    b = equiv.check_boot(D, 8)
    assert b["mismatches"] == 0 and b["only_key_accepted"]


def test_equivalence_check_can_fail():
    """the check is not vacuous: V2's netlist is not V2e's RTL, and V1's is not V2's on every state"""
    assert equiv.check_transition(DESIGNS["v2"], rtl="v2e")["mismatches"] > 0
    assert equiv.check_boot(DESIGNS["v2"], 8, rtl="v2e")["mismatches"] > 0


def test_v2_variants_share_the_logic_netlist():
    def logic(D):
        # same cells, same data connections; only the clock-tree leaf feeding each flop may differ
        return sorted((c.name, c.master, tuple(sorted((p, n) for p, n in c.pins.items() if p != "CLK"))) for c in D.logic)
    base = logic(DESIGNS["v2"])
    for d in ("v2_v8", "v2_s8", "v2_v15", "v2_rr"):
        assert logic(DESIGNS[d]) == base
