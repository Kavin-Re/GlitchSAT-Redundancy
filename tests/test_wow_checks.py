"""Runs the docs/wow checkers via subprocess; each must exit 0.
Browser parts run only when /usr/bin/google-chrome and playwright exist. Total runtime is kept well under 60 s."""
import os, shutil, subprocess, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WOW = os.path.join(ROOT, "docs", "wow")
CHROME = os.path.exists("/usr/bin/google-chrome") or shutil.which("google-chrome")
try:
    import playwright  # noqa: F401
    HAVE_PW = True
except Exception:
    HAVE_PW = False
BROWSER = bool(CHROME and HAVE_PW)


def run(script, *args, timeout=50):
    p = subprocess.run([sys.executable, os.path.join(WOW, script), *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-1000:]


@pytest.mark.parametrize("script", ["check_dial.py", "check_wall.py", "check_theatre.py", "check_hub.py", "check_game_answers.py"])
def test_wow_data_checks(script):
    run(script)


@pytest.mark.skipif(not BROWSER, reason="google-chrome or playwright missing")
def test_hub_browser():
    run("check_hub.py", "--browser")
