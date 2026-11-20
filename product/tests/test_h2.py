"""One reproducer per RT2 finding N1..N14 (research/c5/rt2/RT2_REPORT.md).
Run against the pre-H2 source these tests fail; against the H2 source they pass. Modelled bit flips only; toy designs."""
import json, os, re, shutil, signal, subprocess, sys, tempfile, threading, time
import pytest
from faultbound_wt import cli, config, reports, runner, synth_sweep
from faultbound_wt.cli import example_dir
from faultbound_wt.config import ConfigError, parse_mask

EX = example_dir()
V2 = os.path.join(EX, "v2.json")
TH = os.path.join(EX, "threat.toml")
HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.dirname(HERE)
ROOT = os.path.dirname(PROD)
needs_yosys = pytest.mark.skipif(shutil.which("yosys") is None, reason="yosys not on PATH")

VSRC = "module m(input [7:0] sig, input clk, output [7:0] boot_word);\n reg [7:0] r; always @(posedge clk) r <= sig; assign boot_word = r;\nendmodule\n"
CFG = "[attacker]\ninput = \"sig\"\nlegitimate_value = 195\n[property]\noutput = \"boot_word\"\nbad_value = 195\n[faults]\nmax_flips = 1\ncycles = 3\n"


def _write_cfg(tmp_path, extra=""):
    p = tmp_path / "t.toml"
    p.write_text(CFG + extra)
    return str(p)


def _nl(ports, cells, names=None):
    return dict(creator="x", modules=dict(t=dict(ports=ports, cells=cells, netnames=names or {})))


def _P(d, bits):
    return dict(direction=d, bits=bits)


# ------------------------------------------------------------------ N1 (HIGH): command execution through the Yosys script
@needs_yosys
def test_n1_top_in_toml_cannot_run_a_command(tmp_path, capsys):
    canary = tmp_path / "pwned"
    (tmp_path / "m.v").write_text(VSRC)
    cfg = _write_cfg(tmp_path, f'[netlist]\ntop = "m; exec -- touch {canary}; hierarchy -top m"\n')
    rc = cli.main(["analyze", str(tmp_path / "m.v"), "--config", cfg])
    assert rc == 3 and not canary.exists() and "plain module identifier" in capsys.readouterr().err


@needs_yosys
def test_n1_top_on_cli_cannot_run_a_command(tmp_path, capsys):
    canary = tmp_path / "pwned"
    (tmp_path / "m.v").write_text(VSRC)
    rc = cli.main(["analyze", str(tmp_path / "m.v"), "--config", _write_cfg(tmp_path), "--top", f"m; exec -- touch {canary}; hierarchy -top m"])
    assert rc == 3 and not canary.exists()


