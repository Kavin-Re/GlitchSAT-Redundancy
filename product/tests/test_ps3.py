"""Badge, pytest helper, pre-commit entry, yosys flow script, action/hook YAML."""
import json, os, shutil, subprocess, sys
import pytest
from faultbound_wt import cli, precommit
from faultbound_wt.pytest_helper import assert_no_attack, check
from faultbound_wt.cli import example_dir

EX = example_dir()
V2 = os.path.join(EX, "v2.json")
TH = os.path.join(EX, "threat.toml")
PROD = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PIN = os.path.join(PROD, "examples", "pin_lock")
HAVE_SRC = os.path.isdir(PIN)
needs_yosys = pytest.mark.skipif(not shutil.which("yosys") or not HAVE_SRC, reason="yosys or source tree missing")


def test_badge_no_attack(tmp_path):
    b = tmp_path / "b.json"
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "2", "--badge", str(b)]) == 0
    d = json.loads(b.read_text())
    assert d["schemaVersion"] == 1 and d["label"] == "fault check"
    assert d["message"] == "no attack <=2 flips @ 6 cycles (scoped)"


def test_badge_attack_and_words(tmp_path):
    b = tmp_path / "b.json"
    assert cli.main(["analyze", os.path.join(EX, "v0.json"), "--config", TH, "--max-flips", "1", "--badge", str(b)]) == 1
    m = json.loads(b.read_text())["message"]
    assert "scoped" in m and m.startswith("attack found")
    for w in ("secure", "safe"):
        assert w not in m.lower()


def test_badge_never_secure_or_safe_any_verdict():
    from faultbound_wt import reports
    for v in ("NO_ATTACK_UP_TO_BOUND", "ATTACK_FOUND", "UNKNOWN_TIMEOUT", "CONFIGURATION_PROBLEM"):
        d = reports.badge(dict(verdict=v, bound=dict(max_flips=2, cycles=6), min_faults=2))
        assert "scoped" in d["message"] and "secure" not in d["message"].lower() and "safe" not in d["message"].lower()


def test_pytest_helper_pass():
    rep = assert_no_attack(V2, ("boot_word", 0x96), 2, 6, attacker_input="sig", legitimate_value=0xC3)
    assert rep["verdict"] == "NO_ATTACK_UP_TO_BOUND"
    assert_no_attack(V2, "boot_word==0x96", 2, 6, config_file=TH)


def test_pytest_helper_fail_message():
    with pytest.raises(AssertionError) as e:
        assert_no_attack(os.path.join(EX, "v0.json"), "boot_word==0x96", 1, 6, config_file=TH)
    msg = str(e.value)
    assert "ATTACK_FOUND" in msg and "minimal fault set (1)" in msg and "@" in msg
    assert "netlist_sha256" in msg and "not a proof of security" in msg and "fault_model" in msg


def test_pytest_helper_bad_goal():
    with pytest.raises(ValueError):
        check(V2, "nogoal", 1, 6)


def test_precommit_worst_exit(tmp_path, capsys):
    v0 = os.path.join(EX, "v0.json")
    assert precommit.main(["--config", TH, "--max-flips", "2", V2]) == 0
    assert precommit.main(["--config", TH, "--max-flips", "1", V2, v0]) == 1
    assert precommit.main(["--config", TH]) == 3
    assert precommit.main(["--config", TH, str(tmp_path / "missing.json")]) in (3,)


def test_yosys_flow_missing_yosys(tmp_path):
    script = os.path.join(PROD, "scripts", "yosys_flow.sh")
    if not os.path.isfile(script):
        pytest.skip("source tree missing")
    r = subprocess.run(["/bin/bash", script, "a.v", "top", str(tmp_path / "o.json")], capture_output=True, text=True,
                       env={"PATH": "/nonexistent"})
    assert r.returncode == 3 and "yosys not found" in r.stderr


@needs_yosys
def test_yosys_flow_and_verdict_hash(tmp_path):
    script = os.path.join(PROD, "scripts", "yosys_flow.sh")
    out = tmp_path / "pin.json"
    r = subprocess.run(["bash", script, os.path.join(PIN, "pin.v"), "pin", str(out)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "yosys: Yosys" in r.stdout
    sha = [l for l in r.stdout.splitlines() if l.startswith("netlist_sha256:")][0].split()[1]
    rep = check(out, "unlock==1", 1, 4, attacker_input="code", legitimate_value=10)
    assert rep["scope"]["netlist_sha256"] == sha
    assert rep["verdict"] == "ATTACK_FOUND"


@needs_yosys
def test_yosys_flow_bad_input(tmp_path):
    script = os.path.join(PROD, "scripts", "yosys_flow.sh")
    r = subprocess.run(["bash", script, str(tmp_path / "nope.v"), "pin", str(tmp_path / "o.json")], capture_output=True, text=True)
    assert r.returncode == 3
    r = subprocess.run(["bash", script, os.path.join(PIN, "pin.v"), "x;y", str(tmp_path / "o.json")], capture_output=True, text=True)
    assert r.returncode == 3


def test_yaml_files_parse():
    yaml = pytest.importorskip("yaml")
    for rel in ("action/action.yml", ".pre-commit-hooks.yaml"):
        p = os.path.join(PROD, rel)
        if not os.path.isfile(p):
            pytest.skip("source tree missing")
        d = yaml.safe_load(open(p))
        assert d
    a = yaml.safe_load(open(os.path.join(PROD, "action/action.yml")))
    assert a["runs"]["using"] == "composite" and "exit-code" in a["outputs"]
