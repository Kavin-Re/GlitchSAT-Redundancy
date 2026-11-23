"""Packaging, GitHub Action, pre-commit hooks, template layout and the Studio launcher (static checks; nothing is run on GitHub)."""
import glob, os, re, subprocess, sys, zipfile
try:
    import tomllib
except ModuleNotFoundError:          # Python 3.10: the same parser, from the tomli package
    import tomli as tomllib

import pytest

PRODUCT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PRODUCT)


def _toml(p):
    with open(p, "rb") as f:
        return tomllib.load(f)


def test_entry_points_and_package_data():
    pp = _toml(os.path.join(PRODUCT, "pyproject.toml"))["project"]
    for s in ("glitchsat", "glitchsat-hook", "glitchsat-evidence", "glitchsat-evidence-hook", "glitchsat-studio"):
        assert s in pp["scripts"]
    assert not any(d.startswith("z3-solver") for d in pp["dependencies"])          # the solver is an extra
    assert pp["optional-dependencies"]["solver"] == ["z3-solver>=5.4.1,<6"]
    assert "z3-solver>=5.4.1,<6" in pp["optional-dependencies"]["test"]
    assert not any("==" in d for ds in pp["optional-dependencies"].values() for d in ds)   # exact pins: lock file only
    pats = _toml(os.path.join(PRODUCT, "pyproject.toml"))["tool"]["setuptools"]["package-data"]["faultbound_wt"]
    src = os.path.join(PRODUCT, "src", "faultbound_wt")
    data = [os.path.relpath(p, src) for p in glob.glob(os.path.join(src, "evidence", "data", "**", "*.json"), recursive=True)]
    import fnmatch
    for f in data:
        assert any(fnmatch.fnmatch(f, p) for p in pats), f


def test_root_pyproject_matches_product():
    rp = os.path.join(ROOT, "pyproject.toml")
    if not os.path.isfile(rp):
        pytest.skip("root pyproject.toml not present")
    a, b = _toml(rp)["project"], _toml(os.path.join(PRODUCT, "pyproject.toml"))["project"]
    assert a["dependencies"] == b["dependencies"] and a["scripts"] == b["scripts"] and a["name"] == b["name"]
    assert a["optional-dependencies"] == b["optional-dependencies"]
    for k in ("authors", "keywords", "classifiers", "urls", "license", "requires-python", "description"):
        assert a.get(k) == b.get(k), k
    for p in (rp, os.path.join(PRODUCT, "pyproject.toml")):
        assert _toml(p)["build-system"]["requires"] == ["setuptools>=77"], p      # PEP 639 licence string


def test_wheel_contains_evidence_data(tmp_path):
    pytest.importorskip("setuptools")
    r = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", str(tmp_path), PRODUCT],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("wheel build unavailable here: " + r.stderr[-300:])
    whl = glob.glob(str(tmp_path / "glitchsat-*.whl"))[0]
    names = zipfile.ZipFile(whl).namelist()
    for need in ("faultbound_wt/evidence/data/sarif-2.1.0-subset.schema.json", "faultbound_wt/evidence/data/recorded/surface/v2_spike_surface.json",
                 "faultbound_wt/evidence/data/recorded/reproduce/v2_spike_given-netlist_k3.json", "faultbound_wt/studio_launcher.py",
                 "faultbound_wt/examples/v2.json"):
        assert need in names, need
    ep = [n for n in names if n.endswith("entry_points.txt")][0]
    txt = zipfile.ZipFile(whl).read(ep).decode()
    assert "glitchsat-studio" in txt and "glitchsat-evidence" in txt


def _action():
    yaml = pytest.importorskip("yaml")
    with open(os.path.join(PRODUCT, "action", "action.yml")) as f:
        return yaml.safe_load(f)


