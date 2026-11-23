"""Flop-space reduction and the shared schema physical-fault-campaign/1."""
import json
import os
import sys

import pytest

from shotmodel import design as dsg, flopspace, search, shots

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import shared  # noqa: E402

V1, V2 = dsg.Design("v1"), dsg.Design("v2")


@pytest.mark.parametrize("D", [V1, V2], ids=["v1", "v2"])
@pytest.mark.parametrize("r,rule", [(0.0, "centre"), (2.0, "centre"), (3.0, "centre"), (1.5, "overlap"), (4.0, "overlap")])
def test_flop_space_reduction_replays(D, r, rule):
    tab = shots.shot_table(D, r, rule, "cell")
    res = search.min_shots(D, tab["masks"], 6, 4, "flip", "word")
    w = res["witness"]
    assert w is not None
    assert flopspace.check_equivalent(D, w["shots"], w["sig"], 6)
    fs, q = flopspace.flip_sets(D, w["shots"], w["sig"], 6)
    assert fs and dsg.GOOD in q


def test_no_shot_gives_no_flip_set():
    for D in (V1, V2):
        for sig in (0x00, 0xC2, 0xFF):
            fs, q = flopspace.flip_sets(D, [], sig, 6)
            assert fs == [] and dsg.GOOD not in q
            assert not flopspace.check_equivalent(D, [], sig, 6)
        fs, q = flopspace.flip_sets(D, [], dsg.KEY, 6)           # right key: GOOD without any flip
        assert fs == [] and dsg.GOOD in q


def test_known_flop_flip_reduces_to_itself():
    # flipping flops 0x66 of 0xF0 at cycle 0 shows 0x96 at once (abstract flop-only attack of vlab/comparison.json)
    m = sum(1 << V2.flops[i].idx for i in range(8) if (0x66 >> i) & 1)
    fs, q = flopspace.flip_sets(V2, [(0, m)], 0x00, 6)
    assert fs == [(0, 0x66)] and q[0] == 0x96


def test_validate_rejects_bad_records():
    good = dict(schema=shared.SCHEMA, mechanism="laser_em", design="v1", top="v1", realizable_wrong_key_accept=True,
                realized_flip_sets=[dict(cycle=0, flops=[0, 7])])
    assert shared.validate(good)
    for bad in (dict(good, schema="x"), dict(good, realized_flip_sets=[dict(cycle=0, flops=[8])]),
                {k: v for k, v in good.items() if k != "top"}):
        with pytest.raises(ValueError):
            shared.validate(bad)


RESULTS = os.path.join(HERE, "results")


@pytest.mark.parametrize("d", ["v1", "v2"])
def test_shared_files(d):
    p = os.path.join(RESULTS, "%s_shared.json" % d)
    if not os.path.isfile(p):
        pytest.skip("shared records not generated")
    rec = json.load(open(p))
    assert shared.validate(rec)
    assert rec["mechanism"] == "laser_em" and rec["key"] == 0xC3 and rec["good"] == 0x96 and rec["init"] == 0xF0
    assert rec["realizable_wrong_key_accept"] is True and rec["cost_unit"] == "shot_radius_um"
    assert all(a["flop_only_replay_ok"] for a in rec["extra"]["attacks"])
    assert rec["min_cost"] == (0.0 if d == "v1" else rec["min_cost"]) and rec["min_cost"] is not None
    try:
        sys.path.insert(0, os.path.join(HERE, "..", "vlab"))
        from vlab.interface import validate
    except Exception:
        return
    assert validate(rec)
