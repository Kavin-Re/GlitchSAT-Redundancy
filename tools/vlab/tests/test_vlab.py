"""Validation suite for the virtual glitch lab.

The load-bearing tests are the ones the task names:
  * infinite clock reproduces the zero-delay functional behaviour exactly over all 256 keys;
  * the placed-netlist mapping is cross-checked against the engine's own Yosys-JSON netlist by
    exhaustive simulation over all 256 keys.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from vlab import (abstract, campaign, cells, compare, delaymodel,  # noqa: E402
                  glitch, interface, netlist, sdf, sim)

DESIGNS = ["v1", "v2"]
REPO = netlist.repo_root()


@pytest.fixture(scope="module", params=DESIGNS)
def design(request):
    return netlist.Design(request.param)


# ---------------------------------------------------------------- structural / mapping

def test_eight_state_flops(design):
    assert len(design.flops) == 8
    assert [f.out for f in design.flops] == design.word_nets  # flop i drives boot_word[i]


def test_every_read_net_is_driven(design):
    driven = set(design.driver) | set(design.inputs)
    for c in design.comb:
        for p in cells.input_pins(c.master):
            assert c.pins[p] in driven


def test_cell_table_matches_pdk_transistor_netlists():
    """Every cell function used here is compared with a switch-level evaluation of the sky130 PDK transistor
    subcircuits in the repository (layout/v_designs/out_patched/v2_ref.spice), using the evaluator of
    ext/shots (shotmodel/switchlevel.py). Skipped when ext/shots is not next to this module."""
    shots = os.path.join(os.path.dirname(HERE), "shots")
    if not os.path.isfile(os.path.join(shots, "shotmodel", "switchlevel.py")):
        pytest.skip("ext/shots not present")
    import importlib.util
    spec = importlib.util.spec_from_file_location("_shots_switchlevel",
                                                  os.path.join(shots, "shotmodel", "switchlevel.py"))
    sl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sl)
    subs = sl.read_subckts(os.path.join(REPO, "layout/v_designs/out_patched/v2_ref.spice"))
    masters = sorted({c.master for did in DESIGNS for c in netlist.Design(did).comb})
    checked = 0
    for m in masters:
        if m not in subs:
            continue
        ins = cells.input_pins(m)
        tt = sl.comb_truth_table(subs[m], ins, cells.output_pin(m))
        assert tt == cells.truth_table(m), m
        checked += 1
    assert checked == len(masters), (checked, masters)


def test_cell_table_matches_switchlevel_free_consistency():
    # every cell used in both designs has a truth table of the right arity and is deterministic
    for did in DESIGNS:
        D = netlist.Design(did)
        for c in D.comb:
            tt = cells.truth_table(c.master)
            assert len(tt) == (1 << len(cells.input_pins(c.master)))
            assert set(tt) <= {0, 1}


# ---------------------------------------------------------------- functional oracle

def test_zero_delay_matches_rtl_semantics(design):
    # KEY accepts, every non-key sig is rejected, within the horizon
    acc = sim.accepts_wrong_key(design, 8)
    assert acc == 0                      # no wrong key is ever accepted fault-free
    states, accepted_key = sim.run_scalar(design, 8, netlist.KEY)
    assert accepted_key                  # the honest key boots
    assert states[0] == netlist.INIT and states[1] == 0xCC


def _engine_accepts(path, top, T=8):
    """Minimal Yosys-JSON simulator ($_AND_/OR/XOR/NOT/MUX/DFF_P), bit-parallel over 256 sigs.
    Returns the set of sig values that reach boot_word==GOOD within T cycles AND sig != KEY."""
    N = 256
    ALL = (1 << N) - 1
    SIG = [sum(1 << s for s in range(N) if (s >> i) & 1) for i in range(8)]
    m = json.load(open(path))["modules"][top]
    sigbits = m["ports"]["sig"]["bits"]
    out = m["ports"]["boot_word"]["bits"]
    gates, dffs = {}, []
    for c in m["cells"].values():
        con = c["connections"]
        if c["type"] == "$_DFF_P_":
            dffs.append((con["D"][0], con["Q"][0]))
        else:
            gates[con["Y"][0]] = (c["type"], {p: v[0] for p, v in con.items() if p != "Y"})
    init = {}
    for n, x in m["netnames"].items():
        if "init" in x["attributes"]:
            for i, b in enumerate(reversed(x["attributes"]["init"])):
                init[x["bits"][i]] = (b == "1")
    st = {q: (ALL if init.get(q, False) else 0) for _d, q in dffs}
    sidx = {b: i for i, b in enumerate(sigbits)}
    order, seen = [], set(st) | set(sigbits)

    def vis(b):
        if not isinstance(b, int) or b in seen:
            return
        seen.add(b)
        _t, p = gates[b]
        for v in p.values():
            vis(v)
        order.append(b)
    for d, _q in dffs:
        vis(d)
    for b in out:
        vis(b)
    hit = 0
    for _t in range(T):
        v = {}

        def g(b):
            if b == "0" or b == "x":
                return 0
            if b == "1":
                return ALL
            if b in sidx:
                return SIG[sidx[b]]
            return v[b]
        for q in st:
            v[q] = st[q]
        for b in order:
            ty, p = gates[b]
            if ty == "$_AND_":
                v[b] = g(p["A"]) & g(p["B"])
            elif ty == "$_OR_":
                v[b] = g(p["A"]) | g(p["B"])
            elif ty == "$_XOR_":
                v[b] = g(p["A"]) ^ g(p["B"])
            elif ty == "$_NOT_":
                v[b] = ALL ^ g(p["A"])
            elif ty == "$_MUX_":
                S = g(p["S"])
                v[b] = (g(p["B"]) & S) | (g(p["A"]) & (ALL ^ S))
            else:
                raise AssertionError(ty)
        match = ALL
        for i, b in enumerate(out):
            match &= g(b) if (netlist.GOOD >> i) & 1 else ALL ^ g(b)
        hit |= match
        st = {q: g(d) for d, q in dffs}
    return hit & (ALL ^ (1 << netlist.KEY))


def test_placed_matches_engine_netlist_exhaustively(design):
    """Cross-check the placed-netlist mapping against the engine's own netlist over all 256 keys."""
    eng = os.path.join(REPO, "reference/spike_netlists/%s.json" % design.id)
    engine_acc = _engine_accepts(eng, design.id, T=8)
    placed_acc = sim.accepts_wrong_key(design, 8)
    assert engine_acc == placed_acc == 0   # both: no wrong key accepted; identical behaviour


