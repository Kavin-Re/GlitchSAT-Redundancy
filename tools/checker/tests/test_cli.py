import json
import os
import shutil
import subprocess
import sys

import pytest
import yaml

from conftest import EXT
from survival import cli, pipeline, report

GOAL = dict(output="boot_word", value=0x96, input="sig", key=0xC3)


def _cfg(tmp_path, root, netlists, name="cfg.yaml", **extra):
    cfg = dict(name="v2", top="v2", intent=dict(rtl=[os.path.join(root, "rtl", "v2.v")], reference="none"), goal=GOAL,
               stages=[dict(name=n, netlist=os.path.join(root, p)) for n, p in netlists])
    cfg.update(extra)
    p = tmp_path / name
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


REF = ("synth", "reference/spike_netlists/v2.json")
FLAT = ("flat", "validation/nl/v2.json")
APT = ("apt", "research/c2/e2_variance/baseline_netlists/apt0.33_v2.json")


def test_exit_0_when_everything_survives(root, tmp_path, capsys):
    assert cli.main(["check-survival", _cfg(tmp_path, root, [REF]), "--json", str(tmp_path / "r.json")]) == 0
    rep = json.load(open(tmp_path / "r.json"))
    assert rep["schema"] == "glitchsat-survival/1" and rep["summary"]["verdict"] == "PASS"
    assert {c["verdict"] for c in rep["countermeasures"]} == {"SURVIVED"}
    assert rep["stages"][0]["margin"]["min_faults"] == 3
    assert "PASS" in capsys.readouterr().out


def test_exit_1_on_removed_with_cause_and_fix(root, tmp_path, capsys):
    code = cli.main(["check-survival", _cfg(tmp_path, root, [REF, FLAT]), "--json", str(tmp_path / "r.json"), "--md", str(tmp_path / "r.md")])
    assert code == 1
    rep = json.load(open(tmp_path / "r.json"))
    cp = next(c for c in rep["countermeasures"] if c["kind"] == "redundant_copies")
    assert cp["verdict"] == "REMOVED" and cp["broken_at"] == "flat"
    r = cp["stages"][1]
    assert r["cause"] and len(r["fix"]) >= 2 and any("ext/harden" in f for f in r["fix"])
    assert rep["summary"]["margin_drop"] == dict(rep["summary"]["margin_drop"], reference=3, min_faults=1, stage="flat")
    out = capsys.readouterr().out
    assert "REMOVED" in out and "why:" in out and "fix:" in out and "margin dropped from 3" in out
    assert "| 3 copies of cmp8(sig) | rtl-scan | SURVIVED | REMOVED |" in open(tmp_path / "r.md").read()


def test_margin_drop_without_structural_cause(root, tmp_path, capsys):
    """apt 0.33 mapping: copies and encoding intact, yet 2 flips instead of 3. Reported as a margin drop, exit 1."""
    assert cli.main(["check-survival", _cfg(tmp_path, root, [REF, APT]), "--json", str(tmp_path / "r.json"), "--quiet"]) == 1
    rep = json.load(open(tmp_path / "r.json"))
    assert {c["verdict"] for c in rep["countermeasures"]} == {"SURVIVED"}
    d = rep["summary"]["margin_drop"]
    assert (d["reference"], d["min_faults"], d["explained_by"]) == (3, 2, []) and "no tracked countermeasure changed" in d["text"]


def test_exit_2_when_untracked(root, tmp_path):
    assert cli.main(["check-survival", _cfg(tmp_path, root, [FLAT]), "--no-margin", "--quiet"]) == 2


def test_exit_3_on_bad_input(tmp_path, capsys):
    assert cli.main(["check-survival", str(tmp_path / "missing.yaml")]) == 3
    p = tmp_path / "bad.yaml"
    p.write_text("name: x\n")
    assert cli.main(["check-survival", str(p)]) == 3
    assert "stages" in capsys.readouterr().err


