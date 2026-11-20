"""Scope options: --consumer-bits, --goal-out/--accept-value, --input-sites, --init, --count-rule, --scope-sweep.
Reference numbers: research/c2/b2_scope/B2_REPORT.md (spike V2: full word 3, boot_ok 1, input sites 1, arbitrary init 0) and the M1 matrix
research/c3/m1/m1_all_masks.csv (column v2_spike_min_flips; copied below for 10 four-bit masks). Modelled bit flips only."""
import csv, json, os
import pytest
from faultbound_wt import cli, config, runner
from faultbound_wt.cli import example_dir
from faultbound_wt.config import ConfigError, parse_mask

EX = example_dir()
V0, V2 = os.path.join(EX, "v0.json"), os.path.join(EX, "v2.json")
TH = os.path.join(EX, "threat.toml")

# (mask, min flips on the spike V2, T=6, k<=3) from m1_all_masks.csv, popcount 4
M1_4BIT = [(0x8D, 1), (0x35, 1), (0x95, 1), (0xB4, 1), (0x2B, 2), (0x2E, 2), (0xE8, 2), (0x36, 2), (0x6A, 3), (0x72, 3)]


def rep(design, k, **over):
    th = config.load(TH)
    th.max_flips = k
    for a, b in over.items():
        setattr(th, a, b)
    config.validate(th)
    return runner.analyze(design, th)


def cost(r):
    return r["min_faults"] if r["verdict"] == "ATTACK_FOUND" else None


def test_defaults_unchanged_and_reported():
    r = rep(V2, 2)
    assert r["verdict"] == "NO_ATTACK_UP_TO_BOUND" and r["schema"] == "faultbound-wt-report/1"
    o = r["scope"]["options"]
    assert (o["consumer_bits"], o["input_sites"], o["init"]) == ("all", "none", "known") and o["count_rule"].startswith("stem")
    assert "all bits, combinationally evaluated" in r["scope"]["goal"]
    assert "input ports are NOT fault sites" in r["scope"]["input_treatment"]


def test_full_word_is_three_on_spike_v2():
    r = rep(V2, 3)
    assert cost(r) == 3
    assert cost(rep(V2, 3, consumer_bits=0xFF)) == 3      # full mask == no mask


def test_boot_ok_goal_is_one():
    r = rep(V2, 1, output="boot_ok", bad_value=1)
    assert cost(r) == 1 and r["faults"][0]["net"] == "boot_ok"
    assert "boot_ok" in r["scope"]["goal"]


def test_input_sites_all_is_one():
    r = rep(V2, 2, input_sites="all")
    assert cost(r) == 1 and r["faults"][0]["kind"] == "input_net"
    assert r["scope"]["options"]["input_sites"] == "all" and "IS a fault site" in r["scope"]["input_treatment"]
    assert "primary-input net" in r["explanation"]["summary"]


def test_init_arbitrary_is_zero_and_says_so_plainly():
    r = rep(V2, 2, init="arbitrary")
    assert r["verdict"] == "ATTACK_FOUND" and r["min_faults"] == 0 and r["faults"] == []
    assert "ZERO FLIPS NEEDED under ARBITRARY power-up state" in r["explanation"]["summary"]
    assert "not a fault-tolerance result" in r["explanation"]["summary"]
    assert "ARBITRARY power-up state" in r["scope"]["init_state"] and "no reset" in r["scope"]["init_state"]
    assert isinstance(r["initial_state_witness_flops_set_to_1"], list)


def test_honest_check_ignores_arbitrary_init_and_input_sites():
    r = rep(V2, 1, init="arbitrary", input_sites="all", legitimate_value=0x00)   # honest 0x00 never boots: still a configuration problem
    assert r["verdict"] == "CONFIGURATION_PROBLEM"


@pytest.mark.parametrize("mask,expect", M1_4BIT)
def test_four_bit_consumer_matches_m1_csv(mask, expect):
    r = rep(V2, 3, consumer_bits=mask)
    assert cost(r) == expect
    assert f"0x{mask:X}" in r["scope"]["goal"] and r["scope"]["options"]["consumer_bits"] == f"0x{mask:X}"


def test_m1_csv_agrees_if_present():
    p = os.path.join(os.path.dirname(__file__), "..", "..", "research", "c3", "m1", "m1_all_masks.csv")
    if not os.path.isfile(p):
        pytest.skip("research tree not present")
    rows = {int(r["mask_hex"], 16): r["v2_spike_min_flips"] for r in csv.DictReader(open(p))}
    for m, e in M1_4BIT:
        assert rows[m] == str(e)


