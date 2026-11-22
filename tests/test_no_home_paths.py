"""Recorded files (logs, netlists, CSV/JSON results, notes, scripts) must not hold an absolute home-folder path of the machine
that produced them. Recorded paths are repo-relative (rtl/v2.v, results/deep/json/...) or use the placeholders <repo> and <home>.
/home/you is the placeholder used in examples and is allowed."""
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# '/home/' followed by a folder name; not preceded by a letter or digit (so a URL such as .../ja_JP/home/tools/... is not a path)
HOME_PATH = re.compile(rb'(?<![A-Za-z0-9_])/home/(?!you\b)[A-Za-z0-9_.-]+')
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', 'work', 'node_modules', '.venv', 'venv'}


def tracked_files():
    try:
        out = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'], capture_output=True, check=True).stdout
        files = [f for f in out.decode('utf-8', 'surrogateescape').split('\0') if f]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    found = []   # no git (unpacked bundle): walk the tree
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found += [os.path.relpath(os.path.join(base, n), ROOT) for n in names]
    return found


def test_no_absolute_home_paths_in_recorded_files():
    bad = []
    for rel in tracked_files():
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        with open(p, 'rb') as fh:
            data = fh.read()
        if b'\0' in data[:8192]:          # binary file (image, PDF, slide deck)
            continue
        for n, line in enumerate(data.splitlines(), 1):
            if HOME_PATH.search(line):
                bad.append(f'{rel}:{n}')
    assert not bad, f'{len(bad)} line(s) with an absolute home path, e.g. {bad[:10]}'


def test_pattern_finds_and_allows():
    assert HOME_PATH.search(b'"src": "/home/' + b'alex/project/rtl/v2.v:3.1"')
    assert HOME_PATH.search(b'FAILED ../../home/' + b'alex/x.py')
    assert not HOME_PATH.search(b'cd /home/you/GlitchSAT-Redundancy')
    assert not HOME_PATH.search(b'https://example.com/ja_JP/home/tools/page.html')
    assert not HOME_PATH.search(b'"src": "rtl/v2.v:3.1"')
