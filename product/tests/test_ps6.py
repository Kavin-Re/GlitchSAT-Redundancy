"""Tests: counting rules (stem / fanout_pins / fanout_gates), the sweep counting-rule axis, and the synthesis-flow sweep
(--synth-sweep, --synth-variants). Yosys-dependent tests are skipped when yosys is not on PATH. Modelled bit flips only; toy designs."""
import csv, json, os, shutil, subprocess
import pytest
from faultbound_wt import cli, config, runner, _engine as eng, synth_sweep
from faultbound_wt.cli import example_dir

EX = example_dir()
V2 = os.path.join(EX, "v2.json")
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
RTL = os.path.join(ROOT, "rtl")
REP = os.path.join(ROOT, "research", "c3", "rep", "rep_results.csv")
needs_yosys = pytest.mark.skipif(shutil.which("yosys") is None, reason="yosys not on PATH")
needs_rtl = pytest.mark.skipif(not os.path.isfile(os.path.join(RTL, "v2.v")), reason="rtl/v2.v not present (installed package without the repository)")


def _th(rule, k=4, **kw):
    th = config.Threat(max_flips=k, cycles=6, count_rule=rule, **kw)
    config.validate(th)
    return th


def _cost(path, rule, k=4, top="v2", **kw):
    r = runner.analyze(path, _th(rule, k, **kw), top=top)
    return (r.get("min_cost", r["min_faults"]) if r["verdict"] == runner.ATTACK else f">{k}"), r


# ---- weights on a hand-made netlist
def _tiny(tmp_path):
    # a = input; n1 = a AND a (two pins on a); n2 = NOT n1 -> output y ; n1 also output port bit z. n1 feeds: NOT pin, output bit z.
    doc = {"modules": {"t": {"ports": {"a": {"direction": "input", "bits": [2]}, "y": {"direction": "output", "bits": [4]}, "z": {"direction": "output", "bits": [3]}},
                             "cells": {"g1": {"type": "$_AND_", "connections": {"A": [2], "B": [2], "Y": [3]}},
                                       "g2": {"type": "$_NOT_", "connections": {"A": [3], "Y": [4]}}},
                             "netnames": {"a": {"bits": [2], "attributes": {}}, "z": {"bits": [3], "attributes": {}}, "y": {"bits": [4], "attributes": {}}}}}}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(doc))
    return str(p)


def test_net_weights_hand_netlist(tmp_path):
    nl = eng.Netlist(_tiny(tmp_path), "t")
    assert eng.net_weights(nl, "stem") is None
    wp, wg = eng.net_weights(nl, "fanout_pins"), eng.net_weights(nl, "fanout_gates")
    assert wp[2] == wg[2] == 2          # input a feeds two pins of g1 (repeated pin counts twice)
    assert wp[3] == 2 and wg[3] == 1    # n1: NOT pin + output bit z (pins only counts the port bit)
    assert wp[4] == 1 and wg[4] == 1    # y: no sink pin, one output bit (pins) -> 1; gates -> floor of 1
    with pytest.raises(ValueError):
        eng.net_weights(nl, "branch")


# ---- spike V2: REP says 3 under all rules for the full word
@pytest.mark.parametrize("rule", ["stem", "fanout_pins", "fanout_gates"])
def test_spike_v2_word_is_3_under_every_rule(rule):
    c, r = _cost(V2, rule)
    assert c == 3
    assert r["scope"]["options"]["count_rule"].startswith(rule)
    assert r["schema"] == "faultbound-wt-report/1"


def test_stem_report_has_no_new_keys():
    _, r = _cost(V2, "stem")
    assert "min_cost" not in r and all("cost" not in f for f in r["faults"])


def test_fanout_report_adds_cost_keys_and_states_rule():
    c, r = _cost(V2, "fanout_pins")
    assert r["min_cost"] == 3 and r["min_faults"] == len(r["faults"])
    assert sum(f["cost"] for f in r["faults"]) == r["min_cost"]
    assert "COST" in r["scope"]["fault_model"] and "fanout_pins" in r["scope"]["options"]["count_rule"]
    assert any("fanout_pins" in l for l in runner.scope_lines(r["scope"]))


