"""Tests: warning ignores flag-overridden keys, --timeout-s hard wall clock, --init free_nongoal,
explanation scope line, --sweep-widths against research/c3/m1/m1_all_masks.csv (spike V2). Modelled bit flips only."""
import csv, json, os, time
import pytest
from faultbound_wt import cli, config, runner
from faultbound_wt.cli import example_dir

EX = example_dir()
V2 = os.path.join(EX, "v2.json")
TH = os.path.join(EX, "threat.toml")
M1 = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "research", "c3", "m1", "m1_all_masks.csv"))


def test_warning_ignores_flag_overridden_keys(capsys):
    rc = cli.main(["analyze", V2, "--max-flips", "2", "--cycles", "6", "--goal-out", "boot_word", "--accept-value", "0x96"])
    err = capsys.readouterr().err
    assert rc == 0
    assert "attacker.input (default `sig`)" in err and "attacker.legitimate_value (default 0xC3)" in err
    assert "property.output" not in err and "property.bad_value" not in err


def test_warning_names_all_four_without_flags(capsys):
    cli.main(["analyze", V2, "--max-flips", "0"])
    err = capsys.readouterr().err
    assert all(k in err for k in ("attacker.input", "attacker.legitimate_value", "property.output", "property.bad_value"))


def test_timeout_is_hard_exit2_and_not_no_attack(tmp_path, capsys):
    out = tmp_path / "r.json"
    t0 = time.time()
    rc = cli.main(["analyze", V2, "--config", TH, "--max-flips", "3", "--timeout-s", "0.3", "--report", str(out)])
    assert rc == 2 and time.time() - t0 < 5
    r = json.loads(out.read_text())
    assert r["schema"] == "faultbound-wt-report/1" and r["verdict"] == "UNKNOWN_TIMEOUT" and r["timed_out"] is True
    assert "NOT 'no attack found'" in r["note"]
    assert "wall-clock timeout" in capsys.readouterr().out


def test_timeout_generous_gives_normal_verdict():
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "2", "--timeout-s", "120"]) == 0


def test_timeout_errors_still_exit3(tmp_path):
    assert cli.main(["analyze", str(tmp_path / "nope.json"), "--timeout-s", "5"]) == 3
    assert cli.main(["analyze", V2, "--timeout-s", "0"]) == 3


def test_free_nongoal_needs_at_least_one_flip(capsys):
    th = config.load(TH)
    th.max_flips, th.init = 2, "free_nongoal"
    config.validate(th)
    r = runner.analyze(V2, th)
    assert r["verdict"] == "ATTACK_FOUND" and r["min_faults"] == 1
    assert "never reaches the goal" in r["scope"]["init_state"]
    assert r["scope"]["options"]["init"] == "free_nongoal"
    th.max_flips = 0
    assert runner.analyze(V2, th)["verdict"] == "NO_ATTACK_UP_TO_BOUND"   # zero flips can never satisfy it
    with pytest.raises(SystemExit) as ei:
        cli.main(["analyze", V2, "--config", TH, "--max-flips", "1", "--init", "bogus"])
    assert ei.value.code == 3


def test_explanation_has_one_scope_line():
    th = config.load(TH)
    th.max_flips = 3
    r = runner.analyze(V2, th)
    e = r["explanation"]
    assert "known power-up state" in e["scope_line"] and "not a proof of security" in e["scope_line"] and "\n" not in e["scope_line"]
    assert e["summary"].endswith("[Scope: " + e["scope_line"] + "]")


def test_sweep_widths_matches_m1_csv(tmp_path, capsys):
    rows = {int(r["mask_hex"], 16): r["v2_spike_min_flips"] for r in csv.DictReader(open(M1))}
    out = tmp_path / "w.json"
    rc = cli.main(["analyze", V2, "--config", TH, "--sweep-widths", "--max-flips", "3", "--sweep-out", str(out)])
    assert rc == 1   # some cell found an attack
    sw = json.loads(out.read_text())
    assert sw["schema"] == "faultbound-wt-sweep/1" and sw["mode"] == "widths" and len(sw["cells"]) == 8
    for c in sw["cells"]:
        assert c["cost"] == rows[(1 << c["width"]) - 1], c
    assert [c["cost"] for c in sw["cells"]] == ["0", "1", "1", "2", "2", "3", "3", "3"]
    o = capsys.readouterr().out
    assert "consumer width curve" in o and "min flips" in o
