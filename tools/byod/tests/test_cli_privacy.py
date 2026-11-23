"""CLI (init, check, templates, explain, examples, importers), redaction, no network, unbounded adapter, the
importer on a real third-party netlist, and the Studio module's HTTP surface."""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from conftest import PKG, EXAMPLES, needs_yosys, have_lib, DESIGNS, copy_example
from glitchsat_byod import cli
from glitchsat_byod.errors import GSError
from glitchsat_byod.run import run_project

GS = [sys.executable, os.path.join(PKG, 'glitchsat')]


def sh(args, cwd=None):
    r = subprocess.run(GS + args, capture_output=True, text=True, cwd=cwd, timeout=600)
    return r.returncode, r.stdout, r.stderr


@needs_yosys
def test_init_yes_writes_valid_project(tmp_path):
    shutil.copy(os.path.join(EXAMPLES, 'hello_lock', 'rtl', 'hello_lock.v'), tmp_path / 'hello_lock.v')
    code, out, err = sh(['init', '--yes', '--template', 'custom'], cwd=tmp_path)
    assert code == 0, err
    txt = (tmp_path / 'glitchsat.yaml').read_text()
    assert 'clock: clk' in txt and 'rst_n' in txt and 'drives the clock of 1/1' in txt
    code, out, err = sh(['check'], cwd=tmp_path)
    assert code == 0 and 'valid' in out


def test_templates_and_explain():
    code, out, _ = sh(['templates'])
    assert code == 0 and 'secure_boot_wrong_key' in out and 'alarm_suppressed' in out
    for t in ('secure_boot_wrong_key', 'debug_unlock_locked', 'fsm_forbidden_state', 'key_to_output', 'counter_skip', 'alarm_suppressed'):
        code, out, _ = sh(['templates', t])
        assert code == 0 and 'In plain words' in out
    code, out, _ = sh(['explain', 'GS023'])
    assert code == 0 and 'black box' in out


def test_template_snippets_are_valid():
    import yaml
    from glitchsat_byod import project as PRJ, templates as TPL
    for t in TPL.NAMES:
        snip = yaml.safe_load(open(os.path.join(PKG, 'templates', t + '.yaml')))
        doc = dict(glitchsat=1, design=dict(sources=['x.v']), checks=snip['checks'])
        PRJ.check_schema(doc)
        c = snip['checks'][0]
        if c.get('template') and c['template'] != 'custom':
            ex = TPL.expand(c['template'], c['params'])
            assert ex['bad'] and ex['explain']


def test_examples_list_and_copy(tmp_path):
    code, out, _ = sh(['examples', 'list'])
    assert code == 0 and 'hello_lock' in out
    code, out, _ = sh(['examples', 'copy', 'hello_lock', str(tmp_path / 'hl')])
    assert code == 0 and (tmp_path / 'hl' / 'glitchsat.yaml').is_file()
    assert not (tmp_path / 'hl' / 'expected_results.json').exists()


def test_import_sby(tmp_path):
    (tmp_path / 'x.sby').write_text('[options]\nmode bmc\ndepth 12\n\n[script]\nread -formal top.v\nprep -top top\n\n[files]\ntop.v\n')
    code, out, err = sh(['import-sby', 'x.sby'], cwd=tmp_path)
    assert code == 0, err
    t = (tmp_path / 'glitchsat.yaml').read_text()
    assert 'top: top' in t and 'horizon: 12' in t and 'TODO' in t


@needs_yosys
def test_redact_replaces_every_design_name(tmp_path):
    shutil.copytree(os.path.join(EXAMPLES, 'hello_lock'), tmp_path / 'hl', ignore=shutil.ignore_patterns('.glitchsat', '*.lock'))
    code, out, err = sh(['run', 'glitchsat.yaml', '--redact', '--quick', '--json-only'], cwd=tmp_path / 'hl')
    assert code == 1, err
    for name in ('open_o', 'code_i', 'try_i', 'hello_lock', 'rst_n'):
        assert name not in out, name
    rep = json.loads(out)
    assert rep['redacted']['aliases'] > 3 and rep['summary']['checks'][0]['min_faults'] == 1


@needs_yosys
def test_no_network_connections(monkeypatch, tmp_path):
    """The whole pipeline runs with every socket connection refused (in-process part)."""
    def refuse(*a, **k):
        raise AssertionError('GS060: network access attempted')
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket.socket, 'connect_ex', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)
    rep, _ = run_project(os.path.join(copy_example('hello_lock', tmp_path), 'glitchsat.yaml'))
    assert rep['summary']['checks'][0]['min_faults'] == 1