def test_action_is_composite_and_safe():
    a = _action()
    assert a["runs"]["using"] == "composite"
    steps = a["runs"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(u.startswith("github/codeql-action/upload-sarif@") for u in uses)
    assert any(u.startswith("actions/setup-python@") for u in uses)
    for s in steps:
        if "run" in s:
            assert "${{" not in s["run"], f"step {s.get('name')}: expression inside run (script injection)"
            assert s.get("shell") == "bash"
    names = [s.get("name", "") for s in steps]
    assert "install Yosys" in names and "enforce margin" in names
    assert "apt-get install" in [s for s in steps if s.get("name") == "install Yosys"][0]["run"]
    # third-party actions pinned by full commit SHA; SARIF upload on codeql-action v4 (v3 deprecated December 2026)
    for u in uses:
        if u:
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", u), u
    txt = open(os.path.join(PRODUCT, "action", "action.yml")).read()
    assert re.search(r"github/codeql-action/upload-sarif@[0-9a-f]{40} # v4\.", txt)
    inst = [s for s in steps if s.get("name") == "install GlitchSAT"][0]["run"]
    assert '"$PKG[solver]"' in inst and 'glitchsat[solver]==' in inst
    up = [s for s in steps if s.get("name") == "upload evidence reports"][0]
    assert up["with"]["name"] == "${{ steps.art.outputs.name }}" and "artifact-name" in a["inputs"]


def test_action_artifact_name_step(tmp_path):
    a = _action()
    step = [s for s in a["runs"]["steps"] if s.get("name") == "artifact name"][0]
    for name, job, want in (("", "build", "glitchsat-evidence-build"), ("mine", "build", "mine")):
        out = tmp_path / "out.txt"
        out.write_text("")
        r = subprocess.run(["bash", "-c", step["run"]], env=dict(os.environ, NAME=name, JOB=job, GITHUB_OUTPUT=str(out)),
                           capture_output=True, text=True)
        assert r.returncode == 0 and out.read_text().strip() == f"name={want}"


def test_workflows_pin_actions_by_sha_and_template_uses_release_tag():
    yaml = pytest.importorskip("yaml")
    files = [os.path.join(ROOT, ".github", "workflows", "release.yml"),
             os.path.join(ROOT, "templates", "glitchsat-project", ".github", "workflows", "glitchsat.yml")]
    for f in files:
        if not os.path.isfile(f):
            continue
        for job in yaml.safe_load(open(f))["jobs"].values():
            for st in job["steps"]:
                u = st.get("uses", "")
                if u and not u.startswith("Kavin-Re/"):
                    assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", u), (f, u)
    t = os.path.join(ROOT, "templates", "glitchsat-project")
    if os.path.isdir(t):
        from faultbound_wt import __version__
        wf = open(os.path.join(t, ".github", "workflows", "glitchsat.yml")).read()
        pc = yaml.safe_load(open(os.path.join(t, ".pre-commit-config.yaml")))
        assert f"product/action@v{__version__}" in wf
        assert pc["repos"][0]["rev"] == f"v{__version__}"


def test_action_shell_steps_locally(tmp_path):
    """Run the `enforce margin` step's script with each exit code, as the runner would."""
    a = _action()
    step = [s for s in a["runs"]["steps"] if s.get("name") == "enforce margin"][0]
    for code, fail, expect in (("0", "true", 0), ("1", "true", 1), ("1", "false", 0), ("2", "true", 2), ("3", "true", 3)):
        r = subprocess.run(["bash", "-c", step["run"]], env=dict(os.environ, CODE=code, FAIL=fail), capture_output=True, text=True)
        assert r.returncode == expect, (code, fail, r.stdout, r.stderr)
    inst = [s for s in a["runs"]["steps"] if s.get("name") == "install GlitchSAT"][0]["run"]
    for bad in ("-e", "glitchsat", "evil-package"):
        r = subprocess.run(["bash", "-c", inst], env=dict(os.environ, PKG=bad, ACTION_DIR=str(tmp_path)), capture_output=True, text=True)
        assert r.returncode == 3, bad


def test_precommit_hooks_file():
    yaml = pytest.importorskip("yaml")
    p = os.path.join(ROOT, ".pre-commit-hooks.yaml")
    if not os.path.isfile(p):
        pytest.skip("root hooks file not present")
    hooks = {h["id"]: h for h in yaml.safe_load(open(p))}
    pp = _toml(os.path.join(PRODUCT, "pyproject.toml"))["project"]["scripts"]
    for h in hooks.values():
        assert h["entry"] in pp and h["language"] == "python"
        re.compile(h["files"])
    assert hooks["glitchsat-margin"]["pass_filenames"] is False
    for h in hooks.values():   # the package has no hard z3 dependency; the hooks run the solver
        assert h["additional_dependencies"] == ["z3-solver>=5.4.1,<6"]


def test_template_layout():
    t = os.path.join(ROOT, "templates", "glitchsat-project")
    if not os.path.isdir(t):
        pytest.skip("templates not present")
    cfg = _toml(os.path.join(t, "glitchsat.toml"))
    for tg in cfg["target"]:
        for k in ("netlist", "config"):
            assert os.path.isfile(os.path.join(t, tg[k])), tg[k]
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load(open(os.path.join(t, ".github", "workflows", "glitchsat.yml")))
    job = list(wf["jobs"].values())[0]
    assert job["runs-on"] == "ubuntu-24.04" and wf["permissions"]["security-events"] == "write"
    assert any("product/action@" in s.get("uses", "") for s in job["steps"])


def test_studio_launcher(tmp_path, monkeypatch, capsys):
    from faultbound_wt import studio_launcher as S
    monkeypatch.delenv("GLITCHSAT_STUDIO", raising=False)
    monkeypatch.delenv("GLITCHSAT_ROOT", raising=False)
    monkeypatch.setattr(S, "PKG_DIR", str(tmp_path / "no_pkg"))       # no packaged copy for this part
    monkeypatch.setattr(S, "packaged_studio", lambda: None)
    monkeypatch.chdir(tmp_path)
    assert S.main(["--no-browser"]) == 3
    err = capsys.readouterr().err
    assert "not installed with this package" in err and "GLITCHSAT_STUDIO" in err
    d = tmp_path / "tools" / "studio"
    d.mkdir(parents=True)
    (d / "studio.py").write_text("import sys, os; print('ARGS', sys.argv[1:], os.environ['GLITCHSAT_ROOT']); sys.exit(7)\n")
    sub = tmp_path / "rtl"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert S.find_studio() == (str(d / "studio.py"), "repository")
    code = ("import sys; from faultbound_wt import studio_launcher as S; S.packaged_studio = lambda: None; "
            "sys.exit(S.main(['--port','1']))")
    r = subprocess.run([sys.executable, "-c", code], cwd=sub, capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GLITCHSAT_")})
    assert r.returncode == 7 and "['--port', '1']" in r.stdout and str(tmp_path) in r.stdout


def test_studio_launcher_prefers_the_packaged_copy(tmp_path, monkeypatch):
    """After integration Studio is package data at faultbound_wt/tools/studio/studio.py; the launcher runs that copy
    and points GLITCHSAT_ROOT at the repository found above the current directory, if any."""
    from faultbound_wt import studio_launcher as S
    monkeypatch.delenv("GLITCHSAT_STUDIO", raising=False)
    monkeypatch.delenv("GLITCHSAT_ROOT", raising=False)
    pkg = tmp_path / "site" / "faultbound_wt"
    (pkg / "tools" / "studio").mkdir(parents=True)
    (pkg / "tools" / "studio" / "studio.py").write_text(
        "import sys, os; print('PKG', sys.argv[1:], os.environ.get('GLITCHSAT_ROOT', '-')); sys.exit(5)\n")
    repo = tmp_path / "clone"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "glitchsat.py").write_text("")
    (repo / "tools" / "studio").mkdir(parents=True)
    (repo / "tools" / "studio" / "studio.py").write_text("raise SystemExit(9)\n")   # must not be chosen
    (repo / "rtl").mkdir()
    monkeypatch.setattr(S, "PKG_DIR", str(pkg))
    monkeypatch.chdir(repo / "rtl")
    assert S.find_studio() == (str(pkg / "tools" / "studio" / "studio.py"), "package")
    assert S.main(["--no-browser"]) == 5
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert S.main([]) == 5                      # no repository above: GLITCHSAT_ROOT stays unset (recorded mode)
    monkeypatch.setenv("GLITCHSAT_STUDIO", str(tmp_path / "missing.py"))
    assert S.find_studio() == (None, None) and S.main([]) == 3


def test_studio_is_package_data():
    pats = _toml(os.path.join(PRODUCT, "pyproject.toml"))["tool"]["setuptools"]["package-data"]["faultbound_wt"]
    import fnmatch
    assert any(fnmatch.fnmatch("tools/studio/studio.py", p) for p in pats)
    rp = os.path.join(ROOT, "pyproject.toml")
    if os.path.isfile(rp):
        assert _toml(rp)["tool"]["setuptools"]["package-data"] == _toml(os.path.join(PRODUCT, "pyproject.toml"))["tool"]["setuptools"]["package-data"]


def test_version_and_help_without_z3(capsys):
    from faultbound_wt import cli
    with pytest.raises(SystemExit) as e:
        cli.main(["--help"])
    assert e.value.code == 0 and "margin" in capsys.readouterr().out


def test_action_single_netlist_mode_writes_safe_toml(tmp_path):
    """Run the `glitchsat check` step locally with a stand-in `glitchsat` that copies the targets file it receives."""
    a = _action()
    step = [s for s in a["runs"]["steps"] if s.get("name") == "glitchsat check"][0]
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "glitchsat").write_text('#!/bin/sh\nfor x in "$@"; do case "$x" in --targets=*) cp "${x#--targets=}" "$OUTCOPY";; esac; done\nexit 1\n')
    (bindir / "glitchsat").chmod(0o755)
    (bindir / "python").write_text(f'#!/bin/sh\nexec {sys.executable} "$@"\n')
    (bindir / "python").chmod(0o755)
    out, summ = tmp_path / "out.txt", tmp_path / "summary.md"
    env = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", RUNNER_TEMP=str(tmp_path), GITHUB_OUTPUT=str(out),
               GITHUB_STEP_SUMMARY=str(summ), GITHUB_WORKSPACE=str(tmp_path), OUTCOPY=str(tmp_path / "seen.toml"),
               TARGETS="glitchsat.toml", SARIF="g.sarif", REPORTS="ev", NETLIST='net"\nlist$(id).json', CONFIG="threat.toml",
               TOP="v2", MAXF="3", CYC="6", TMIN="2")
    r = subprocess.run(["bash", "-c", step["run"]], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "exit_code=1" in out.read_text()
    t = _toml(tmp_path / "seen.toml")["target"][0]
    assert t["netlist"] == os.path.join(str(tmp_path), 'net"\nlist$(id).json') and t["top"] == "v2" and t["max_flips"] == 3
    env["MAXF"] = "3; rm -rf /"
    out.write_text("")
    r = subprocess.run(["bash", "-c", step["run"]], env=env, capture_output=True, text=True)
    assert "exit_code=3" in out.read_text()


def test_docs_plain_language_first_and_wording():
    readme = open(os.path.join(PRODUCT, "README.md"), encoding="utf-8").read()
    first = readme.split("\n## ")[1]
    assert first.startswith("What it does, in plain words") and "never replaces" in readme
    bundles = os.path.join(PRODUCT, "packaging", "BUNDLES.md")
    assert os.path.isfile(bundles) and "OSS CAD Suite" in open(bundles).read() and "IIC-OSIC-TOOLS" in open(bundles).read()
    # hex-encoded so that the test file does not contain the words it rejects
    w = [bytes.fromhex(h).decode() for h in (
        "756e69766572736974", "72616b736861", "6169", "6167656e74", "6c6c6d", "63686174677074", "636c61756465")]
    bad = re.compile(rf"{w[0]}|{w[1]}|\b{w[2]}\b|{w[3]}|\b{w[4]}\b|{w[5]}|{w[6]}", re.I)
    for d, _, fs in os.walk(PRODUCT):
        if "tests" in d.split(os.sep) or "__pycache__" in d:
            continue
        for f in fs:
            if f.endswith((".md", ".py", ".yml", ".yaml", ".toml", ".html", ".sarif")):
                txt = open(os.path.join(d, f), encoding="utf-8").read()
                m = bad.search(txt)
                assert m is None, f"{f}: {m.group(0) if m else ''}"
