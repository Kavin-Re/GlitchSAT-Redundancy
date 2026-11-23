"""Command line and the files it writes (evidence JSON, Studio panel JSON, Verilog, Yosys script)."""
import json, os, subprocess, sys
import pytest
from harden import cli

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_design_writes_evidence_and_panel(tmp_path, capsys):
    rc = cli.main(['design', 'v1', '--goal', '2', '--alternatives', '1', '--out', str(tmp_path)])
    assert rc == 0
    ev = json.load(open(tmp_path / 'v1_g2.evidence.json'))
    assert ev['schema'] == 'glitchsat-harden/1' and ev['reached']
    f = ev['fixes'][0]
    assert f['after']['label'] == 'MEASURED' and f['yosys']['label'] == 'UNTESTED-HERE'
    assert f['cost']['gates_added'] is not None and f['cost']['flops_added'] == 0
    panel = json.load(open(tmp_path / 'v1_g2.suggest_fix.json'))
    assert panel['schema'] == 'glitchsat-studio-suggest-fix/1' and panel['cards'][0]['suggestions']
    for k in ('verilog', 'yosys_script', 'spec', 'netlist_select-shared'):
        assert os.path.isfile(os.path.join(os.path.dirname(str(tmp_path)), f['files'][k])), k
    out = capsys.readouterr().out
    assert '| v1 | >= 2 |' in out


def test_check_command(repo, capsys):
    rc = cli.main(['check', repo('research/c2/e2_variance/baseline_netlists/apt0.33_v2.json'), '--top', 'v2', '--kmax', '3', '--cycles', '6'])
    assert rc == 0
    assert 'minimum flips: 2' in capsys.readouterr().out


def test_wrapper_script_runs():
    p = subprocess.run([os.path.join(TOP, 'glitchsat'), 'harden', '--version'], capture_output=True, text=True)
    assert p.returncode == 0 and p.stdout.strip()


def test_text_has_no_forbidden_wording():
    """Plain technical wording only in the shipped text."""
    # Kept hex-encoded so that this file does not itself contain the words it rejects.
    bad = tuple(bytes.fromhex(h).decode() for h in (
        '756e69766572736974', '20616920', '6167656e74', '6c6c6d', '63686174677074', '636c61756465', '72616b736861'))
    for d, _, fs in os.walk(TOP):
        if any(x in d for x in ('__pycache__', '.pytest_cache', '.venv', 'cloud_out', os.sep + 'work')):
            continue
        for fn in fs:
            if fn.endswith(('.py', '.md', '.sh', '.v', '.ys', '.json')):
                t = open(os.path.join(d, fn), errors='replace').read().lower()
                for w in bad:
                    assert w not in t, (fn, w)
