"""Golden + behaviour tests. Expected verdicts are the repo's MEASURED table (ci/expected_reproduce.json,
spike netlists, 6 cycles): V0, V1 attack at k=1; V2 none at k<=2, attack (3 flips) at k=3."""
import json, os, shutil, xml.etree.ElementTree as ET
import pytest
from faultbound_wt import cli, config, runner
from faultbound_wt.cli import example_dir

EX = example_dir()
net = lambda n: os.path.join(EX, n)
TH = os.path.join(EX, "threat.toml")


def run(design, k, cycles=6, extra=()):
    return cli.main(["analyze", net(design + ".json"), "--config", TH, "--max-flips", str(k), "--cycles", str(cycles), *extra])


def rep(design, k, cycles=6, **over):
    th = config.load(TH); th.max_flips = k; th.cycles = cycles
    for a, b in over.items(): setattr(th, a, b)
    return runner.analyze(net(design + ".json"), th)


@pytest.mark.parametrize("d", ["v0", "v1"])
def test_v0_v1_break_with_one_flip(d):
    r = rep(d, 1)
    assert r["verdict"] == "ATTACK_FOUND" and r["min_faults"] == 1
    assert rep(d, 0)["verdict"] == "NO_ATTACK_UP_TO_BOUND"


def test_v2_none_up_to_2_attack_at_3():
    assert rep("v2", 2)["verdict"] == "NO_ATTACK_UP_TO_BOUND"
    r = rep("v2", 3)
    assert r["verdict"] == "ATTACK_FOUND" and r["min_faults"] == 3


def test_provenance_block():
    r = rep("v0", 1)
    p = r["provenance"]
    assert len(p["netlist_sha256"]) == 64 and p["netlist_stats"]["gates"] > 0 and p["z3"] and p["python"]
    assert p["netlist_yosys_creator"] and "Yosys" in p["netlist_yosys_creator"]
    assert r["honest_input_reaches_goal_fault_free"] is True
    assert "BOUNDED" in r["note"]


def test_exit_codes_and_reports(tmp_path):
    j, s, x = (str(tmp_path / n) for n in ("o.json", "o.sarif", "o.junit.xml"))
    assert run("v0", 1, extra=["--report", j, "--report", s, "--report", x]) == 1
    assert run("v0", 0) == 0
    assert run("v0", 1, extra=["--exit-zero"]) == 0
    d = json.load(open(j)); assert d["verdict"] == "ATTACK_FOUND" and d["provenance"]["command"].startswith("faultbound-wt analyze")
    sa = json.load(open(s))
    assert sa["version"] == "2.1.0" and sa["runs"][0]["results"][0]["ruleId"] == "FBWT001"
    assert sa["runs"][0]["tool"]["driver"]["rules"][0]["id"] == "FBWT001"
    assert sa["runs"][0]["artifacts"][0]["hashes"]["sha-256"] == d["provenance"]["netlist_sha256"]
    t = ET.parse(x).getroot()
    assert t.tag == "testsuites" and t.find("testsuite/testcase/failure") is not None


def test_clean_reports_have_no_failure(tmp_path):
    s, x = str(tmp_path / "o.sarif"), str(tmp_path / "o.junit.xml")
    assert run("v0", 0, extra=["--report", s, "--report", x]) == 0
    assert json.load(open(s))["runs"][0]["results"] == []
    assert ET.parse(x).getroot().find("testsuite/testcase/failure") is None
    assert "BOUNDED" in open(x).read()


def test_errors_exit_3(tmp_path):
    assert cli.main(["analyze", str(tmp_path / "nope.json")]) == 3
    bad = tmp_path / "bad.json"; bad.write_text("{}")
    assert cli.main(["analyze", str(bad)]) == 3
    c = tmp_path / "c.toml"; c.write_text("[faults]\nbogus = 1\n")
    assert cli.main(["analyze", net("v0.json"), "--config", str(c)]) == 3
    c.write_text("[attacker]\nmodel = 'per-cycle'\n")
    assert cli.main(["analyze", net("v0.json"), "--config", str(c)]) == 3
    c.write_text("[property]\noutput = 'nope'\n")
    assert cli.main(["analyze", net("v0.json"), "--config", str(c)]) == 3
    assert cli.main(["analyze", net("v0.json"), "--report", str(tmp_path / "r.txt")]) == 3


def test_unsupported_cell_is_input_error(tmp_path):
    d = json.load(open(net("v0.json")))
    m = d["modules"]["v0"]; c = next(iter(m["cells"].values())); c["type"] = "$_NAND_"
    p = tmp_path / "n.json"; p.write_text(json.dumps(d))
    assert cli.main(["analyze", str(p)]) == 3


def test_site_filter_restricts_and_is_monotone():
    assert rep("v0", 1)["verdict"] == "ATTACK_FOUND"
    assert rep("v0", 1, kinds=["gate"])["sites"]["modelled"] < rep("v0", 1)["sites"]["modelled"]
    r = rep("v0", 3, include=["no_such_net_*"])          # nothing may be faulted -> same as k=0
    assert r["verdict"] == "NO_ATTACK_UP_TO_BOUND" and r["sites"]["modelled"] == 0
    # restricting sites can only remove attacks
    assert rep("v2", 2, kinds=["flop"])["verdict"] == "NO_ATTACK_UP_TO_BOUND"


@pytest.mark.skipif(not shutil.which("yosys"), reason="yosys not installed")
def test_verilog_input_records_yosys(tmp_path):
    th = config.load(TH); th.max_flips = 1
    r = runner.analyze(net("v0.v"), th, top="v0")
    assert r["verdict"] == "ATTACK_FOUND"
    assert "Yosys" in r["provenance"]["synthesis_yosys"] and r["provenance"]["source_sha256"]
