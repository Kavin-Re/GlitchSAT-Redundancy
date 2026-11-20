"""Async-reset failure, honest-input check, structural explanation text, scope block in all reports."""
import json, os, shutil, xml.etree.ElementTree as ET
import pytest
from faultbound_wt import cli, config, reports, runner
from faultbound_wt.cli import example_dir

EX = example_dir()
TH = os.path.join(EX, "threat.toml")
net = lambda n: os.path.join(EX, n)
SCOPE_KEYS = {"goal", "input_treatment", "init_state", "fault_model", "bounds", "netlist_sha256", "tool_version", "statement"}


def rep(design, k, cycles=6, **over):
    th = config.load(TH); th.max_flips = k; th.cycles = cycles
    for a, b in over.items(): setattr(th, a, b)
    return runner.analyze(net(design + ".json"), th)


def test_scope_block_in_every_format():
    r = rep("v0", 1)
    assert SCOPE_KEYS <= set(r["scope"]) and r["scope"]["statement"] == "bounded result under this model; not a proof of security"
    assert r["scope"]["netlist_sha256"] == r["provenance"]["netlist_sha256"]
    sarif = json.loads(reports.to_sarif(r))
    assert SCOPE_KEYS <= set(sarif["runs"][0]["properties"]["scope"])
    assert "not a proof of security" in sarif["runs"][0]["results"][0]["message"]["text"]
    assert "informationUri" not in sarif["runs"][0]["tool"]["driver"]
    ju = ET.fromstring(reports.to_junit(r))
    names = {p.get("name") for p in ju.iter("property")}
    assert {"scope_" + k for k in SCOPE_KEYS} <= names
    assert any(p.get("value") == r["scope"]["statement"] for p in ju.iter("property"))


def test_scope_in_text_output(capsys):
    cli.main(["analyze", net("v0.json"), "--config", TH, "--max-flips", "0"])
    out = capsys.readouterr().out
    for key in ("scope: goal", "scope: inputs", "scope: init state", "scope: fault model", "scope: bounds", "sha256", "tool version",
                "bounded result under this model; not a proof of security"):
        assert key in out


def test_wrong_legitimate_value_is_config_error(tmp_path, capsys):
    out = str(tmp_path / "r.json"); sar = str(tmp_path / "r.sarif")
    th = open(TH).read().replace("0xC3", "0x11")
    c = str(tmp_path / "t.toml"); open(c, "w").write(th)
    rc = cli.main(["analyze", net("v0.json"), "--config", c, "--report", out, "--report", sar])
    cap = capsys.readouterr()
    assert rc == 3 and "honest input does not reach the goal in the fault-free design" in cap.err
    assert json.load(open(out))["verdict"] == "CONFIGURATION_PROBLEM"
    assert json.load(open(sar))["runs"][0]["results"][0]["ruleId"] == "FBWT003"
    rc = cli.main(["analyze", net("v0.json"), "--config", c, "--no-honest-check"])   # explicit override: warning, not error
    assert rc in (0, 1) and "warning:" in capsys.readouterr().err


def test_missing_legitimate_value_warns(tmp_path, capsys):
    c = str(tmp_path / "t.toml")
    open(c, "w").write("[faults]\nmax_flips = 0\ncycles = 6\n[property]\noutput = \"boot_word\"\nbad_value = 0x96\n")
    rc = cli.main(["analyze", net("v0.json"), "--config", c])
    err = capsys.readouterr().err
    assert rc == 0 and "attacker.legitimate_value" in err and "NOT set" in err
    assert "attacker.legitimate_value" in rep("v0", 0, defaulted=["attacker.legitimate_value"])["scope"]["defaulted_config_values"]


def test_async_reset_is_clean_exit_3(tmp_path, capsys):
    d = dict(modules=dict(t=dict(ports=dict(clk=dict(direction="input", bits=[2]), r=dict(direction="input", bits=[3]), sig=dict(direction="input", bits=[4]),
             o=dict(direction="output", bits=[5])), netnames={}, cells=dict(
             f=dict(type="$_DFF_PN0_", connections=dict(C=[2], R=[3], D=[4], Q=[5]))))))
    p = str(tmp_path / "a.json"); json.dump(d, open(p, "w"))
    c = str(tmp_path / "t.toml"); open(c, "w").write('[attacker]\ninput="sig"\nlegitimate_value=0\n[property]\noutput="o"\nbad_value=1\n')
    rc = cli.main(["analyze", p, "--config", c, "--top", "t"])
    err = capsys.readouterr().err
    assert rc == 3 and "ASYNCHRONOUS" in err and "Traceback" not in err and "KeyError" not in err


def test_canned_redundancy_text_only_when_structure_supports_it():
    s1 = rep("v1", 1)["explanation"]["summary"]
    assert "parallel checks" in s1                      # v1 has two parallel check sub-circuits feeding the flipped gate
    for d in ("v0",):
        s = rep(d, 1)["explanation"]["summary"]
        assert "redundant" not in s and "parallel checks" not in s and "converge" not in s
    s3 = rep("v2", 3)["explanation"]["summary"]
    assert "redundant" not in s3 and "independent" not in s3 and "converge" not in s3