def test_colliding_mask_needs_zero_flips():
    assert cost(rep(V2, 1, consumer_bits=0x18)) == 0     # M1: idle state already equals 0x96 on bits 3,4


def test_parse_mask_forms():
    assert parse_mask("0xF0") == 0xF0 and parse_mask("0-3,6") == 0x4F and parse_mask([0, 7]) == 0x81 and parse_mask(0x0F) == 0x0F
    for bad in (0, "0x0", "abc", "3-1", [-1], [True], "", 1.5, "0xZZ"):
        with pytest.raises(ConfigError):
            parse_mask(bad)


def test_toml_keys(tmp_path):
    p = tmp_path / "t.toml"
    p.write_text('[faults]\nmax_flips = 1\ninput_sites = "all"\ninit = "known"\ncount_rule = "stem"\n[property]\nconsumer_bits = "0-3"\n')
    t = config.load(str(p))
    assert (t.consumer_bits, t.input_sites, t.init) == (0xF, "all", "known")
    p.write_text('[faults]\ncount_rule = "branch"\n')
    t = config.load(str(p))
    with pytest.raises(ConfigError, match="NOT IMPLEMENTED"):
        config.validate(t)
    p.write_text('[faults]\ninit = "zero"\n')
    with pytest.raises(ConfigError):
        config.validate(config.load(str(p)))


def run(*a):
    return cli.main(["analyze", V2, "--config", TH, *a])


def test_cli_exit_codes(capsys):
    assert run("--count-rule", "branch") == 3
    assert "NOT IMPLEMENTED" in capsys.readouterr().err
    assert run("--consumer-bits", "0x0") == 3
    assert run("--consumer-bits", "0x1FF") == 3          # beyond the 8-bit output
    assert run("--accept-value", "zz") == 3
    assert run("--goal-out", "nope") == 3
    assert run("--max-flips", "1", "--goal-out", "boot_ok", "--accept-value", "1") == 1
    assert run("--max-flips", "2", "--input-sites", "all") == 1
    assert run("--max-flips", "0", "--init", "arbitrary") == 1
    assert run("--max-flips", "1", "--consumer-bits", "0x6A") == 0    # M1: 3 flips needed, so none with 1
    out = capsys.readouterr().out
    assert "scope: options:" in out and "consumer_bits=0x6A" in out


def test_scope_in_all_report_formats(tmp_path):
    j, s, x = (str(tmp_path / n) for n in ("o.json", "o.sarif", "o.junit.xml"))
    assert run("--max-flips", "1", "--input-sites", "all", "--report", j, "--report", s, "--report", x) == 1
    d = json.load(open(j))
    assert d["scope"]["options"]["input_sites"] == "all"
    assert json.load(open(s))["runs"][0]["properties"]["scope"]["options"]["input_sites"] == "all"
    assert "scope_options" in open(x).read()


def test_sweep_table_and_files(tmp_path, capsys):
    o, c = str(tmp_path / "s.json"), str(tmp_path / "s.csv")
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "2", "--scope-sweep", "--sweep-masks", "0xF", "--sweep-out", o]) == 1
    cli.main(["analyze", V2, "--config", TH, "--max-flips", "2", "--scope-sweep", "--sweep-out", c])
    out = capsys.readouterr().out
    assert "scope sweep" in out and "boot_ok==1" in out and "in-sites=all init=arbitrary" in out
    d = json.load(open(o))
    assert d["schema"] == "faultbound-wt-sweep/1"
    cell = {(x["goal"], x["input_sites"], x["init"]): x["cost"] for x in d["cells"]}
    assert cell[("boot_word==0x96", "none", "known")] == ">2"
    assert cell[("boot_word==0x96", "all", "known")] == "1"
    assert cell[("boot_word==0x96", "none", "arbitrary")] == "0"
    assert cell[("boot_ok==1", "none", "known")] == "1"
    assert cell[("boot_word bits 0xF", "none", "known")] == "2"
    assert open(c).read().startswith("goal,input_sites,init,verdict,cost,runtime_s")


def test_sweep_timeout_cells_are_unknown_and_exit_2(tmp_path):
    o = str(tmp_path / "s.json")
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "3", "--scope-sweep", "--cell-timeout-ms", "1", "--sweep-out", o]) == 2
    assert {c["cost"] for c in json.load(open(o))["cells"]} == {"unknown"}


def test_sweep_honest_input_wrong_is_exit_3(tmp_path):
    p = tmp_path / "t.toml"
    p.write_text("[attacker]\ninput = 'sig'\nlegitimate_value = 0\n[property]\noutput = 'boot_word'\nbad_value = 0x96\n")
    assert cli.main(["analyze", V0, "--config", str(p), "--max-flips", "1", "--scope-sweep"]) == 3