# ---------------------------------------------------------------- the glitch model

def test_infinite_clock_reproduces_oracle_over_all_keys(design):
    """THE validation: a very long period = zero-delay behaviour, for every sig and every offset."""
    dm = delaymodel.DelayModel(design)
    for sig in range(256):
        for offset in range(0, 7):
            r = glitch.glitch_shot(design, dm, 8, offset, 1e12, sig)
            assert r["outcome"] == "NO_EFFECT"
            assert r["realized_flips"] == []


def test_short_period_does_corrupt_but_never_accepts(design):
    """A shortened period must be able to corrupt state (model is not inert) yet never accept a wrong key."""
    dm = delaymodel.DelayModel(design)
    res = campaign.run(design, dm, T=8)
    tot = {k: sum(c["counts"][k] for c in res["cells"]) for k in ("SUCCESS", "CRASH", "NO_EFFECT")}
    assert tot["CRASH"] > 0            # the glitch does something
    assert tot["SUCCESS"] == 0         # but never a wrong-key accept


def test_oldnew_mix_check_uses_campaign_edges_all_sigs_and_continuation(design):
    """Hazard-free diagnostic: campaign offsets 1..7 with capture pair (S[t], S[t+1]), all 255 wrong sigs,
    fault-free continuation. GOOD is neither a mix nor reached from one, for V1 and V2."""
    chk = abstract.oldnew_mix_check(design, 8)
    assert chk["offsets"] == list(range(1, 8)) and chk["wrong_sigs_covered"] == 255
    assert chk["continuation_cycles"] == 20
    assert chk["distinct_wrong_key_trajectories"] == 1
    states = sim.run_scalar(design, 8, 0x00)[0]
    for e in chk["per_edge"]:
        assert (e["old_state"], e["new_state"]) == (states[e["offset"]], states[e["offset"] + 1])
    assert sum(e["n_wrong_sigs"] for e in chk["per_edge"]) == 255 * 7
    assert chk["good_reachable"] is False
    assert "not a proof" in chk["model"]