def test_no_network_code_in_package():
    """No module of the package (or the Studio module) imports a network client."""
    import re
    for d in ('glitchsat_byod', os.path.join('tools', 'studio')):
        for f in os.listdir(os.path.join(PKG, d)):
            if f.endswith('.py'):
                src = open(os.path.join(PKG, d, f)).read()
                assert not re.search(r'^\s*(import|from)\s+(urllib\.request|http\.client|requests|socket)\b', src, re.M), f


@needs_yosys
def test_unbounded_finds_longer_attacks_and_proves(project, tmp_path):
    """k = minimum: the unbounded adapter must find an attack (it exists within the horizon)."""
    from glitchsat_byod import unbounded as UB, run as RN
    p = os.path.join(copy_example('hello_lock', tmp_path), 'glitchsat_hardened.yaml')
    rep, spec = run_project(p, only=['min_faults'])
    mf = rep['checks'][0]['analyses']['min_faults']
    assert (mf['verdict'], mf['min_faults']) == ('ATTACK_FOUND', 3)       # one flip per copy (max_faults: 3)
    # rebuild the composed problem and ask for 3 faults: an attack exists (one flip per copy)
    from glitchsat_byod import project as PRJ, flows as FL, detect as DET, compose as CO, netlist as NL
    spec, W = PRJ.load(p)
    E = FL.elaborate(spec, spec['out'])
    det = DET.detect(E['detect']['modules'][E['top']])
    res = CO.resolve(spec, det, [])
    RN.CLOCK[0] = res['clock']
    R, s, info = RN.import_flow(spec, 'plain', E['top'], spec['out'], [], lambda *a: None)
    ch = spec['checks'][0]
    M, text = CO.make_monitor(spec, ch, res, det, E['flat']['modules'][E['top']])
    mv = os.path.join(spec['out'], 'm.v'); open(mv, 'w').write(text)
    Mi = NL.import_module(FL.synth_small(mv, 'glitchsat_monitor', spec['out'], 'mon_t')['module'], 'm', None, clock_ports=[CO.MON.CLK])
    X = CO.compose(spec, res, R, s['module'], Mi, ch, {})
    assert UB.prove(spec, X, 3, time_s=60)['verdict'] == 'ATTACK_FOUND'
    assert UB.prove(spec, X, 2, time_s=60)['verdict'] == 'PROVED_UNBOUNDED'


