"""Smoke test (Labs bar): the OpenTitan primitives example (3 primitives) builds with Yosys 0.71 read_slang + 0.33, runs
the minimum-flip search and the survival check, and writes a valid labs-result/1 file. Builds go to labs/work/."""
import json
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.environ.get('GLITCHSAT_EXT') or os.path.dirname(os.path.dirname(HERE))   # tools/ (tools/real/opentitan_prims)
sys.path.insert(0, os.path.join(EXT, 'labs'))
import labs_result as LR  # noqa: E402


def _slang_yosys():
    """The Yosys that scripts/build.py elaborates with (same lookup order), if it has the read_slang command; else
    (None, reason). Yosys 0.33 from Ubuntu apt has no read_slang, so on such a machine this suite skips."""
    y = os.environ.get('Y71') or os.environ.get('GLITCHSAT_YOSYS_SLANG') or shutil.which('yosys')
    if not y:
        return None, 'Yosys was not found'
    try:
        r = subprocess.run([y, '-Q', '-T', '-p', 'help read_slang'], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return None, 'could not run %s (%s)' % (y, e)
    out = r.stdout + r.stderr
    if r.returncode != 0 or 'No such command' in out or 'read_slang [options]' not in out:
        return None, ('%s has no read_slang command (needs a Yosys with the yosys-slang plugin built in, 0.67 or '
                      'newer; point Y71 or GLITCHSAT_YOSYS_SLANG at it)' % y)
    return y, ''


def _z3():
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False


_Y71, _WHY = _slang_yosys()
pytestmark = [pytest.mark.skipif(_Y71 is None, reason='OpenTitan primitives: ' + _WHY),
              pytest.mark.skipif(shutil.which('yosys') is None and not os.environ.get('Y33'), reason='Yosys 0.33 was not found'),
              pytest.mark.skipif(not _z3(), reason='z3 (z3-solver) is not installed')]


def test_example_runs(tmp_path):
    out = tmp_path / 'r.json'
    env = dict(os.environ)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'labs', 'run_labs.py'), '--out', str(out)],
                       capture_output=True, text=True, timeout=560, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.load(open(out))
    assert LR.validate(d) == []
    rows = d['run']['rows']
    assert set(rows) == {'mubi_flag', 'mubi_word', 'count_regs'}
    for i, row in rows.items():
        assert row['build']['gates'] > 0 and row['scale']['status'], i
    # the bounded minimum must match the run recorded in work/ (reproducible)
    for i, row in rows.items():
        if row.get('recorded'):
            assert (row['scale']['lo'], row['scale']['hi']) == (row['recorded']['lo'], row['recorded']['hi']), i