@needs_yosys
def test_n1_file_name_cannot_run_a_command(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    canary = tmp_path / "pwned_fn"
    name = "m.v; exec -- touch pwned_fn; .v"
    (tmp_path / name).write_text(VSRC)
    cfg = _write_cfg(tmp_path)
    rc = cli.main(["analyze", name, "--config", cfg, "--top", "m"])
    assert rc == 3 and not canary.exists() and "not accepted" in capsys.readouterr().err


@pytest.mark.parametrize("top", ["m;x", "m x", "", "\\m", "m.n", "1m", "m\nx", "m'", 'm"', "m$$x;", "-m", "m" * 300])
def test_n1_check_top_rejects(top):
    with pytest.raises(runner.InputError):
        runner.check_top(top)


@pytest.mark.parametrize("top", ["m", "_a1", "$paramod_x", "Top_Module9"])
def test_n1_check_top_accepts(top):
    assert runner.check_top(top) == top


@pytest.mark.parametrize("p", ["a;b.v", "a\nb.v", "a\rb.v", "a\x01.v", 'a"b.v', "a'b.v", "a`b.v", "a\\b.v", "-x.v", "", "a#b.v", "a\x7f.v"])
def test_n1_check_path_rejects(p):
    with pytest.raises(runner.InputError):
        runner.check_path(p)


@needs_yosys
def test_n12_file_name_with_space_works(tmp_path, capsys):   # RT2 N12
    f = tmp_path / "my file.v"
    f.write_text(VSRC)
    rc = cli.main(["analyze", str(f), "--config", _write_cfg(tmp_path), "--top", "m"])
    assert rc in (0, 1), capsys.readouterr().err


def test_n1_yosys_is_run_from_a_script_file_without_p(tmp_path, monkeypatch):
    seen = {}

    def fake(args, cwd=None, timeout=600):
        seen["args"] = args
        seen["script"] = open(args[-1]).read()
        return 1, "", "stop"
    monkeypatch.setattr(runner, "run_yosys", fake)
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/yosys")
    out = tmp_path / "o.json"
    with pytest.raises(runner.InputError):
        runner.synthesize("dir with space/a b.v", "top", str(out))
    assert "-p" not in seen["args"] and seen["args"][1:3] == ["-q", "-s"]
    assert seen["script"].startswith('read_verilog "dir with space/a b.v"\nhierarchy -top top\n') and seen["script"].count("\n") == 7


@needs_yosys
def test_n1_yosys_flow_sh_does_not_execute_names(tmp_path):
    script = os.path.join(PROD, "scripts", "yosys_flow.sh")
    canary = tmp_path / "pwned"
    v = tmp_path / "a b.v"
    v.write_text(VSRC)
    r = subprocess.run(["bash", script, str(v), f"m; exec -- touch {canary}; hierarchy -top m", str(tmp_path / "o.json")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 3 and not canary.exists()
    bad_out = str(tmp_path / f"o\"; exec -- touch {canary}; \".json")
    r = subprocess.run(["bash", script, str(v), "m", bad_out], capture_output=True, text=True, timeout=60)
    assert r.returncode == 3 and not canary.exists()
    r = subprocess.run(["bash", script, str(v), "m", str(tmp_path / "o 2.json")], capture_output=True, text=True, timeout=60)   # spaces are fine now
    assert r.returncode == 0 and "netlist_sha256:" in r.stdout


def test_n1_yosys_flow_sh_refuses_newline_in_names(tmp_path):
    """A newline in a file name must be refused BEFORE any Yosys script is written: a second script line that starts with '!' is run by
    Yosys as a shell command. Uses a fake `yosys` on PATH that records whether it was reached, so the test needs no real Yosys."""
    script = os.path.join(PROD, "scripts", "yosys_flow.sh")
    fake = tmp_path / "bin"; fake.mkdir()
    reached = tmp_path / "reached"
    (fake / "yosys").write_text(f'#!/bin/sh\n[ "$1" = "-V" ] && {{ echo fake; exit 0; }}\ntouch "{reached}"\nexit 1\n')
    (fake / "yosys").chmod(0o755)
    env = dict(os.environ, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}")
    bad = tmp_path / "real.v\n!touch PWNED\nx"
    bad.write_text(VSRC)
    r = subprocess.run(["bash", script, str(bad), "m", str(tmp_path / "o.json")], capture_output=True, text=True, timeout=60, env=env, cwd=tmp_path)
    assert r.returncode == 3 and not reached.exists() and not (tmp_path / "PWNED").exists()
    ok = tmp_path / "a.v"; ok.write_text(VSRC)
    r = subprocess.run(["bash", script, str(ok), "m", str(tmp_path / "o\n!id\n.json")], capture_output=True, text=True, timeout=60, env=env, cwd=tmp_path)
    assert r.returncode == 3 and not reached.exists()


def test_n1_action_passes_inputs_through_env_only():
    text = open(os.path.join(PROD, "action", "action.yml"), encoding="utf-8").read()
    yaml = pytest.importorskip("yaml")
    d = yaml.safe_load(text)
    for st in d["runs"]["steps"]:
        if "run" in st:
            assert "${{" not in st["run"], f"inline expression interpolation in run: of step {st.get('name')}"


# ------------------------------------------------------------------ N1b: --synth-variants ALLOW-LIST
BAD_FLOWS = [("pre", "shell"), ("pre", "read_verilog /etc/passwd"), ("pre", "techmap -map /tmp/x.v"), ("post", "write_verilog /tmp/zz.v"), ("post", "write_json /tmp/zz"),
             ("abc", "abc -script +strash"), ("abc", "abc -exe /bin/sh"), ("abc", "abc -liberty x.lib"), ("abc", "abc -g AND,EVIL"), ("abc", "proc"),
             ("pre", "abc -fast"), ("pre", "opt -unknown"), ("pre", "synth -run begin:fine"), ("pre", "synth -top a;b"), ("pre", "setattr -mod -set keep 1 *"),
             ("pre", "exec -- touch /tmp/x"), ("pre", "proc; !ls"), ("pre", "tee -o /tmp/x stat"), ("pre", "plugin -i x"), ("pre", "script x.ys"),
             ("pre", "hierarchy -top x"), ("pre", "opt_clean \"x\""), ("pre", "proc #c"), ("post", "dump"), ("pre", "cd foo"), ("pre", "yosys-abc")]


@pytest.mark.parametrize("field,cmd", BAD_FLOWS)
def test_n1b_allowlist_refuses(tmp_path, field, cmd):
    p = tmp_path / "v.toml"
    p.write_text('[[variant]]\nname = "x"\n' + f"{field} = {json.dumps(cmd)}\n")
    with pytest.raises(ConfigError):
        synth_sweep.load_variants(str(p))


def test_n1b_allowlist_exit3_on_cli(tmp_path, capsys):
    p = tmp_path / "v.toml"
    p.write_text('[[variant]]\nname = "x"\npre = "exec -- touch /tmp/never"\n')
    (tmp_path / "m.v").write_text(VSRC)
    rc = cli.main(["analyze", str(tmp_path / "m.v"), "--top", "m", "--synth-sweep", "--synth-variants", str(p)])
    assert rc == 3 and "not allowed" in capsys.readouterr().err


def test_n1b_builtins_and_documented_examples_pass_the_allowlist():
    for v in synth_sweep.builtin_variants():
        for k in ("pre", "abc", "post"):
            synth_sweep._check_cmds(v["name"], k, v[k])
    vs = synth_sweep.load_variants(os.path.join(ROOT, "product", "examples", "synth_sweep", "variants.toml")) if os.path.isfile(
        os.path.join(ROOT, "product", "examples", "synth_sweep", "variants.toml")) else []
    assert all(v["name"] for v in vs)


def test_n1b_make_script_rechecks_variants_from_a_job_file():
    v = dict(name="evil", pre="proc; exec -- id", abc="abc", post="opt_clean", strip_keep=False)
    with pytest.raises(ConfigError):
        synth_sweep.make_script(v, "design.v", "m", "o.json")


# ------------------------------------------------------------------ N2 / N13: check_reproduce.py
CHECK = os.path.join(ROOT, "ci", "check_reproduce.py")


def _tree(tmp, glitch_src):
    t = os.path.join(str(tmp), "t")
    for d in ("ci", "results", "reference", "rtl"):
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(t, d), ignore=shutil.ignore_patterns("work", "mutants", "deep", "logs"))
    os.makedirs(os.path.join(t, "scripts"))
    with open(os.path.join(t, "scripts", "glitchsat.py"), "w") as f:
        f.write(glitch_src)
    return t


FAKE = '''import json, os
EXP = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ci", "expected_reproduce.json")))["expected"]
def run_check(path, design, k, N, out=None, flow="plain", workdir=None, **kw):
    for key, (verdict, mf) in EXP.items():
        if key.startswith(design + "|") and key.endswith("|k%d" % k) and (("rtl" in key) == path.endswith(".v")):
            if COND: return dict(verdict="NO_ATTACK_UP_TO_BOUND" if verdict == "ATTACK_FOUND" else "ATTACK_FOUND", min_faults=None if verdict == "ATTACK_FOUND" else 1)
            return dict(verdict=verdict, min_faults=mf)
    raise RuntimeError("no row")
'''


def _chk(t, *a):
    return subprocess.run([sys.executable, os.path.join(t, "ci", "check_reproduce.py"), *a], capture_output=True, text=True, timeout=300)


def _need_results():
    if not os.path.isfile(os.path.join(ROOT, "results", "reproduce_summary.json")):
        pytest.skip("run make reproduce first")


def test_n2_rerun_mismatch_is_not_counted_as_a_match(tmp_path):
    _need_results()
    t = _tree(tmp_path, FAKE.replace("COND", "design == 'v2' and k == 3 and 'spike' in path"))
    r = _chk(t, "--rerun")
    assert r.returncode == 1 and "RERUN MISMATCH" in r.stdout
    m = re.search(r"(\d+)/36 rows match", r.stdout)
    assert m and int(m.group(1)) < 36 and "36/36 rows match" not in r.stdout
    assert "NOT DETECTED" in r.stdout and "EXTERNAL copy" in r.stdout          # states what is and is not tamper-evident


def test_n2_tampered_engine_is_warned_about(tmp_path):
    _need_results()
    t = _tree(tmp_path, FAKE.replace("COND", "False"))   # a lookup-table 'engine' that returns the expected file: the T4 attack
    r = _chk(t, "--rerun")
    assert "ENGINE FILE DIFFERS FROM MANIFEST scripts/glitchsat.py" in r.stdout + r.stderr
    assert _chk(t, "--rerun", "--strict-engine").returncode == 1


def test_n13_rerun_engine_crash_is_exit4_not_traceback(tmp_path):
    _need_results()
    t = _tree(tmp_path, "def run_check(*a, **k):\n    raise RuntimeError('boom')\n")
    r = _chk(t, "--rerun")
    assert r.returncode == 4 and "RERUN ERROR" in r.stdout and "Traceback" not in r.stderr and "36/36" not in r.stdout


def test_n2_default_mode_still_passes_on_the_clean_tree(tmp_path):
    _need_results()
    t = _tree(tmp_path, open(os.path.join(ROOT, "scripts", "glitchsat.py")).read())
    r = _chk(t)
    assert r.returncode == 0 and "36/36 rows match" in r.stdout and "0 row(s) FAILED" in r.stdout


# ------------------------------------------------------------------ N3 / N11: sweeps and --report/--badge, CSV formula guard
def test_n3_scope_sweep_writes_the_report(tmp_path, capsys):
    out = tmp_path / "sw.json"
    rc = cli.main(["analyze", V2, "--config", TH, "--max-flips", "1", "--scope-sweep", "--report", str(out)])
    assert rc in (0, 1) and json.load(open(out))["schema"] == "faultbound-wt-sweep/1"
    csvp = tmp_path / "sw.csv"
    cli.main(["analyze", V2, "--config", TH, "--max-flips", "1", "--sweep-widths", "--report", str(csvp)])
    assert csvp.read_text().startswith("goal,input_sites,init,verdict,cost,runtime_s,count_rule")


def test_n3_sweep_with_badge_or_sarif_is_exit3(tmp_path, capsys):
    for extra in (["--badge", str(tmp_path / "b.json")], ["--report", str(tmp_path / "x.sarif")], ["--report", str(tmp_path / "x.junit.xml")]):
        rc = cli.main(["analyze", V2, "--config", TH, "--max-flips", "1", "--scope-sweep", *extra])
        assert rc == 3 and "not supported" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@needs_yosys
def test_n3_synth_sweep_honours_report(tmp_path):
    (tmp_path / "m.v").write_text(VSRC)
    out = tmp_path / "ss.json"
    rc = cli.main(["analyze", str(tmp_path / "m.v"), "--top", "m", "--config", _write_cfg(tmp_path), "--synth-sweep", "--synth-select", "plain", "--report", str(out)])
    assert rc in (0, 1) and json.load(open(out))["schema"] == "faultbound-wt-synthsweep/1"


def test_n11_csv_cells_are_formula_safe(tmp_path):
    sw = dict(schema="faultbound-wt-sweep/1", cells=[dict(goal="=cmd|'calc'!A0", input_sites="+x", init="-y", verdict="@z", cost="\t1", runtime_s=0.1, count_rule="stem")])
    p = tmp_path / "s.csv"
    reports.write_sweep(sw, str(p))
    row = p.read_text().splitlines()[1]
    assert row.startswith("\"'=cmd") and "\"'+x\"" in row and "\"'-y\"" in row and "\"'@z\"" in row and "\"'\t1\"" in row
    assert reports.csv_cell("plain") == '"plain"' and reports.csv_cell(">3") == '">3"'


# ------------------------------------------------------------------ N5: atomic report writes
def test_n5_concurrent_writers_never_leave_invalid_json(tmp_path):
    p = str(tmp_path / "race.json")
    small, big = {"s": 1}, {"s": "x" * 400000}
    stop = []
    bad = []

    def writer(doc):
        for _ in range(60):
            reports.atomic_write_text(p, json.dumps(doc) + "\n")

    def reader():
        while not stop:
            try:
                with open(p) as f:
                    txt = f.read()
            except FileNotFoundError:
                continue
            try:
                json.loads(txt)
            except ValueError:
                bad.append(len(txt))
    r = threading.Thread(target=reader)
    ts = [threading.Thread(target=writer, args=(d,)) for d in (small, big, small, big)]
    r.start()
    [t.start() for t in ts]
    [t.join() for t in ts]
    stop.append(1)
    r.join()
    assert not bad
    json.load(open(p))
    assert os.listdir(tmp_path) == ["race.json"]   # no temp file left behind


def test_n5_report_and_badge_writers_use_replace(tmp_path):
    rep = runner.analyze(V2, config.load(TH))
    reports.write(rep, str(tmp_path / "a.json"))
    reports.write_badge(rep, str(tmp_path / "b.json"))
    assert sorted(os.listdir(tmp_path)) == ["a.json", "b.json"]
    assert oct(os.stat(tmp_path / "a.json").st_mode & 0o777) in ("0o644", "0o664", "0o666", "0o640", "0o600", "0o660", "0o755") and os.stat(tmp_path / "a.json").st_mode & 0o400


# ------------------------------------------------------------------ N4: vacuous free_nongoal
def test_n4_free_nongoal_on_constant_output_is_exit3(tmp_path, capsys):
    nl = _nl({"clk": _P("input", [2]), "sig": _P("input", [3, 4]), "boot_word": _P("output", ["0", "1"])}, {})
    j = tmp_path / "b_const.json"
    j.write_text(json.dumps(nl))
    cfg = tmp_path / "t.toml"
    cfg.write_text('[attacker]\ninput="sig"\nlegitimate_value=1\n[property]\noutput="boot_word"\nbad_value=2\n[netlist]\ntop="t"\n')
    assert cli.main(["analyze", str(j), "--config", str(cfg)]) == 1                       # known init: 0 flips needed, ATTACK_FOUND
    capsys.readouterr()
    rc = cli.main(["analyze", str(j), "--config", str(cfg), "--init", "free_nongoal"])
    err = capsys.readouterr().err
    assert rc == 3 and "goal output is constant: nothing to attack" in err


def test_n4_free_nongoal_still_works_on_a_real_design():
    rep = runner.analyze(V2, _th(init="free_nongoal", max_flips=2))
    assert rep["verdict"] in ("ATTACK_FOUND", "NO_ATTACK_UP_TO_BOUND")


def _th(**kw):
    t = config.load(TH)
    for k, v in kw.items():
        setattr(t, k, v)
    config.validate(t)
    return t


# ------------------------------------------------------------------ N6 / N7 / N14: --consumer-bits syntax
@pytest.mark.parametrize("v,m", [("0xF0", 0xF0), ("0XF0", 0xF0), (" 0x0f ", 0xF), ("0b101", 5), ("15", 15), ("3", 3), (3, 3), (255, 255), ("bits:3,5", 0x28), ("bits:0-3,6", 0x4F),
                                 ("bits: 3, 5", 0x28), ("[3,5]", 0x28), ("[3, 5]", 0x28), ([3, 5], 0x28), ("0-3,6", 0x4F), ("3,5", 0x28), ("bits:7", 0x80)])
def test_n6_syntax(v, m):
    assert parse_mask(v) == m


@pytest.mark.parametrize("v", ["0", "0x0", 0, "", "bits:", "bits:3-", "bits:-3", "3-", "1-", "-1", "7-0", "0,,1", "0x", "abc", "1e3", "1_0", "0b102", "0o7", "[]", "[3",
                               "bits:0-100000000", "0-100000000", "0-99999999999999", "bits:5000", [5000], "9" * 2000, [-1], [True], True, 1.5, None, "0xZZ", "bits:3;5"])
def test_n6_n7_n14_rejected(v):
    t0 = time.time()
    with pytest.raises(ConfigError):
        parse_mask(v)
    assert time.time() - t0 < 1.0   # N7: fast, no range loop


def test_n6_cli_decimal_is_mask_in_cli_and_toml(tmp_path, capsys):
    # "3" = mask 3 = bits 0,1 in the CLI and in TOML, int or string
    cfgs = []
    for i, val in enumerate(('3', '"3"', '[0, 1]', '"bits:0,1"')):
        p = tmp_path / f"c{i}.toml"
        p.write_text(f"[property]\nconsumer_bits = {val}\n")
        cfgs.append(config.load(str(p)).consumer_bits)
    assert cfgs == [3, 3, 3, 3]
    rc = cli.main(["analyze", V2, "--config", TH, "--max-flips", "0", "--consumer-bits", "3"])
    out = capsys.readouterr().out
    assert "consumer_bits=0x3" in out


def test_n7_huge_range_via_cli_is_fast_exit3(capsys):
    t0 = time.time()
    rc = cli.main(["analyze", V2, "--config", TH, "--consumer-bits", "bits:0-100000000"])
    assert rc == 3 and time.time() - t0 < 5
    rc = cli.main(["analyze", V2, "--config", TH, "--consumer-bits", "0-99999999999999"])
    assert rc == 3
    rc = cli.main(["analyze", V2, "--config", TH, "--consumer-bits", "bits:100"])   # beyond the 8-bit output
    assert rc == 3 and "beyond" in capsys.readouterr().err


# ------------------------------------------------------------------ N8: --max-flips cost
def test_n8_max_flips_cap_is_a_clear_exit3(capsys):
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", str(config.MAX_FLIPS + 1)]) == 3
    assert "maximum" in capsys.readouterr().err
    assert cli.main(["analyze", V2, "--config", TH, "--max-flips", "3000"]) == 3


def test_n8_max_flips_at_cap_is_fast():
    t0 = time.time()
    rep = runner.analyze(V2, _th(max_flips=config.MAX_FLIPS))
    assert rep["verdict"] == "ATTACK_FOUND" and rep["min_faults"] == 3
    assert time.time() - t0 < 20


def test_n8_counter_is_capped_by_the_number_of_items():
    from faultbound_wt import _engine as eng
    nl = eng.Netlist(V2, "v2")
    kw = dict(goal_out="boot_word", goal_value=0x96, attack_in="sig", key=0xC3, reduce="full")
    a = eng.solve(nl, 6, 3, **kw)
    b = eng.solve(nl, 6, 60, **kw)
    assert a[0] == b[0] == "ATTACK_FOUND" and len(a[2]["faults"]) == len(b[2]["faults"]) == 3


# ------------------------------------------------------------------ N9 / N10: timeouts, process groups, temp dirs
def _fake_yosys(tmp_path, marker):
    d = tmp_path / "bin"
    d.mkdir()
    y = d / "yosys"
    y.write_text(f'#!/bin/bash\nif [ "$1" = "-V" ]; then echo "Yosys fake"; exit 0; fi\nsleep {marker} &\nsleep {marker}\n')
    y.chmod(0o755)
    return str(d)


def _procs(marker):
    out = []
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                cmd = open(f"/proc/{p}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if f"sleep {marker}" in cmd:
                out.append(int(p))
    return out


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="needs /proc")
def test_n9_timeout_kills_the_yosys_children_and_removes_temp_dirs(tmp_path, monkeypatch, capsys):
    marker = "4711"
    monkeypatch.setenv("PATH", _fake_yosys(tmp_path, marker) + os.pathsep + os.environ["PATH"])
    tdir = tmp_path / "tmp"
    tdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tdir))
    (tmp_path / "m.v").write_text(VSRC)
    t0 = time.time()
    rc = cli.main(["analyze", str(tmp_path / "m.v"), "--top", "m", "--config", _write_cfg(tmp_path), "--timeout-s", "3"])
    assert rc == 2 and time.time() - t0 < 15
    time.sleep(0.5)
    assert _procs(marker) == []
    assert os.listdir(tdir) == []


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="needs /proc")
def test_n9_killing_the_parent_does_not_leave_worker_or_yosys(tmp_path):
    marker = "4712"
    env = dict(os.environ, PATH=_fake_yosys(tmp_path, marker) + os.pathsep + os.environ["PATH"], PYTHONPATH=os.path.join(PROD, "src"), TMPDIR=str(tmp_path))
    (tmp_path / "m.v").write_text(VSRC)
    code = f"import sys; from faultbound_wt import cli; sys.exit(cli.main(['analyze', {str(tmp_path / 'm.v')!r}, '--top', 'm', '--config', {_write_cfg(tmp_path)!r}, '--timeout-s', '120']))"
    p = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        if _procs(marker):
            break
        time.sleep(0.1)
    assert _procs(marker), "fake yosys did not start"
    p.kill()
    p.wait()
    for _ in range(40):
        if not _procs(marker):
            break
        time.sleep(0.25)
    assert _procs(marker) == []


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="needs /proc")
def test_n9_sigterm_to_the_parent_cleans_up(tmp_path):
    marker = "4713"
    env = dict(os.environ, PATH=_fake_yosys(tmp_path, marker) + os.pathsep + os.environ["PATH"], PYTHONPATH=os.path.join(PROD, "src"), TMPDIR=str(tmp_path))
    (tmp_path / "m.v").write_text(VSRC)
    code = f"import sys; from faultbound_wt import cli; sys.exit(cli.main(['analyze', {str(tmp_path / 'm.v')!r}, '--top', 'm', '--config', {_write_cfg(tmp_path)!r}, '--timeout-s', '120']))"
    p = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        if _procs(marker):
            break
        time.sleep(0.1)
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=20)
    time.sleep(0.5)
    assert _procs(marker) == []
    assert [x for x in os.listdir(tmp_path) if x.startswith("fbwt_")] == []


@needs_yosys
def test_n10_verilog_error_leaves_no_temp_dir(tmp_path, monkeypatch, capsys):
    tdir = tmp_path / "tmp"
    tdir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tdir))
    (tmp_path / "m.v").write_text(VSRC)
    assert cli.main(["analyze", str(tmp_path / "m.v"), "--top", "m", "--config", _write_cfg(tmp_path), "--goal-out", "nonexist"]) == 3
    assert cli.main(["analyze", str(tmp_path / "m.v"), "--top", "m", "--config", _write_cfg(tmp_path), "--accept-value", "0x1FF"]) == 3
    (tmp_path / "bad.v").write_text("module m(; endmodule\n")
    assert cli.main(["analyze", str(tmp_path / "bad.v"), "--top", "m", "--config", _write_cfg(tmp_path)]) == 3
    assert cli.main(["analyze", str(tmp_path / "m.v"), "--top", "nosuch", "--config", _write_cfg(tmp_path)]) == 3
    assert os.listdir(tdir) == []
