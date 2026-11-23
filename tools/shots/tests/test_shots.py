"""Geometry, search, the r = 0 agreement with the single-fault model, and search vs plain enumeration."""
import os

import numpy as np
import pytest

from shotmodel import bruteforce, design as dsg, search, shots, sim

V1, V2 = dsg.Design("v1"), dsg.Design("v2")


@pytest.mark.parametrize("D", [V1, V2], ids=["v1", "v2"])
@pytest.mark.parametrize("rule", shots.RULES)
def test_r0_is_one_cell_per_shot(D, rule):
    tab = shots.shot_table(D, 0.0, rule, "cell")
    assert sorted(int(m) for m in tab["masks"]) == sorted(1 << c.idx for c in D.logic)


@pytest.mark.parametrize("D", [V1, V2], ids=["v1", "v2"])
def test_geometry_relations(D):
    for r in (0.5, 1.7, 3.0, 6.0):
        px, py = shots.aim_points(D, "cell")
        dc = shots._dist2(px, py, D.logic, "centre") <= (r + shots.EPS) ** 2
        do = shots._dist2(px, py, D.logic, "overlap") <= (r + shots.EPS) ** 2
        assert (do | ~dc).all()                                   # overlap footprint contains the centre footprint
        cell = {int(m) for m in shots.shot_table(D, r, "centre", "cell")["masks"]}
        grid = {int(m) for m in shots.shot_table(D, r, "centre", "grid", pitch=0.2)["masks"]}
        assert cell <= grid                                       # free aim contains every cell-aimed shot
    big = shots.shot_table(D, 100.0, "centre", "cell")
    assert [int(m) for m in big["masks"]] == [(1 << D.n) - 1]
    assert int(shots.shot_table(D, 100.0, "centre", "cell", targets="flops")["masks"][0]) == D.flop_mask
    assert len(shots.shot_table(D, 100.0, "centre", "cell", clk="forbid")["masks"]) == 0


def test_headline_values_at_r0():
    for D, word, ok in ((V1, 1, 1), (V2, 3, 1)):
        S = search.Searcher(D, shots.shot_table(D, 0.0, "centre", "cell")["masks"])
        assert S.min_shots(6, 4, "word")["min"] == word
        assert S.min_shots(6, 4, "ok")["min"] == ok
    S = search.Searcher(V2, shots.shot_table(V2, 0.0, "centre", "cell")["masks"])
    assert S.min_shots(2, 4, "word")["min"] == 4               # four state flops flipped: 0xF0 ^ 0x96 has 4 ones
    r = S.min_shots(2, 3, "word")
    assert r["min"] is None and r["searched_k"] == 3
    assert S.min_shots(3, 3, "word")["min"] == 3


@pytest.mark.parametrize("D", [V1, V2], ids=["v1", "v2"])
@pytest.mark.parametrize("effect", sim.EFFECTS)
def test_r0_equals_single_fault_model(D, effect):
    """exhaustive: every set of <= 2 single-cell faults over 4 cycles, against the shot search at r = 0"""
    T, K = 4, 2
    bf = bruteforce.single_flip(D, T, K, effect)
    S = search.Searcher(D, shots.shot_table(D, 0.0, "centre", "cell")["masks"], effect)
    assert {g: S.min_shots(T, K, g)["min"] for g in search.GOALS} == bf["min"]
    n = D.n * T
    assert bf["total"] == {0: 1, 1: n, 2: n * (n - 1) // 2}


@pytest.mark.skipif(not os.environ.get("SHOTS_SLOW"), reason="set SHOTS_SLOW=1 (several minutes): K = 3 enumeration")
def test_v2_r0_three_faults_enumerated():
    bf = bruteforce.single_flip(V2, 3, 3, "flip")
    assert bf["min"]["word"] == 3 and bf["word"][2] == 0


@pytest.mark.parametrize("D", [V1, V2], ids=["v1", "v2"])
@pytest.mark.parametrize("rule,r", [("centre", 2.0), ("centre", 3.0), ("overlap", 1.5), ("overlap", 4.0)])
def test_search_equals_enumeration(D, rule, r):
    T, K = 3, 2
    tab = shots.shot_table(D, r, rule, "cell")
    for effect in ("flip", "set0"):
        bf = bruteforce.enumerate_sets(D, tab["masks"], T, K, effect)
        S = search.Searcher(D, tab["masks"], effect)
        assert {g: S.min_shots(T, K, g)["min"] for g in search.GOALS} == bf["min"]


def test_witness_replays_and_is_minimal():
    for D in (V1, V2):
        for r in (0.0, 2.0, 3.0, 9.0):
            tab = shots.shot_table(D, r, "centre", "cell")
            for goal in search.GOALS:
                res = search.min_shots(D, tab["masks"], 6, 4, "flip", goal)
                if res["min"] is None:
                    continue
                w = res["witness"]
                assert len(w["shots"]) == res["min"] and w["sig"] != dsg.KEY
                assert search.replay(D, w, 6, "flip", goal)
                for i in range(len(w["shots"])):               # dropping any one shot of this witness loses the goal
                    w2 = dict(w, shots=w["shots"][:i] + w["shots"][i + 1:])
                    assert not search.replay(D, w2, 6, "flip", goal)   # fewer shots than the minimum cannot win


def test_sig_classes_partition_and_agree():
    for D in (V1, V2):
        cl = search.sig_classes(D)
        allm = sorted(m for _, ms in cl for m in ms)
        assert allm == [s for s in range(256) if s != dsg.KEY]
        # members of a class behave identically: same nets for a random disturbance pattern
        rng = np.random.default_rng(3)
        for _ in range(20):
            mask = int(rng.integers(0, 1 << D.n, dtype=np.uint64))
            st = [int(rng.integers(0, 2)) * sim.ALL for _ in range(8)]
            _m, _ok, nxt, _v = sim.cycle_int(D, st, mask)
            for _rep, ms in cl:
                assert len({sim.lane_word(nxt, s) for s in ms}) == 1


def test_backends_agree():
    rng = np.random.default_rng(5)
    for D in (V1, V2):
        masks = rng.integers(0, 1 << D.n, size=200, dtype=np.uint64)
        for effect in sim.EFFECTS:
            for s8, sig in ((0xF0, 0x00), (0xCC, 0xC3), (0xCC, 0x41), (0x69, 0xFF), (0x96, 0x12)):
                nxt, match, ok = sim.cycle_np(D, s8, sig, masks, effect)
                st = [sim.ALL if (s8 >> i) & 1 else 0 for i in range(8)]
                for i, m in enumerate(masks.tolist()):
                    mi, oki, ni, _ = sim.cycle_int(D, st, m, effect)
                    assert sim.lane_word(ni, sig) == int(nxt[i])
                    assert ((mi >> sig) & 1) == int(match[i]) and ((oki >> sig) & 1) == int(ok[i])


def test_union_levels():
    U = search.UnionLevels(np.array([1, 2, 4, 3], dtype=np.uint64))
    assert U.level(1).tolist() == [1, 2, 3, 4]
    assert U.level(2).tolist() == [5, 6, 7]                    # 3 = one shot already, so not level 2
    assert U.level(3).tolist() == []
    for j in (1, 2):
        for i, m in enumerate(U.level(j).tolist()):
            parts = U.decompose(j, i)
            assert len(parts) == j
            acc = 0
            for p in parts:
                acc |= int(U.levels[1][p])
            assert acc == m


def _mec_radius(pts):
    """Smallest enclosing circle of a few points (brute force over pairs and triples)."""
    import itertools, math
    cands = [(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), math.dist(a, b) / 2) for a, b in itertools.combinations(pts, 2)]
    for a, b, c in itertools.combinations(pts, 3):
        (ax, ay), (bx, by), (cx, cy) = a, b, c
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) > 1e-12:
            ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
            uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
            cands.append(((ux, uy), math.dist((ux, uy), a)))
    return min(r for c, r in cands if all(math.dist(c, p) <= r + 1e-9 for p in pts))


