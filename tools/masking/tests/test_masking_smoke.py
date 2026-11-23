"""Smoke test (Labs bar): the masking example runs end to end and writes a valid labs-result/1 file.
It also checks the known textbook answers, so a broken engine cannot pass silently."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), 'labs'))
import labs_result as LR  # noqa: E402

HAVE_OT = os.path.isdir(os.path.join(ROOT, 'work', 'ot', 'hw', 'ip', 'aes'))


def test_example_runs(tmp_path):
    out = tmp_path / 'r.json'
    cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'run_labs.py'), '--out', str(out)] + ([] if HAVE_OT else ['--quick'])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=540)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.load(open(out))
    assert LR.validate(d) == []
    assert d['status'] == 'EXPERIMENTAL' and all(f['experimental'] for f in d['findings'])
    rows = d['run']['rows']
    # known answers (textbook): naive leaks, ISW is secure only without glitches, DOM is secure in both models
    assert not rows['naive_and2/plain']['standard']['secure']
    assert rows['isw_and2/plain']['standard']['secure'] and not rows['isw_and2/plain']['glitch']['secure']
    assert rows['dom_indep_and2/plain']['standard']['secure'] and rows['dom_indep_and2/plain']['glitch']['secure']
    assert all(rows[k]['unmasked_output_ok'] for k in rows if 'unmasked_output_ok' in rows[k])
    if HAVE_OT:
        assert rows['ot_dom_and/plain']['glitch']['secure']
