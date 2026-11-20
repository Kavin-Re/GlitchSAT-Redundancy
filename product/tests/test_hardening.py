"""Product CLI exit codes, hostile netlists, JUnit well-formedness."""
import json, os, xml.etree.ElementTree as ET
import pytest
from faultbound_wt import cli, config, reports, runner
from faultbound_wt.cli import example_dir

EX = example_dir()
TH = os.path.join(EX, "threat.toml")


def base():
    return dict(modules=dict(t=dict(ports=dict(clk=dict(direction="input", bits=[2]), sig=dict(direction="input", bits=[3, 4]),
                boot_word=dict(direction="output", bits=[5, 6])), cells={}, netnames={})))


def add(d, name, ty, **con):
    d["modules"]["t"]["cells"][name] = dict(type=ty, connections={k: (v if isinstance(v, list) else [v]) for k, v in con.items()})


def go(tmp, d, *extra):
    p = os.path.join(str(tmp), "n.json"); json.dump(d, open(p, "w"))
    c = os.path.join(str(tmp), "t.toml")
    open(c, "w").write('[faults]\nmax_flips = 0\ncycles = 2\n[attacker]\ninput = "sig"\nmodel = "constant"\nlegitimate_value = 3\n'
                       '[property]\noutput = "boot_word"\nbad_value = 1\n')
    return cli.main(["analyze", p, "--config", c, "--top", "t", "--no-honest-check", *extra])


def good():
    d = base(); add(d, "a", "$_XOR_", A=3, B=4, Y=5); add(d, "z", "$_AND_", A=3, B="0", Y=6); return d


def test_exit_codes_distinct(tmp_path, capsys, monkeypatch):
    assert (cli.EXIT_OK, cli.EXIT_ATTACK, cli.EXIT_UNKNOWN, cli.EXIT_ERROR, cli.EXIT_INTERNAL) == (0, 1, 2, 3, 4)
    with pytest.raises(SystemExit) as e: cli.main(["analyze"])          # usage error must not be 2 (= solver unknown)
    assert e.value.code == 3
    monkeypatch.setattr(runner, "analyze", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert go(tmp_path, good()) == 4 and "internal error" in capsys.readouterr().err
    monkeypatch.setattr(runner, "analyze", lambda *a, **k: (_ for _ in ()).throw(RecursionError("deep")))
    assert go(tmp_path, good()) == 4


@pytest.mark.parametrize("mk,msg", [
    (lambda d: (add(d, "g1", "$_AND_", A=3, B=4, Y=5), add(d, "g2", "$_OR_", A=3, B=4, Y=5)), "multiple drivers"),
    (lambda d: (add(d, "g1", "$_AND_", A=3, B=99, Y=5),), "undriven"),
    (lambda d: (add(d, "g1", "$_OR_", A=3, B="x", Y=5),), "x/z"),
    (lambda d: (add(d, "g1", "$_NOT_", A=7, Y=5), add(d, "g2", "$_NOT_", A=5, Y=7)), "combinational loop"),
    (lambda d: (add(d, "l", "$_DLATCH_P_", D=3, E=4, Q=5),), "no Y output"),
    (lambda d: (add(d, "g1", "$_AND_", A=3, B=4, Y=5), add(d, "f", "$_DFF_P_", C=2, D=3, Q=5)), "multiple drivers"),
])
def test_malformed_netlists_exit_3(tmp_path, capsys, mk, msg):
    d = base(); mk(d); add(d, "z", "$_AND_", A=3, B="0", Y=6)
    assert go(tmp_path, d) == 3
    err = capsys.readouterr().err
    assert msg in err and "Traceback" not in err


def test_duplicate_key_and_x_init(tmp_path, capsys):
    p = os.path.join(str(tmp_path), "dup.json")
    open(p, "w").write('{"modules":{"t":{"ports":{},"cells":{"g":{},"g":{}},"netnames":{}}}}')
    assert cli.main(["analyze", p, "--config", TH, "--top", "t"]) == 3 and "duplicate JSON key" in capsys.readouterr().err
    d = base(); add(d, "f", "$_DFF_P_", C=2, D=7, Q=7); add(d, "b", "$_AND_", A=7, B=7, Y=5); add(d, "z", "$_AND_", A=3, B="0", Y=6)
    d["modules"]["t"]["netnames"]["q"] = dict(bits=[7], attributes=dict(init="x"))
    assert go(tmp_path, d) == 3 and "unknown" in capsys.readouterr().err


def test_deep_chain_no_recursion_error(tmp_path):
    d = base(); prev = 3
    for i in range(3000):
        add(d, f"n{i}", "$_NOT_", A=prev, Y=100 + i); prev = 100 + i
    d["modules"]["t"]["ports"]["boot_word"]["bits"] = [prev, 6]
    add(d, "z", "$_AND_", A=3, B="0", Y=6)
    th = config.load(TH); th.max_flips = 0; th.cycles = 1; th.legitimate_value = 3; th.bad_value = 1; th.honest_check = False
    p = os.path.join(str(tmp_path), "n.json"); json.dump(d, open(p, "w"))
    r = runner.analyze(p, th, top="t")
    assert r["verdict"] == "ATTACK_FOUND"


def test_junit_control_chars_well_formed(tmp_path):
    d = base(); add(d, "a", "$_XOR_", A=3, B=4, Y=5); add(d, "z", "$_AND_", A=3, B="0", Y=6)
    d["modules"]["t"]["netnames"]["evil\x01\x1f\ud800</failure>"] = dict(bits=[5], attributes={})
    th = config.load(TH); th.max_flips = 0; th.cycles = 2; th.legitimate_value = 3; th.bad_value = 1; th.honest_check = False
    p = os.path.join(str(tmp_path), "n.json"); json.dump(d, open(p, "w"))
    rep = runner.analyze(p, th, top="t")
    assert rep["verdict"] == "ATTACK_FOUND"
    out = os.path.join(str(tmp_path), "r.junit.xml"); reports.write(rep, out)
    ET.parse(out)                                                       # must be well-formed
    assert "\x01" not in open(out, encoding="utf-8").read()


def test_cli_prints_escaped_names(tmp_path, capsys):
    d = base(); add(d, "a", "$_XOR_", A=3, B=4, Y=5); add(d, "z", "$_AND_", A=3, B="0", Y=6)
    d["modules"]["t"]["netnames"]["x\n\x1b[31mred‮"] = dict(bits=[5], attributes={})
    assert go(tmp_path, d) == 1
    out = capsys.readouterr().out
    assert "\x1b" not in out and "‮" not in out
