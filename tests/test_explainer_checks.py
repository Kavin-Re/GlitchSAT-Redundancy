"""Runs the checkers of the explainer pages (docs/explainers/dev/check_*.py) via subprocess; each must exit 0.
Browser parts run only when /usr/bin/google-chrome and playwright exist. Total runtime is kept well under 60 s."""
import os, shutil, subprocess, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKS = os.path.join(ROOT, "docs", "explainers", "dev")
CHROME = os.path.exists("/usr/bin/google-chrome") or shutil.which("google-chrome")
try:
    import playwright  # noqa: F401
    HAVE_PW = True
except Exception:
    HAVE_PW = False
BROWSER = bool(CHROME and HAVE_PW)
try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except Exception:
    HAVE_Z3 = False
NEEDS_Z3 = pytest.mark.skipif(not HAVE_Z3, reason="z3-solver is not installed (check_theatre re-runs the solver)")


def run(script, *args, timeout=50):
    p = subprocess.run([sys.executable, os.path.join(CHECKS, script), *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-1000:]


@pytest.mark.parametrize("script", ["check_dial.py", "check_wall.py", pytest.param("check_theatre.py", marks=NEEDS_Z3), "check_hub.py", "check_game_answers.py"])
def test_explainer_data_checks(script):
    run(script)


@pytest.mark.skipif(not BROWSER, reason="google-chrome or playwright missing")
def test_hub_browser():
    run("check_hub.py", "--browser")
