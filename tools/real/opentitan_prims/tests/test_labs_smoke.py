"""Smoke test (Labs bar): the OpenTitan primitives example (3 primitives) builds with Yosys 0.71 read_slang + 0.33, runs
the minimum-flip search and the survival check, and writes a valid labs-result/1 file. Builds go to labs/work/."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.environ.get('GLITCHSAT_EXT') or os.path.dirname(os.path.dirname(HERE))   # tools/ (tools/real/opentitan_prims)
sys.path.insert(0, os.path.join(EXT, 'labs'))
import labs_result as LR  # noqa: E402


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