def test_fail_on_policy(root, tmp_path):
    cfg = _cfg(tmp_path, root, [REF, FLAT])
    assert cli.main(["check-survival", cfg, "--no-margin", "--quiet", "--fail-on", "never"]) == 0
    assert cli.main(["check-survival", cfg, "--no-margin", "--quiet", "--fail-on", "removed"]) == 1


def test_margin_target(root, tmp_path):
    cfg = _cfg(tmp_path, root, [APT], margin=dict(k=3, cycles=6, min=3))
    assert cli.main(["check-survival", cfg, "--json", str(tmp_path / "r.json"), "--quiet"]) == 1
    assert json.load(open(tmp_path / "r.json"))["summary"]["margin_below_target"] == [dict(stage="apt", min_faults=2, target=3)]


def test_no_config_form(root, tmp_path):
    code = cli.main(["check-survival", "--rtl", os.path.join(root, "rtl/v2.v"), "--top", "v2", "--no-margin", "--quiet",
                     "--netlist", os.path.join(root, REF[1]), "--netlist", os.path.join(root, FLAT[1]),
                     "--json", str(tmp_path / "r.json")])
    rep = json.load(open(tmp_path / "r.json"))
    if rep["stages"][0]["name"] == "rtl":            # Yosys present: the checker added its own reference
        assert len(rep["stages"]) == 3
    assert code == 1