@needs_yosys
@pytest.mark.skipif(not have_lib('nangate45'), reason='Nangate45 not fetched')
def test_synfi_nangate_netlist_matches_yosys_reading():
    """Import of a third-party Nangate45 netlist (lowRISC/synfi AES FSM) vs Yosys's own reading of the same cells
    (read_liberty functional models, flattened): equal outputs on random inputs for 12 cycles from the same state."""
    from glitchsat_byod import liberty as LIB, netlist as NL, sim as SIM, flows as FL
    import random, tempfile
    nl = os.environ.get('GLITCHSAT_SYNFI_NETLIST', '')   # lowRISC/synfi examples/aes_cipher_control_fsm/netlist_aes_cipher_control_fsm.json
    if not os.path.isfile(nl):
        pytest.skip('SYNFI netlist not given (GLITCHSAT_SYNFI_NETLIST)')
    lp = os.path.join(FL.libs_dir(), FL.KNOWN_LIBS['nangate45'])
    lib = LIB.load(lp)
    doc = json.load(open(nl)); top = next(iter(doc['modules']))
    A = NL.import_module(doc['modules'][top], top, lib, clock_ports=['clk_i'])
    d = tempfile.mkdtemp(); out = os.path.join(d, 'y.json')
    r = subprocess.run(['yosys', '-q', '-p', 'read_liberty -ignore_miss_func "%s"; read_json "%s"; hierarchy -top %s; flatten; opt_clean; write_json "%s"'
                        % (lp, nl, top, out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    Bm = json.load(open(out))['modules'][top]
    B = NL.import_module(Bm, top, None, clock_ports=['clk_i'])
    rng = random.Random(3)
    W = 64; mask = (1 << W) - 1
    ins = [p for p, v in doc['modules'][top]['ports'].items() if v['direction'] == 'input' and p != 'clk_i']
    outs = [p for p, v in doc['modules'][top]['ports'].items() if v['direction'] == 'output']
    sa = {q: 0 for q in A.circ.flops}; sb = {q: 0 for q in B.circ.flops}
    oa, ob = SIM.order(A.circ), SIM.order(B.circ)
    for t in range(12):
        vals = {(p, i): rng.getrandbits(W) for p in ins for i in range(len(doc['modules'][top]['ports'][p]['bits']))}
        if t == 0:
            vals[('rst_ni', 0)] = 0
        ia = {b: vals[(p, i)] for b, (p, i) in A.circ.inputs.items()}
        ib = {b: vals[(p, i)] for b, (p, i) in B.circ.inputs.items()}
        va, sa = SIM.step(A.circ, oa, sa, ia, mask)
        vb, sb = SIM.step(B.circ, ob, sb, ib, mask)
        for p in outs:
            for ba, bb in zip(A.port_bits[p], B.port_bits[p]):
                x = va.get(ba, 0) if isinstance(ba, int) else (mask if ba == '1' else 0)
                y = vb.get(bb, 0) if isinstance(bb, int) else (mask if bb == '1' else 0)
                assert x == y, (t, p)


@needs_yosys
def test_studio_module_http(tmp_path):
    st = os.environ.get('GLITCHSAT_STUDIO') or next((p for p in (os.path.join(PKG, 'tools', 'studio', 'studio.py'), os.path.join(os.path.dirname(PKG), 'studio', 'studio.py')) if os.path.isfile(p)), '')
    if not os.path.isfile(st):
        pytest.skip('studio.py not found')
    import socket
    with socket.socket() as so:                 # a free port: another Studio may be running on a fixed one
        so.bind(('127.0.0.1', 0))
        port = so.getsockname()[1]
    env = dict(os.environ, GLITCHSAT_STUDIO=st)
    p = subprocess.Popen([sys.executable, os.path.join(PKG, 'tools', 'studio', 'studio_byod.py'), '--port', str(port), '--no-browser',
                          '--no-autostop'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=str(tmp_path))
    try:
        base = 'http://127.0.0.1:%d' % port
        for _ in range(60):
            try:
                page = urllib.request.urlopen(base + '/', timeout=2)
                break
            except Exception:              # noqa: BLE001
                time.sleep(0.25)
        assert "default-src 'self'" in page.headers.get('Content-Security-Policy', '')
        html = page.read().decode()
        assert "registerView({id:'mine'" in html and 'cdn' not in html.lower()
        tok = html.split("const TOKEN='")[1].split("'")[0]
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + '/api/byod/examples', timeout=5)              # no token: refused
        req = urllib.request.Request(base + '/api/byod/examples', headers={'X-GlitchSAT-Token': tok})
        ex = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert {e['id'] for e in ex['examples']} >= {'hello_lock', 'secure_boot'}
        body = json.dumps({'folder': os.path.join(EXAMPLES, 'hello_lock'), 'top': 'hello_lock'}).encode()
        req = urllib.request.Request(base + '/api/byod/open', data=body, headers={'X-GlitchSAT': '1', 'X-GlitchSAT-Token': tok,
                                                                                    'Content-Type': 'application/json'})
        det = json.loads(urllib.request.urlopen(req, timeout=60).read())
        assert det.get('clock') == 'clk' and det['reset']['port'] == 'rst_n', det
        req = urllib.request.Request(base + '/api/byod/browse', data=json.dumps({'path': '/etc'}).encode(),
                                     headers={'X-GlitchSAT': '1', 'X-GlitchSAT-Token': tok, 'Content-Type': 'application/json'})
        assert 'error' in json.loads(urllib.request.urlopen(req, timeout=5).read())            # outside home: refused
        bad = urllib.request.Request(base + '/api/byod/examples', headers={'X-GlitchSAT-Token': tok, 'Host': 'evil.example:%d' % port})
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad, timeout=5)                                               # DNS rebinding: refused
    finally:
        p.terminate()
        p.wait(timeout=10)


@needs_yosys
def test_init_from_tinytapeout(tmp_path):
    """A Tiny Tapeout project: info.yaml names the top module and the source files in src/."""
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'project.v').write_text('''
module tt_um_lock (input [7:0] ui_in, output [7:0] uo_out, input [7:0] uio_in, output [7:0] uio_out, output [7:0] uio_oe,
                   input ena, input clk, input rst_n);
  reg open_q;
  always @(posedge clk or negedge rst_n) if (!rst_n) open_q <= 0; else if (ui_in == 8'hA5) open_q <= 1;
  assign uo_out = {7'b0, open_q}; assign uio_out = 0; assign uio_oe = 0;
endmodule
''')
    (tmp_path / 'info.yaml').write_text('project:\n  title: "lock"\n  top_module: "tt_um_lock"\n  source_files:\n    - "project.v"\n')
    code, out, err = sh(['init', '--from-tinytapeout', str(tmp_path), '--yes', '--template', 'custom'])
    assert code == 0, err
    t = (tmp_path / 'glitchsat.yaml').read_text()
    assert 'top: tt_um_lock' in t and 'src/project.v' in t and 'clock: clk' in t
    t = t.replace('bad: "uo_out != 0"', 'bad: "uo_out[0]"\n    must_hold: ["ui_in != 8\'hA5"]').replace('horizon: 20', 'horizon: 5')
    (tmp_path / 'glitchsat.yaml').write_text(t)
    code, out, err = sh(['run', '--quick'], cwd=tmp_path)
    assert code == 1 and '1 fault is enough' in out, out + err