def test_input_sites_stem_1_but_fanout_costs_more():
    """An input bit is one stem flip, but it feeds several pins: the rule changes the answer (spike V2: 1 -> 3)."""
    assert _cost(V2, "stem", input_sites="all")[0] == 1
    assert _cost(V2, "fanout_pins", input_sites="all")[0] == 3


def test_fanout_budget_too_small_is_no_attack():
    c, r = _cost(V2, "fanout_pins", k=2)
    assert c == ">2" and r["verdict"] == runner.NO_ATTACK


# ---- CLI / config
def test_alias_fanout_recorded_as_fanout_pins(tmp_path):
    out = tmp_path / "r.json"
    assert cli.main(["analyze", V2, "--top", "v2", "--max-flips", "3", "--count-rule", "fanout", "--report", str(out)]) == 1
    assert json.loads(out.read_text())["threat_model"]["count_rule"] == "fanout_pins"


def test_branch_still_not_implemented_exit3(capsys):
    assert cli.main(["analyze", V2, "--top", "v2", "--count-rule", "branch"]) == 3
    assert "NOT IMPLEMENTED" in capsys.readouterr().err


def test_bad_rule_in_config_exit3(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[faults]\ncount_rule = "bogus"\n')
    assert cli.main(["analyze", V2, "--top", "v2", "--config", str(p)]) == 3


def test_config_key_fanout_gates(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[faults]\nmax_flips = 3\ncount_rule = "fanout_gates"\n')
    assert cli.main(["analyze", V2, "--top", "v2", "--config", str(p)]) == 1


def test_sweep_count_rule_axis(tmp_path, capsys):
    out = tmp_path / "s.json"
    rc = cli.main(["analyze", V2, "--top", "v2", "--scope-sweep", "--max-flips", "3", "--sweep-count-rules", "stem,fanout_pins,fanout_gates", "--sweep-out", str(out)])
    assert rc == 1
    sw = json.loads(out.read_text())
    assert sw["schema"] == "faultbound-wt-sweep/1" and sw["count_rule"] == "stem,fanout_pins,fanout_gates"
    got = {(c["goal"], c["input_sites"], c["init"], c["count_rule"]): c["cost"] for c in sw["cells"]}
    assert len(got) == 2 * 4 * 3   # goals boot_word, boot_ok x 4 scope columns x 3 rules
    assert got[("boot_word==0x96", "none", "known", "stem")] == "3"
    assert got[("boot_word==0x96", "none", "known", "fanout_pins")] == "3"
    assert got[("boot_word==0x96", "all", "known", "stem")] == "1"
    assert got[("boot_word==0x96", "all", "known", "fanout_pins")] == "3"
    assert "rule=fanout_gates" in capsys.readouterr().out


def test_sweep_without_axis_unchanged_columns(capsys):
    cli.main(["analyze", V2, "--top", "v2", "--scope-sweep", "--max-flips", "1"])
    o = capsys.readouterr().out
    assert "rule=" not in o and "count rule stem" in o


def test_sweep_rule_axis_rejects_branch_and_needs_sweep(capsys):
    assert cli.main(["analyze", V2, "--top", "v2", "--scope-sweep", "--sweep-count-rules", "stem,branch"]) == 3
    assert cli.main(["analyze", V2, "--top", "v2", "--sweep-count-rules", "stem"]) == 3


# ---- Yosys-dependent
def _yosys_033():
    v = runner.yosys_version() or ""
    return v.startswith("Yosys 0.33")


def _sweep_v2(tmp_path, *extra):
    out = tmp_path / "ss.json"
    rc = cli.main(["analyze", os.path.join(RTL, "v2.v"), "--top", "v2", "--synth-sweep", "--max-flips", "4", "--sweep-out", str(out), *extra])
    return rc, json.loads(out.read_text())


@needs_yosys
@needs_rtl
def test_synth_sweep_v2_documented_variants(tmp_path, capsys):
    rc, sw = _sweep_v2(tmp_path)
    assert rc == 1 and sw["schema"] == "faultbound-wt-synthsweep/1"
    names = [v["name"] for v in sw["variants"]]
    for n in ("plain", "plain_opt_merge", "flatten_before_abc", "abc_fast", "opt_flow", "plain_keep_off"):
        assert n in names
    assert len(names) >= 6 and all(v["status"] == "ok" for v in sw["variants"])
    row = {v["name"]: v for v in sw["variants"]}
    assert all(len(v["netlist_sha256"]) == 64 and v["flops"] == 8 and v["script"].startswith("read_verilog design.v\nhierarchy -top v2\n") for v in sw["variants"])
    assert sw["yosys"].startswith("Yosys")
    out = capsys.readouterr().out
    assert "verdict changes across" in out and "min flips ranged" in out
    if _yosys_033():   # EDU2 report: baseline 2 flips / 85 gates, opt_merge 1 flip / 63 gates (apt Yosys 0.33)
        assert (row["plain"]["cost"], row["plain"]["gates"]) == ("2", 85)
        assert (row["plain_opt_merge"]["cost"], row["plain_opt_merge"]["gates"]) == ("1", 63)
        assert sw["summary"]["line"].startswith("verdict changes across 8 variants: min flips ranged 1..2")


@needs_yosys
@needs_rtl
def test_synth_sweep_hashes_are_reproducible_and_location_independent(tmp_path):
    _, a = _sweep_v2(tmp_path)
    sub = tmp_path / "elsewhere"
    sub.mkdir()
    shutil.copy(os.path.join(RTL, "v2.v"), sub / "copy_of_design.v")
    out = tmp_path / "b.json"
    cli.main(["analyze", str(sub / "copy_of_design.v"), "--top", "v2", "--synth-sweep", "--max-flips", "4", "--sweep-out", str(out)])
    b = json.loads(out.read_text())
    assert [v["netlist_sha256"] for v in a["variants"]] == [v["netlist_sha256"] for v in b["variants"]]


@needs_yosys
@needs_rtl
def test_synth_sweep_custom_variants_toml_and_json_and_csv(tmp_path):
    t = tmp_path / "v.toml"
    t.write_text('[[variant]]\nname = "fast_merge"\nabc = "abc -fast -g AND,OR,XOR,MUX"\n'
                 'post = "opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_merge; opt_clean"\n')
    j = tmp_path / "v.json"
    j.write_text(json.dumps({"variant": [{"name": "noabc_like", "extends": "flatten_before_abc", "strip_keep": True}]}))
    csvp = tmp_path / "o.csv"
    rc = cli.main(["analyze", os.path.join(RTL, "v2.v"), "--top", "v2", "--synth-sweep", "--max-flips", "4", "--synth-variants", str(t),
                   "--synth-select", "plain,fast_merge", "--sweep-out", str(csvp)])
    assert rc == 1
    rows = list(csv.DictReader(open(csvp)))
    assert [r["variant"] for r in rows] == ["plain", "fast_merge"]
    if _yosys_033():
        assert (rows[0]["cost"], rows[1]["cost"]) == ("2", "1")
    out = tmp_path / "o.json"
    assert cli.main(["analyze", os.path.join(RTL, "v2.v"), "--top", "v2", "--synth-sweep", "--max-flips", "4", "--synth-variants", str(j),
                     "--synth-select", "noabc_like", "--sweep-out", str(out)]) == 1
    assert json.loads(out.read_text())["variants"][0]["name"] == "noabc_like"


@needs_yosys
@needs_rtl
def test_synth_sweep_with_fanout_rule(tmp_path):
    rc, sw = _sweep_v2(tmp_path, "--count-rule", "fanout_pins", "--synth-select", "plain,plain_opt_merge")
    assert sw["count_rule"] == "fanout_pins" and [v["verdict"] for v in sw["variants"]] and rc in (0, 1)


@needs_yosys
@needs_rtl
def test_synth_sweep_no_attack_variants_exit0_and_range(tmp_path):
    rc, sw = _sweep_v2(tmp_path, "--max-flips", "1", "--synth-select", "plain,abc_fast")   # 2 flips needed on these two (apt 0.33): none within 1
    if _yosys_033():
        assert rc == 0 and {v["cost"] for v in sw["variants"]} == {">1"} and sw["summary"]["changed"] is False


def test_synth_sweep_denied_commands_and_bad_files(tmp_path, capsys):
    for body in ('[[variant]]\nname="x"\npre="shell"\n', '[[variant]]\nname="x"\npost="write_verilog /tmp/zz.v"\n', '[[variant]]\nname="x"\nabc="!ls"\n',
                 '[[variant]]\nname="plain"\n', '[[variant]]\nname="a b"\n', '[[variant]]\nname="x"\nbogus=1\n', 'not toml ['):
        p = tmp_path / "bad.toml"
        p.write_text(body)
        with pytest.raises(config.ConfigError):
            synth_sweep.load_variants(str(p))
    with pytest.raises(config.ConfigError):
        synth_sweep.load_variants(str(tmp_path / "missing.json"))


def test_synth_sweep_json_input_exit3(capsys):
    assert cli.main(["analyze", V2, "--top", "v2", "--synth-sweep"]) == 3
    assert "Verilog" in capsys.readouterr().err


@needs_rtl
def test_synth_sweep_without_yosys_exit3_clear_message(monkeypatch, capsys):
    monkeypatch.setenv("PATH", "/nonexistent_ps6")
    assert cli.main(["analyze", os.path.join(RTL, "v2.v"), "--top", "v2", "--synth-sweep"]) == 3
    err = capsys.readouterr().err
    assert "yosys" in err and "PATH" in err


@needs_yosys
@needs_rtl
def test_synth_sweep_needs_top_and_exclusive_flags(capsys):
    assert cli.main(["analyze", os.path.join(RTL, "v2.v"), "--synth-sweep"]) == 3
    assert cli.main(["analyze", os.path.join(RTL, "v2.v"), "--top", "v2", "--synth-sweep", "--scope-sweep"]) == 3


@needs_yosys
@needs_rtl
def test_synth_sweep_timeout_is_unknown_exit2():
    assert cli.main(["analyze", os.path.join(RTL, "v2.v"), "--top", "v2", "--synth-sweep", "--timeout-s", "0.05"]) == 2


# ---- compare with REP (research/c3/rep/rep_results.csv): 10 apt-0.33 cells, same Yosys recipe
ABC = ["abc -g AND,OR,XOR,MUX", "abc -g AND,OR,XOR", "abc -fast -g AND,OR,XOR,MUX", "abc -fast -g AND,OR,XOR", "abc -g AND,OR", "abc -g AND,OR,MUX", None,
       "abc -g AND,OR,XOR,MUX -D 1000"]
CELLS = [("v2", "plain", i) for i in (0, 1, 2, 3, 4, 5, 7)] + [("v1", "plain", 0), ("v2", "opt", 0), ("v1", "opt", 3)]


@needs_yosys
@needs_rtl
@pytest.mark.skipif(not os.path.isfile(REP), reason="research/c3/rep/rep_results.csv not present")
@pytest.mark.parametrize("d,fl,i", CELLS)
def test_rep_cells(tmp_path, d, fl, i):
    if not _yosys_033():
        pytest.skip("REP's apt netlists need Yosys 0.33")
    pre = "synth -top %s; dffunmap" % d if fl == "opt" else "proc; opt_clean; techmap; opt_clean"
    out = tmp_path / "n.json"
    script = (f"read_verilog rtl/{d}.v; hierarchy -top {d}; {pre}; {ABC[i]}; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json {out}")
    subprocess.run(["yosys", "-q", "-p", script], cwd=ROOT, check=True, capture_output=True, timeout=120)
    R = {r["netlist"]: r for r in csv.DictReader(open(REP))}[f"{d}_{fl}_033_s{i}"]
    for rule, col in (("stem", "rep_unit_cli"), ("fanout_pins", "rep_fanout_pins"), ("fanout_gates", "rep_fanout_gates")):
        c, r = _cost(str(out), rule, top=d)
        assert str(c) == R[col], (rule, c, R[col])
    assert r["provenance"]["netlist_stats"]["gates"] == int(R["gates"])
    assert r["provenance"]["netlist_sha256"][:16] == R["sha16"]