def _wrong_keys_accepted(D, names, effect):
    m = 0
    for n in names:
        m |= 1 << D.cell(n).idx
    hit = 0
    for match, _ok, _st in sim.run_int(D, 6, [(1, m)], effect):
        hit |= match
    hit &= ~(1 << dsg.KEY)
    return bin(hit).count("1")


def test_relation_to_LAY_radius():
    """README "Relation to LAY.radius": the nand4bb triple of LAY.radius has a 2.95 um enclosing circle and works as a
    flip and as a force-to-0; {c0/_2_, c1/_4_, c2/_4_} has a 1.67 um circle and works as a flip only."""
    lay = ["c0/_2_", "c1/_2_", "c2/_2_"]
    small = ["c0/_2_", "c1/_4_", "c2/_4_"]
    r = lambda ns: _mec_radius([(V2.cell(n).cx, V2.cell(n).cy) for n in ns])
    assert abs(r(lay) - 2.95) < 0.01 and abs(r(small) - 1.665) < 0.01
    assert _wrong_keys_accepted(V2, lay, "flip") == 15 and _wrong_keys_accepted(V2, lay, "set0") == 15
    assert _wrong_keys_accepted(V2, small, "flip") == 15 and _wrong_keys_accepted(V2, small, "set0") == 0


def test_overlap_shot_geometry_matches_readme():
    """Two copies share the corner (23.00, 8.16); the third is 0.46 um away; a 0.25 um disc at (22.75, 7.93) touches
    exactly c0/_2_, c1/_4_, c2/_2_ among the logic cells."""
    b = {n: V2.cell(n) for n in ("c0/_2_", "c1/_4_", "c2/_2_")}
    assert abs(b["c0/_2_"].x + b["c0/_2_"].w - 23.00) < 1e-6 and abs(b["c0/_2_"].y - 8.16) < 1e-6
    assert abs(b["c2/_2_"].x - 23.00) < 1e-6 and abs(b["c2/_2_"].y + b["c2/_2_"].h - 8.16) < 1e-6
    assert abs(b["c2/_2_"].x - (b["c1/_4_"].x + b["c1/_4_"].w) - 0.46) < 1e-6
    px, py = np.array([22.75]), np.array([7.93])
    d2 = shots._dist2(px, py, V2.logic, "overlap")[0]          # shape (npoints, ncells) -> this one point
    hit = sorted(c.name for c, d in zip(V2.logic, d2) if d <= (0.25 + shots.EPS) ** 2)
    assert hit == ["c0/_2_", "c1/_4_", "c2/_2_"]


def test_repo_root_env_and_alias(monkeypatch, tmp_path):
    from shotmodel import paths
    root = str(paths.repo_root())
    monkeypatch.setenv("GLITCHSAT_ROOT", root)
    assert str(paths.repo_root()) == root
    monkeypatch.delenv("GLITCHSAT_ROOT")
    monkeypatch.setenv("GLITCHSAT_REPO", root)
    assert str(paths.repo_root()) == root
    monkeypatch.setenv("GLITCHSAT_REPO", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        paths.repo_root()
