"""Checks added with the multi-angle audit (AUDIT_FIXES.md): generated names never clash with design names,
the gallery is never changed by a test run, and the first run after `init --yes` explains the missing condition."""
import hashlib
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import EXAMPLES, PKG, needs_yosys
from glitchsat_byod.run import run_project

GS = os.path.join(PKG, 'glitchsat')

# A tiny lock whose ports carry the names that generated wrapper and monitor code used to declare itself.
COMMON_NAMES_V = '''
module t (input wire clk, input wire rst, input wire [3:0] code, input wire try_i, output reg ok, output wire bad, output wire dut);
  reg [1:0] tries;
  always @(posedge clk) begin
    if (rst) begin ok <= 1'b0; tries <= 2'd0; end
    else if (try_i) begin ok <= (code == 4'hA); tries <= tries + 2'd1; end
  end
  assign bad = (tries == 2'd3);
  assign dut = ok & ~bad;
endmodule
'''


@needs_yosys
@pytest.mark.parametrize('port', ['ok', 'bad', 'dut'])
def test_common_port_names_do_not_clash(project, port):
    """Audit 2-B1: a design with a port named `ok` (or `bad`, `dut`) is analysed like any other design."""
    p = project('''
        glitchsat: 1
        design: {sources: [t.v], top: t}
        clock: clk
        reset: {port: rst, active: high}
        checks:
          - id: c
            bad: "%s"
            must_hold: ["!(try_i && code == 4'hA)"]
        faults: {max_faults: 1, horizon: 4}
        analyses: [validate, min_faults]
        ''' % port, files={'t.v': COMMON_NAMES_V})
    rep, _ = run_project(p)
    c = rep['checks'][0]
    assert c['analyses']['min_faults']['verdict'] in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND', 'FAILS_WITHOUT_FAULTS')
    for fl, x in c['flows'].items():
        assert x['validation']['mismatch'] is None, (fl, x['validation'])


def test_generated_names_are_prefixed():
    from glitchsat_byod import monitor as MON
    M = MON.Monitor({'ok': 1, 'clk': 1, 'bad': 1}, {}, 'clk')
    e = M.rewrite('ok && !$past(bad)', {})
    v = M.verilog([e], [], 1)
    decl = [ln for ln in v.splitlines() if ln.strip().startswith(('output', 'reg', 'wire'))]
    assert decl and all(MON.PFX in ln for ln in decl), decl
    w = MON.wrapper_verilog('t', {'clk': ('input', 1), 'ok': ('output', 1)}, {'clk': 'clock'}, {}, None, {}, ['ok'], {})
    assert ' ok ' not in w.replace('.ok(', '') and MON.OUT + 'ok' in w and MON.DUT in w and MON.MON in w


def _tree_hash(root):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(root)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            h.update(os.path.relpath(p, root).encode())
            h.update(str(os.path.getsize(p)).encode())
            h.update(str(int(os.path.getmtime(p))).encode())
    return h.hexdigest()


@needs_yosys
def test_running_an_example_leaves_the_gallery_unchanged(example):
    """Audit 8-S4: tests run examples from a temp copy, never in place."""
    before = _tree_hash(EXAMPLES)
    run_project(os.path.join(example('hello_lock'), 'glitchsat.yaml'), only=['min_faults'], quick=True)
    assert _tree_hash(EXAMPLES) == before


@needs_yosys
def test_init_yes_then_run_names_the_missing_condition(tmp_path):
    """Audit 2-S1: `init --yes` writes no must-hold condition, so the first run finds the attack without any glitch.
    The run must then say that a must-hold condition is missing and show the line to add, not talk about placement."""
    (tmp_path / 'pin.v').write_text(textwrap.dedent('''
        module pin (input wire clk, input wire rst_n, input wire [3:0] pin_i, input wire try_i, output reg open_o);
          always @(posedge clk or negedge rst_n)
            if (!rst_n) open_o <= 1'b0; else if (try_i) open_o <= (pin_i == 4'h5);
        endmodule
        '''))
    r = subprocess.run([sys.executable, GS, 'init', '--yes'], cwd=tmp_path, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run([sys.executable, GS, 'run'], cwd=tmp_path, capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    assert 'WITHOUT any fault' in out, out
    assert 'must_hold' in out and 'missing' in out.lower(), out


def test_sources_outside_the_project_are_refused(tmp_path, monkeypatch):
    """Audit 4-S3: a project file cannot make the tool read files outside its folder, unless allowed."""
    from glitchsat_byod import project as PRJ
    from glitchsat_byod.errors import GSError
    (tmp_path / 'outside.v').write_text('module t(input wire clk, output wire o); assign o = 1\'b0; endmodule\n')
    proj = tmp_path / 'proj'
    proj.mkdir()
    (proj / 'glitchsat.yaml').write_text(textwrap.dedent('''
        glitchsat: 1
        design: {sources: [../outside.v], top: t}
        clock: clk
        reset: none
        checks: [{id: c, bad: "o"}]
        faults: {max_faults: 1, horizon: 2}
        '''))
    monkeypatch.delenv('GLITCHSAT_ALLOW_OUTSIDE', raising=False)
    with pytest.raises(GSError) as e:
        PRJ.load(str(proj / 'glitchsat.yaml'))
    assert e.value.code == 'GS003' and 'outside the project folder' in e.value.msg
    monkeypatch.setenv('GLITCHSAT_ALLOW_OUTSIDE', '1')
    spec, _ = PRJ.load(str(proj / 'glitchsat.yaml'))
    assert spec['sources']


@needs_yosys
def test_redact_says_what_it_does_not_cover(example):
    """Audit 4-S2: --redact prints that the work folder and the lock file keep the real names."""
    d = example('hello_lock')
    r = subprocess.run([sys.executable, GS, 'run', 'glitchsat.yaml', '--redact', '--quick', '--json-only'], cwd=d,
                       capture_output=True, text=True, timeout=300)
    assert 'NOTE: --redact covers' in r.stderr and 'never a zip of the project folder' in r.stderr, r.stderr[-400:]


@needs_yosys
def test_plain_words_findings_in_text_json_and_sarif(example, tmp_path):
    """Plain-words findings lead the text report (summary line first), are stored in report.json, and go to SARIF with
    the how-we-found-it steps as a code flow. A one-glitch lock bypass is Critical."""
    import json
    from glitchsat_byod.report import plain_findings_module
    if plain_findings_module() is None:
        pytest.skip('findings module not found next to this folder')
    d = example('hello_lock')
    sar = str(tmp_path / 'r.sarif')
    r = subprocess.run([sys.executable, GS, 'run', 'glitchsat.yaml', '--quick', '--sarif', sar], cwd=d, capture_output=True, text=True, timeout=300)
    lines = r.stdout.splitlines()
    assert lines[2] == 'What we found and what it means' and lines[4].startswith('1 critical'), lines[:6]
    assert '[!!! CRITICAL]' in r.stdout and 'How we found it' in r.stdout and 'Technical details' in r.stdout
    rep = json.load(open(os.path.join(d, '.glitchsat', 'default', 'report.json')))
    f = rep['plain_findings'][0]
    assert f['severity']['level'] == 'Critical' and len(f['how']['steps']) == 6 and f['where']['file'] and f['how']['replay']['replayed']
    s = json.load(open(sar))
    res = s['runs'][0]['results'][0]
    assert s['version'] == '2.1.0' and res['level'] == 'error' and len(res['codeFlows'][0]['threadFlows'][0]['locations']) == 6
