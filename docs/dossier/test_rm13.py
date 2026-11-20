#!/usr/bin/env python3
"""License: Apache-2.0. GlitchSAT.

Self-contained pytest: the Reed-Muller code RM(1,3) and the 8-bit words used in rtl/v1.v and rtl/v2.v.

BIT-ORDER CONVENTION. A byte b (written in hex as in the RTL, e.g. 8'h96) is read as a truth table:
bit i of b (bit 0 = least significant) is the value f(x) of a Boolean function f at the point
x = (x2, x1, x0) = the 3-bit binary expansion of i. Under this convention the coordinate functions are
x0 -> 0xAA, x1 -> 0xCC, x2 -> 0xF0, and their complements are 0x55, 0x33, 0x0F.
RM(1,3) = all affine functions of (x2, x1, x0) = the span over GF(2) of {0xFF, 0x0F, 0x33, 0x55}
(the same span as {0xFF, 0xF0, 0xCC, 0xAA}). The test also checks that reading the byte MSB-first
gives the same code, so the membership claims do not depend on the bit order.

What is a FACT here (arithmetic, checked below): membership, length 8, dimension 4, minimum distance 4,
weight enumerator 1 + 14 z^4 + z^8, distances between the state words.
What is NOT claimed: that anyone chose RM(1,3) on purpose; anything about circuits or hardware.

Comparisons with stored repo data (skipped if the files are absent; read-only):
  * research/c5/anchor/bf_*.json (brute-force attack-set counts over ALL netlist sites, stem-flip model):
    these are NOT a codeword weight enumerator, so only a bound is comparable: the measured minimum
    over all nets is <= the flops-only code distance d = 4 (the decoder sets a ceiling), and no
    attacking set of size 1 or 2 exists on V2 spike.
  * research/c3/m1/m1_all_masks.csv: the 27 "colliding" masks are exactly the masks on which an idle
    word (F0 or CC) already agrees with 96 (masked distance 0), and for every mask the solver minimum
    is <= the masked Hamming distance from {F0, CC} to 96 (the flop route is always available).
Run: python3 -m pytest -q docs/comms/test_rm13.py
"""
import csv
import glob
import itertools
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GEN = [0xFF, 0x0F, 0x33, 0x55]
RTL_WORDS = {"F0": 0xF0, "CC": 0xCC, "96": 0x96, "69": 0x69, "C3": 0xC3}
STATE_CODE = [0xF0, 0xCC, 0x96, 0x69]  # IDLE, CMP, BOOT, FAIL in rtl/v1.v and rtl/v2.v
GROUPS = {"m0": {0, 3, 6}, "m1": {1, 4, 7}, "m2": {2, 5}}  # from sel = {m1,m0,m2,m1,m0,m2,m1,m0} in rtl/v2.v


def wt(x):
    return bin(x).count("1")


def span(gens):
    code = set()
    for coeffs in itertools.product([0, 1], repeat=len(gens)):
        w = 0
        for c, g in zip(coeffs, gens):
            if c:
                w ^= g
        code.add(w)
    return code


def rev8(x):
    return int(f"{x:08b}"[::-1], 2)


def affine_truth_table(a0, a1, a2, c):
    """Truth table of f(x) = c + a0 x0 + a1 x1 + a2 x2 under the convention above."""
    b = 0
    for i in range(8):
        x0, x1, x2 = i & 1, (i >> 1) & 1, (i >> 2) & 1
        if (c ^ (a0 & x0) ^ (a1 & x1) ^ (a2 & x2)) & 1:
            b |= 1 << i
    return b


RM13 = span(GEN)


def test_coordinate_functions_match_convention():
    assert affine_truth_table(1, 0, 0, 0) == 0xAA
    assert affine_truth_table(0, 1, 0, 0) == 0xCC
    assert affine_truth_table(0, 0, 1, 0) == 0xF0
    assert {affine_truth_table(*t) for t in itertools.product([0, 1], repeat=4)} == RM13


def test_parameters_n8_k4_d4():
    assert len(RM13) == 2 ** 4           # dimension 4 (generators independent)
    assert max(RM13) <= 0xFF             # length 8
    d = min(wt(w) for w in RM13 if w)    # linear code: d = minimum nonzero weight
    assert d == 4
    assert d == min(wt(a ^ b) for a, b in itertools.combinations(RM13, 2))


def test_weight_enumerator():
    A = {w: sum(1 for c in RM13 if wt(c) == w) for w in range(9)}
    assert A == {0: 1, 1: 0, 2: 0, 3: 0, 4: 14, 5: 0, 6: 0, 7: 0, 8: 1}
    print("RM(1,3) weight enumerator A_w:", {w: a for w, a in A.items() if a})