def test_capture_is_not_limited_to_oldnew_mixes():
    """The premise "each bit captures only old or new" does NOT hold in this lab's own event-driven
    simulator: V1, ASSUMED delays, offset 2, period 815.99 ps (on the campaign grid) captures 0x6d while
    old = new = 0x69 (bit 2 is neither). The campaign records such captures (nonmix_captures)."""
    D = netlist.Design("v1")
    dm = delaymodel.DelayModel(D)
    res = campaign.run(D, dm, T=8)
    assert 815.99 in res["periods_ps"]
    r = glitch.glitch_shot(D, dm, 8, 2, 815.99, 0x00)
    assert (r["old_next"], r["good_next"], r["captured"]) == (0x69, 0x69, 0x6D)
    assert r["nonmix_mask"] == 0x04
    nm = res["nonmix_captures"]
    assert nm["cells_total"] == 672
    assert nm["cells_wrong_key"] == 1 and nm["sig_cells_wrong_key"] == 255     # the (offset 2, 815.99 ps) cell
    assert nm["cells"] == 4    # + 3 cells where only the honest key 0xC3 captures a non-mix value
    assert all(c["counts"]["SUCCESS"] == 0 for c in res["cells"])   # still 0 wrong-key accepts


def test_v2_has_no_nonmix_capture_under_assumed_delays():
    D = netlist.Design("v2")
    res = campaign.run(D, delaymodel.DelayModel(D), T=8)
    assert res["nonmix_captures"]["cells"] == 0


def test_flop_only_abstract_attacks_exist_but_need_nonoldnew_values(design):
    fa = abstract.enumerate_flop_attacks(design, 8)
    assert fa["min_flips"] == 4        # flops-only single-cycle attacks exist at 4 flips
    assert not abstract.oldnew_mix_check(design, 8)["good_reachable"]


def test_classifier_detects_a_real_accept(design):
    """Non-vacuity: forcing the state to GOOD at a wrong key is detected as an accept by the oracle."""
    wrong = 0x00
    _states, accepted = sim.run_scalar(design, 8, wrong,
                                       forced_by_cycle={2: {f.out: (netlist.GOOD >> i) & 1
                                                             for i, f in enumerate(design.flops)}})
    assert accepted


# ---------------------------------------------------------------- determinism / interface / sdf

def test_campaign_deterministic(design):
    dm = delaymodel.DelayModel(design)
    a = campaign.run(design, dm, T=6)
    b = campaign.run(design, dm, T=6)
    assert [c["counts"] for c in a["cells"]] == [c["counts"] for c in b["cells"]]


def test_shared_interface_record(design):
    dm = delaymodel.DelayModel(design)
    res = campaign.run(design, dm, T=6)
    rec = interface.from_vlab_campaign(res)
    assert interface.validate(rec)
    assert rec["mechanism"] == "clock_glitch"
    assert rec["key"] == netlist.KEY


def test_sdf_loader_parses_iopath():
    txt = ('(DELAYFILE (SDFVERSION "3.0") (TIMESCALE 1 ns)\n'
           '(CELL (CELLTYPE "sky130_fd_sc_hd__inv_1") (INSTANCE _16_)\n'
           ' (DELAY (ABSOLUTE (IOPATH A Y (0.12:0.15:0.20) (0.10:0.13:0.18)))))\n')
    p = os.path.join(HERE, "tests", "_tmp.sdf")
    open(p, "w").write(txt)
    try:
        d = sdf.load_sdf(p)
        assert abs(d["_16_"] - 200.0) < 1e-6   # worst 0.20 ns -> 200 ps
    finally:
        os.remove(p)


def test_compare_design_realizability():
    for did in DESIGNS:
        c = compare.compare_design(did, T=8)
        assert c["realizable_by_single_clock_glitch"] is False
        assert c["abstract_flop_only_single_cycle_min"] == 4
        assert "reference netlist" in c["engine_abstract_min_flips_source"]
        assert "proof" not in json.dumps(c).replace("not a proof", "")
    c1 = compare.compare_design("v1", T=8)
    assert c1["engine_attack_sites_reference_netlist"] == [dict(net="ok", cycle=1)]   # merge AND `ok`


def test_repo_root_env_and_alias(monkeypatch, tmp_path):
    monkeypatch.setenv("GLITCHSAT_ROOT", REPO)
    assert netlist.repo_root() == REPO
    monkeypatch.delenv("GLITCHSAT_ROOT")
    monkeypatch.setenv("GLITCHSAT_REPO", REPO)
    assert netlist.repo_root() == REPO
    monkeypatch.setenv("GLITCHSAT_REPO", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        netlist.repo_root()


def test_stored_results_have_no_absolute_paths_and_carry_input_hashes():
    import glob
    for f in glob.glob(os.path.join(HERE, "results", "*.json")):
        txt = open(f).read()
        assert "/home/" not in txt, f
    for did in DESIGNS:
        r = json.load(open(os.path.join(HERE, "results", "%s_campaign.json" % did)))
        assert set(r["inputs"]) >= set(netlist.DESIGNS[did][1:]) | {netlist.LEF}
        for rel, h in r["inputs"].items():
            assert not rel.startswith("/") and len(h) == 64