def test_sarif_passes_product_checks(root, tmp_path):
    out = tmp_path / "r.sarif"
    cli.main(["check-survival", _cfg(tmp_path, root, [REF, FLAT]), "--sarif", str(out), "--quiet", "--repo-root", root])
    doc = json.load(open(out))
    assert doc["version"] == "2.1.0"
    res = doc["runs"][0]["results"]
    assert [r["ruleId"] for r in res] == ["GSS001", "GSS003"]
    loc = res[0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "rtl/v2.v" and loc["region"]["startLine"] == 9      # the line of the three instances
    assert all(len(r["partialFingerprints"]["primaryLocationLineHash"]) == 34 for r in res)
    errs = report.validate_sarif(doc)
    if errs is None:
        pytest.skip("ext/product SARIF checker not available")
    assert errs == []


def test_diff_mode(root, tmp_path, capsys):
    good = _cfg(tmp_path, root, [("synth", REF[1])], name="good.yaml")
    bad = _cfg(tmp_path, root, [("synth", FLAT[1])], name="bad.yaml")
    base = str(tmp_path / "base.json")
    assert cli.main(["check-survival", good, "--json", base, "--quiet"]) == 0
    # same build again: no regression
    assert cli.main(["check-survival", good, "--baseline", base, "--quiet"]) == 0
    # the "commit" that flattens before optimising
    cur = str(tmp_path / "cur.json")
    assert cli.main(["check-survival", bad, "--baseline", base, "--json", cur, "--sarif", str(tmp_path / "d.sarif")]) == 1
    d = json.load(open(cur))["diff"]
    kinds = sorted(x["kind"] for x in d["regressions"])
    assert "margin" in kinds and ("verdict" in kinds or "disappeared" in kinds)
    assert "REGRESSION" in capsys.readouterr().out
    assert "GSS005" in [r["ruleId"] for r in json.load(open(tmp_path / "d.sarif"))["runs"][0]["results"]]
    # the other direction is an improvement, and --diff-only ignores findings that were already there
    assert cli.main(["check-survival", good, "--baseline", cur, "--quiet"]) == 0
    both = _cfg(tmp_path, root, [REF, FLAT], name="both.yaml")
    known = str(tmp_path / "known.json")
    assert cli.main(["check-survival", both, "--json", known, "--quiet"]) == 1
    assert cli.main(["check-survival", both, "--baseline", known, "--quiet"]) == 1               # findings still fail
    assert cli.main(["check-survival", both, "--baseline", known, "--diff-only", "--quiet"]) == 0  # unless only regressions count


def test_diff_detects_fewer_copies_and_margin():
    def rep(indep, verdict, m):
        return dict(countermeasures=[dict(id="c", title="copies", where="a.v:1", stages=[
            dict(stage="s", verdict=verdict, evidence=["e"], measured=dict(independent=indep))])],
            stages=[dict(name="s", margin=dict(status="attack", min_faults=m, bound=dict(k=3)))])
    d = report.diff(rep(3, "SURVIVED", 3), rep(2, "WEAKENED", 2))
    assert sorted(x["kind"] for x in d["regressions"]) == ["margin", "verdict"]
    d = report.diff(rep(3, "WEAKENED", 2), rep(2, "WEAKENED", 2))
    assert [x["kind"] for x in d["regressions"]] == ["count"]
    d = report.diff(rep(2, "WEAKENED", 2), rep(3, "SURVIVED", 3))
    assert not d["regressions"] and len(d["improvements"]) == 2
    gone = dict(countermeasures=[], stages=[])
    assert [x["kind"] for x in report.diff(rep(3, "SURVIVED", 3), gone)["regressions"]] == ["disappeared"]


def test_against_git_revision(root, tmp_path):
    """This commit vs main: main has the good netlist, the working tree the merged one."""
    if not shutil.which("git"):
        pytest.skip("git not installed")
    repo = tmp_path / "repo"
    (repo / "build").mkdir(parents=True)
    shutil.copy(os.path.join(root, "rtl/v2.v"), repo / "v2.v")
    shutil.copy(os.path.join(root, REF[1]), repo / "build/v2.json")
    (repo / "survival.yaml").write_text(yaml.safe_dump(dict(
        name="v2", top="v2", intent=dict(rtl=["v2.v"], reference="none"), stages=[dict(name="synth", netlist="build/v2.json")])))
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    for c in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "good"]):
        subprocess.run(["git", "-C", str(repo)] + c, check=True, env=env, capture_output=True)
    # second "commit" (kept in the working tree): a reference-compatible but merged netlist replaces the build output.
    # The merged netlist has no names, so the function is taken from the baseline's netlist kept as an extra stage.
    shutil.copy(os.path.join(root, REF[1]), repo / "build/v2_ref.json")
    shutil.copy(os.path.join(root, FLAT[1]), repo / "build/v2.json")
    (repo / "survival.yaml").write_text(yaml.safe_dump(dict(
        name="v2", top="v2", intent=dict(rtl=["v2.v"], reference="none"),
        stages=[dict(name="as-written", netlist="build/v2_ref.json"), dict(name="synth", netlist="build/v2.json")])))
    out = tmp_path / "r.json"
    code = cli.main(["check-survival", str(repo / "survival.yaml"), "--against", "main", "--no-margin", "--quiet", "--json", str(out)])
    assert code == 1
    d = json.load(open(out))["diff"]
    assert d["baseline"] == "main" and any(x["kind"] == "verdict" and x["now"] == "REMOVED" for x in d["regressions"])
    assert not (repo / ".git" / "worktrees").exists() or not os.listdir(repo / ".git" / "worktrees")


def test_launcher_and_scan(root):
    exe = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "glitchsat")
    env = dict(os.environ, GLITCHSAT_ROOT=root)
    p = subprocess.run([sys.executable, exe, "scan", os.path.join(root, "rtl/v2.v"), os.path.join(EXT, "firmware/src/rom_triple.c"),
                        os.path.join(root, "reference/spike_netlists/v2.json")], capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    assert "redundant_copies: 3 copies of cmp8(sig)" in p.stdout and "fw_repeated_check" in p.stdout
    assert "netlist-scan" in p.stdout and p.stdout.strip().endswith("countermeasure(s) found")
    assert subprocess.run([sys.executable, exe], capture_output=True, env=env).returncode == 3


@pytest.mark.parametrize("example,code", [("v2_synth.yaml", 1), ("firmware_triple.yaml", 1)])
def test_examples_run(root, example, code):
    cfgp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", example)
    cfg = pipeline.load_config(cfgp)
    for s in cfg["stages"]:
        for k in ("netlist", "elf"):
            if s.get(k) and not os.path.exists(os.path.join(os.path.dirname(cfgp), s[k])):
                pytest.skip("example inputs not at the expected relative path")
    assert cli.main(["check-survival", cfgp, "--no-margin", "--quiet"]) == code
