"""One test per RT3 finding F2, F3, F5. Modelled bit flips only; toy designs."""
import os, re, subprocess, sys, time
import pytest
from faultbound_wt import cli, config, runner
from faultbound_wt.cli import example_dir
from faultbound_wt.config import ConfigError

EX = example_dir()
V2 = os.path.join(EX, "v2.json")
TH = os.path.join(EX, "threat.toml")
PROD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_f2_cycles_cap_is_documented_value():
    assert config.MAX_CYCLES == 200


@pytest.mark.parametrize("n", ["201", "100000", "1000000000"])
def test_f2_cli_cycles_above_cap_is_exit3_fast(n, capsys):
    t0 = time.time()
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "1", "--cycles", n]) == 3
    err = capsys.readouterr().err
    assert "maximum of 200" in err and time.time() - t0 < 10


def test_f2_toml_cycles_above_cap_is_exit3(tmp_path, capsys):
    cfg = tmp_path / "t.toml"
    cfg.write_text(open(TH).read().replace("[faults]", "[faults]\ncycles = 5000", 1) if "cycles" not in open(TH).read() else re.sub(r"cycles\s*=\s*\d+", "cycles = 5000", open(TH).read()))
    assert cli.main(["analyze", V2, "--config", str(cfg)]) == 3
    assert "maximum of 200" in capsys.readouterr().err


def test_f2_cycles_at_cap_is_accepted_by_validate():
    th = config.load(TH)
    th.cycles = config.MAX_CYCLES
    config.validate(th)
    th.cycles = config.MAX_CYCLES + 1
    with pytest.raises(ConfigError):
        config.validate(th)


def test_f2_verdict_unchanged_at_default_cycles():
    th = config.load(TH)
    th.max_flips = 3
    assert runner.analyze(V2, th)["verdict"] == "ATTACK_FOUND"


def test_f2_help_and_quickstart_mention_cap():
    out = subprocess.run([sys.executable, "-m", "faultbound_wt.cli", "analyze", "--help"], capture_output=True, text=True, timeout=60).stdout
    assert "maximum 200" in re.sub(r"\s+", " ", out)
    assert "Maximum `--cycles` is 200" in open(os.path.join(PROD, "QUICKSTART.md")).read()


def test_f3_pyyaml_in_test_extra():
    txt = open(os.path.join(PROD, "pyproject.toml")).read()
    m = re.search(r"\[project\.optional-dependencies\](.*?)(\n\[|\Z)", txt, re.S)
    assert m and re.search(r"test\s*=\s*\[[^\]]*pytest[^\]]*pyyaml", m.group(1))


def test_f5_report_into_missing_dir_is_exit3_before_solve(tmp_path, capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("solve ran before the report-dir check")
    monkeypatch.setattr(runner, "analyze", boom)
    bad = str(tmp_path / "nope" / "x.json")
    assert cli.main(["analyze", V2, "--config", TH, "--report", bad]) == 3
    err = capsys.readouterr().err
    assert "does not exist" in err and "nope" in err
    assert cli.main(["analyze", V2, "--config", TH, "--badge", str(tmp_path / "nope" / "b.json")]) == 3


def test_f5_report_into_existing_dir_still_works(tmp_path):
    out = tmp_path / "r.json"
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "1", "--report", str(out)]) == 0
    assert out.exists()