@pytest.mark.parametrize("name", list(RTL_WORDS))
def test_rtl_words_are_codewords(name):
    w = RTL_WORDS[name]
    assert w in RM13, f"0x{name} is not in RM(1,3)"
    assert rev8(w) in RM13  # MSB-first reading: still a member


def test_convention_independent():
    assert {rev8(c) for c in RM13} == RM13


def test_rtl_words_as_affine_functions():
    # which affine function each word is (fact under the stated convention)
    names = {}
    for a0, a1, a2, c in itertools.product([0, 1], repeat=4):
        names[affine_truth_table(a0, a1, a2, c)] = (a0, a1, a2, c)
    assert names[0xF0] == (0, 0, 1, 0)   # x2
    assert names[0xCC] == (0, 1, 0, 0)   # x1
    assert names[0x96] == (1, 1, 1, 0)   # x0 + x1 + x2
    assert names[0x69] == (1, 1, 1, 1)   # 1 + x0 + x1 + x2
    assert names[0xC3] == (0, 1, 1, 1)   # 1 + x1 + x2


def test_state_code_distances():
    D = {(a, b): wt(a ^ b) for a, b in itertools.combinations(STATE_CODE, 2)}
    assert min(D.values()) == 4
    assert D[(0x96, 0x69)] == 8          # complementary pair
    assert sorted(D.values()) == [4, 4, 4, 4, 4, 8]


def test_all_flop_burst_maps_fail_to_accept():
    # one modelled 'burst' that inverts all 8 state bits: 69 -> 96 (difference 0xFF); arithmetic only
    assert 0x69 ^ 0xFF == 0x96
    assert 0xF0 ^ 0xFF not in (0x96,) and 0xCC ^ 0xFF not in (0x96,)


def test_repetition_view_of_decision_bit():
    # the match bit m copied n times is a repetition code [n,1,n]
    for n in (2, 3):
        rep = span([(1 << n) - 1])
        assert len(rep) == 2 and min(wt(c) for c in rep if c) == n


def test_groups_touched_by_idle_to_accept_differences():
    # which comparator-copy groups the flop route F0->96 and CC->96 must touch (arithmetic only)
    def touched(diff):
        return sorted(g for g, bits in GROUPS.items() if any((diff >> b) & 1 for b in bits))
    assert 0xCC ^ 0x96 == 0x5A and touched(0x5A) == ["m0", "m1"]
    assert 0xF0 ^ 0x96 == 0x66 and touched(0x66) == ["m0", "m1", "m2"]
    assert touched(0x96 ^ 0x69) == ["m0", "m1", "m2"]


ANCHOR = sorted(glob.glob(str(REPO / "research/c5/anchor/bf_*_T*_k*.json")))


@pytest.mark.skipif(not ANCHOR, reason="research/c5/anchor not present")
def test_anchor_minima_below_flop_distance():
    d_flops = 4
    seen = {}
    for f in ANCHOR:
        j = json.load(open(f))
        if j.get("model") != "stem_flip":
            continue
        att = {int(k): v for k, v in j["attacking_by_size"].items()}
        if j["netlist"] == "v2_spike.json":
            assert att.get(1, 0) == 0 and att.get(2, 0) == 0
        if j.get("min_cost") is not None:
            assert j["min_cost"] < d_flops   # all-nets minimum below the code distance: decoder ceiling
        seen[Path(f).name] = (j["netlist"], j["T"], j["K"], j["min_cost"], att)
    for k, v in seen.items():
        print("anchor", k, "netlist=%s T=%s K=%s min=%s attacking_by_size=%s" % v)


M1CSV = REPO / "research/c3/m1/m1_all_masks.csv"


@pytest.mark.skipif(not M1CSV.exists(), reason="research/c3/m1 not present")
def test_m1_masks_consistent_with_masked_distance():
    rows = list(csv.DictReader(open(M1CSV)))
    assert len(rows) == 255
    coll = 0
    for r in rows:
        m = int(r["mask_hex"], 16)
        dmask = min(wt((s ^ 0x96) & m) for s in (0xF0, 0xCC))
        assert (dmask == 0) == (r["collides_with_legit_state"] == "1")
        coll += dmask == 0
        for col in ("v1_spike_min_flips", "v2_spike_min_flips", "v2_apt033_min_flips"):
            assert int(r[col]) <= dmask
    assert coll == 27
    print("M1 masks: 27 colliding = masked distance 0; solver minimum <= masked distance on 255/255 masks")
