"""Regression tests for the fixes of the review of this module: a project file can never run a program (B1), fault
semantics do not depend on enable flip-flops (B2), the module works when landed in the repository and its examples
survive a copy (B3), and the should/nice items (honest reports, redaction, lock file, templates, messages)."""
import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

from conftest import needs_yosys, have_lib, DESIGNS, EXAMPLES, PKG
from glitchsat_byod.errors import GSError, explain
from glitchsat_byod.run import run_project
from glitchsat_byod import flows as FL
from glitchsat_byod import project as PRJ

GS = os.path.join(PKG, 'glitchsat')


def sh(args, cwd=None, env=None):
    r = subprocess.run([sys.executable, GS] + args, capture_output=True, text=True, cwd=cwd, env=env, timeout=600)
    return r.returncode, r.stdout, r.stderr


def lock_src(tmp_path, extra_design='', extra='', flows='', check_extra=''):
    shutil.copy(os.path.join(EXAMPLES, 'hello_lock', 'rtl', 'hello_lock.v'), tmp_path / 'hello_lock.v')
    p = tmp_path / 'glitchsat.yaml'
    p.write_text(textwrap.dedent('''
        glitchsat: 1
        design:
          sources: [hello_lock.v]
          top: hello_lock
        %s
        clock: clk
        reset: {port: rst_n, active: low}
        checks:
          - id: c
            bad: "open_o"
            must_hold: ["!(try_i && code_i == 8'hA5)"]
        %s
        faults: {max_faults: 1, horizon: 4}
        analyses: [validate, min_faults]
        %s
        ''') % (textwrap.indent(extra_design, '  ').strip() and textwrap.indent(extra_design, '  '), check_extra, flows) + extra)
    return str(p)


# ================================================================ B1: a project file never runs a program

MARK = 'PWNED_marker'


def _refused(tmp_path, path, code='GS002'):
    with pytest.raises(GSError) as e:
        run_project(path)
    assert e.value.code == code, e.value.render()
    assert not any(MARK in f for f in os.listdir(tmp_path)), 'a marker file was created'
    rc, out, err = sh(['check', path])
    assert rc == 3 and code in err, out + err
    assert not any(MARK in f for f in os.listdir(tmp_path))
    return e.value


def test_newline_in_define_is_refused(tmp_path):
    mk = tmp_path / MARK
    p = lock_src(tmp_path, extra_design='defines: {FOO: "1 x.v\\n!touch %s\\nread_verilog -sv"}' % mk)
    e = _refused(tmp_path, p)
    assert 'define' in e.msg


@pytest.mark.parametrize('cmd', ['!touch {m}', 'shell touch {m}', 'tee -o {m} stat', 'script {m}.ys', 'exec -- touch {m}',
                                 'abc -exe /bin/sh', 'plugin -i x.so', 'write_verilog {m}', 'synth -top hello_lock; !touch {m}',
                                 'log -o {m} x', 'select -write {m}'])
def test_yosys_script_escape_hatch_is_sandboxed(tmp_path, cmd):
    mk = str(tmp_path / MARK)
    p = lock_src(tmp_path, extra_design='yosys_script: [%s]' % json.dumps(cmd.format(m=mk)), flows='flows: [custom]')
    _refused(tmp_path, p)


def test_yosys_script_path_traversal_is_refused(tmp_path):
    os.makedirs(tmp_path / 'proj')
    outside = tmp_path / 'outside.v'
    outside.write_text('module evil(); endmodule\n')
    shutil.copy(os.path.join(EXAMPLES, 'hello_lock', 'rtl', 'hello_lock.v'), tmp_path / 'proj' / 'hello_lock.v')
    p = tmp_path / 'proj' / 'glitchsat.yaml'
    p.write_text(textwrap.dedent('''
        glitchsat: 1
        design: {sources: [hello_lock.v], top: hello_lock, yosys_script: ["read_verilog ../outside.v", "synth -top hello_lock"]}
        checks: [{id: c, bad: "open_o"}]
        flows: [custom]
        '''))
    with pytest.raises(GSError) as e:
        run_project(str(p))
    assert e.value.code == 'GS002' and 'outside the project folder' in e.value.msg


def test_allowed_custom_script_runs_and_is_shown_by_check(tmp_path):
    p = lock_src(tmp_path, extra_design='yosys_script: ["synth -top hello_lock -flatten", "opt_clean"]', flows='flows: [custom]')
    spec, _ = PRJ.load(p)
    assert FL.user_script(spec) == ['synth -top hello_lock -flatten', 'opt_clean']
    rc, out, err = sh(['check', p])
    assert 'runs its own Yosys commands' in out and 'synth -top hello_lock -flatten' in out, out + err


@pytest.mark.parametrize('patch,what', [
    ('report: {out: ../../escaped}', 'report.out'),
    ('probes: {p: "u_x.sig;!touch"}', 'probe'),
    ('tasks: {"../x": {name: y}}', 'task'),
])
def test_other_injection_paths_are_refused(tmp_path, patch, what):
    p = lock_src(tmp_path, extra=patch + '\n')
    with pytest.raises(GSError) as e:
        PRJ.load(p)
    assert e.value.code == 'GS002', e.value.render()


def test_guard_line_is_the_last_line_of_defence():
    for bad in ['!touch x', 'read_verilog "a.v"; !touch x', 'read_verilog a.v\n!touch x', 'shell', 'tee -o x stat']:
        with pytest.raises(GSError):
            FL.guard_line(bad)
    assert FL.guard_line('read_verilog -sv "a;b.v"')          # a quoted ; inside a path is not a command separator


def test_param_and_top_validation():
    for spec in (dict(params={'W; !x': 1}), dict(params={'W': '1 -x'}), dict(defines={'A': 'b c'}), dict(defines={'A B': None})):
        s = dict(dict(sources=['a.v'], frontend='verilog', include_dirs=[], defines={}, params={}, liberty=[], blackboxes=[]), **spec)
        with pytest.raises(GSError):
            FL.read_cmds(s, None)
            FL.hier_cmds(s, 'top')
    with pytest.raises(GSError):
        FL.hier_cmds(dict(sources=['a.v'], frontend='verilog', params={}), 'top\n!x')


def test_studio_requires_confirmation_for_projects_outside_the_gallery(tmp_path, monkeypatch):
    import importlib.util as ilu
    sp = ilu.spec_from_file_location('byod_view_t', os.path.join(PKG, 'tools', 'studio', 'byod_view.py'))
    bv = ilu.module_from_spec(sp); sp.loader.exec_module(bv)
    monkeypatch.setattr(bv, 'ROOTS', [str(tmp_path), bv.EXAMPLES])
    p = lock_src(tmp_path, extra_design='yosys_script: ["synth -top hello_lock -flatten"]', flows='flows: [custom]')
    r = bv.start_run(dict(path=p))
    assert r.get('confirm_needed') and 'id' not in r
    rd = bv.read_yaml(dict(path=p))
    assert rd['plan']['custom'] and any('synth -top hello_lock -flatten' in c for c in rd['plan']['flows']['custom'])
    open(p, 'a').write('# changed after the plan was shown\n')
    assert bv.start_run(dict(path=p, confirm=rd['nonce'])).get('confirm_needed')      # the code is bound to the content
    # wizard file names and values
    assert 'error' in bv.write_yaml(dict(folder=str(tmp_path), file='/tmp/abs.yaml', answers={}))
    assert 'error' in bv.write_yaml(dict(folder=str(tmp_path), file='../x.yaml', answers={}))
    assert 'error' in bv.read_yaml(dict(path=str(tmp_path / 'hello_lock.v')))
    w = bv.write_yaml(dict(folder=str(tmp_path), file='w.yaml', dry=True,
                           answers=dict(name='x\n!echo hi', sources=['hello_lock.v'], top='hello_lock\nflows: [custom]',
                                        clock='clk', reset=None, attacker=['code_i'], template='custom', bad='open_o')))
    import yaml
    doc = yaml.safe_load(w['text'])
    assert 'flows' not in doc and doc['design']['top'] == 'hello_lock\nflows: [custom]'


# ================================================================ B2: same fault model for every flow

@needs_yosys
def test_enable_flop_gives_the_same_minimum_in_every_flow(tmp_path):
    shutil.copy(os.path.join(DESIGNS, 'en_reg.v'), tmp_path / 'en_reg.v')
    p = tmp_path / 'glitchsat.yaml'
    p.write_text(textwrap.dedent('''
        glitchsat: 1
        design: {sources: [en_reg.v], top: en_reg}
        clock: clk
        reset: {port: rst_n, active: low}
        checks: [{id: kept, bad: "!$initial && $past(r) && r", must_hold: ["!en"]}]
        faults: {where: flops, max_faults: 2, horizon: 6}
        flows: [plain, synth, synth-keep, synth-nofsm]
        analyses: [validate, min_faults, survival]
        '''))
    rep, _ = run_project(str(p))
    rows = {r['flow']: r['min_faults'] for r in rep['checks'][0]['analyses']['survival']['rows']}
    assert rows == {'plain': 1, 'synth': 1, 'synth-keep': 1, 'synth-nofsm': 1}, rows
    for fl in rows:
        assert 'dffunmap' in rep['flows'][fl]['normalised']
        assert any(c.startswith('dffunmap') for c in rep['flows'][fl]['commands'])


@needs_yosys
def test_json_netlist_with_enable_flops_is_normalised(tmp_path):
    shutil.copy(os.path.join(DESIGNS, 'en_reg.v'), tmp_path / 'en_reg.v')
    ys = FL.find_yosys()
    subprocess.run([ys.path, '-q', '-p', 'read_verilog en_reg.v; synth -top en_reg -flatten; write_json en_reg.json'],
                   cwd=tmp_path, check=True)
    assert '$_DFFE_' in (tmp_path / 'en_reg.json').read_text()
    p = tmp_path / 'glitchsat.yaml'
    p.write_text(textwrap.dedent('''
        glitchsat: 1
        design: {sources: [en_reg.json], top: en_reg, frontend: json}
        clock: clk
        reset: {port: rst_n, active: low}
        checks: [{id: kept, bad: "!$initial && $past(r) && r", must_hold: ["!en"]}]
        faults: {where: flops, max_faults: 2, horizon: 6}
        analyses: [min_faults]
        '''))
    rep, _ = run_project(str(p))
    assert rep['checks'][0]['analyses']['min_faults']['min_faults'] == 1


def test_importer_stored_value_site_without_dffunmap():
    """Even a $_DFFE_ cell read directly (no Yosys normalisation) has its stored value as the one fault site, so a
    flip persists through the hold path."""
    from glitchsat_byod import netlist as NL
    mod = dict(ports=dict(clk=dict(direction='input', bits=[2]), en=dict(direction='input', bits=[3]),
                          d=dict(direction='input', bits=[4]), r=dict(direction='output', bits=[5])),
               cells={'ff': dict(type='$_DFFE_PP_', connections=dict(C=[2], D=[4], E=[3], Q=[5]))}, netnames={})
    R = NL.import_module(mod, 'x', None, clock_ports=['clk'])
    flops = [si for si in R.site_info.values() if si['kind'] == 'flop']
    assert len(flops) == 1 and flops[0]['pin'] == 'stored'
    q = next(iter(R.circ.flops))
    qf = R.stored[q]
    d, _ = R.circ.flops[q]
    # the next state (hold path) reads the stored-value site, not the raw flop
    seen, todo = set(), [d]
    while todo:
        n = todo.pop()
        if n in seen or not isinstance(n, int):
            continue
        seen.add(n)
        todo += list(R.circ.gates.get(n, ('', ()))[1])
    assert qf in seen


@needs_yosys
@pytest.mark.skipif(not have_lib('sky130hd'), reason='sky130 not fetched')
def test_liberty_enable_flop_flip_persists(project):
    nl = '''
    module enl(input clk, input d, input en, output q);
      sky130_fd_sc_hd__edfxtp_1 u_ff (.CLK(clk), .D(d), .DE(en), .Q(q));
      sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_1 ();
    endmodule
    '''
    p = project('''
        glitchsat: 1
        design: {sources: [enl.v], top: enl, frontend: netlist, liberty: [$GLITCHSAT_LIBS/sky130hd/sky130_fd_sc_hd__tt_025C_1v80.lib]}
        clock: clk
        reset: none
        powerup: zero
        checks: [{id: c, bad: "!$initial && $past(q) && q", must_hold: ["!en"]}]
        faults: {max_faults: 2, horizon: 4}
        analyses: [validate, min_faults]
        ''', files={'enl.v': nl})
    rep, _ = run_project(p)
    assert rep['checks'][0]['analyses']['min_faults']['min_faults'] == 1
    assert rep['flows']['netlist']['physical_dropped'] == {'sky130_fd_sc_hd__tapvpwrvgnd_1': 1}
    assert 'Physical-only cells dropped' in __import__('glitchsat_byod.report', fromlist=['x']).plain(rep)


# ================================================================ B3: landing and copies

@needs_yosys
def test_runs_when_landed_as_tools_byod(tmp_path):
    root = os.environ.get('GLITCHSAT_ROOT') or ''
    from glitchsat_byod import engine as EN
    if not EN.repo_root():
        pytest.skip('repository not available')
    repo = tmp_path / 'repo'
    os.makedirs(repo / 'scripts'); os.makedirs(repo / 'tools')
    os.symlink(os.path.join(EN.repo_root(), 'scripts', 'glitchsat.py'), repo / 'scripts' / 'glitchsat.py')
    for n in ('scale', 'fastsat', 'unbounded', 'checker'):
        os.symlink(EN.tool_dir(n), repo / 'tools' / n)
    shutil.copytree(PKG, repo / 'tools' / 'byod', ignore=shutil.ignore_patterns('.glitchsat', '__pycache__', '.pytest_cache', 'saved'))
    env = {k: v for k, v in os.environ.items() if not k.startswith('GLITCHSAT_') or k in ('GLITCHSAT_YOSYS', 'GLITCHSAT_LIBS')}
    g = str(repo / 'tools' / 'byod' / 'glitchsat')
    r = subprocess.run([sys.executable, g, 'doctor'], capture_output=True, text=True, env=env)
    assert r.returncode == 0 and str(repo) in r.stdout, r.stdout + r.stderr
    r = subprocess.run([sys.executable, g, 'examples', 'copy', 'secure_boot', str(tmp_path / 'sb')], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([sys.executable, g, 'run', '--quick', '--only', 'min_faults'], capture_output=True, text=True, env=env,
                       cwd=tmp_path / 'sb', timeout=600)
    assert r.returncode == 1 and '1 fault is enough' in r.stdout, r.stdout + r.stderr


def test_missing_repository_is_gs021_not_a_traceback(tmp_path):
    lone = tmp_path / 'lone'
    shutil.copytree(PKG, lone, ignore=shutil.ignore_patterns('.glitchsat', '__pycache__', '.pytest_cache', 'saved', 'examples'))
    shutil.copytree(os.path.join(EXAMPLES, 'hello_lock'), tmp_path / 'hl', ignore=shutil.ignore_patterns('.glitchsat', '*.lock', 'saved'))
    env = {k: v for k, v in os.environ.items() if not k.startswith('GLITCHSAT_')}
    r = subprocess.run([sys.executable, str(lone / 'glitchsat'), 'run'], capture_output=True, text=True, env=env, cwd=tmp_path / 'hl')
    assert r.returncode == 3 and 'error[GS021]' in r.stderr and 'Traceback' not in r.stderr, r.stderr
    assert 'GLITCHSAT_ROOT' in r.stderr


def test_secure_boot_copy_is_self_contained(tmp_path):
    rc, out, err = sh(['examples', 'copy', 'secure_boot', str(tmp_path / 'sb')])
    assert rc == 0, err
    spec, _ = PRJ.load(str(tmp_path / 'sb' / 'glitchsat.yaml'))
    assert all(s.startswith(str(tmp_path / 'sb')) for s in spec['sources'])


@needs_yosys
def test_run_examples_check_fails_on_a_difference(tmp_path):
    ex = tmp_path / 'ex'
    os.makedirs(ex)
    shutil.copytree(os.path.join(EXAMPLES, 'hello_lock'), ex / 'hello_lock', ignore=shutil.ignore_patterns('.glitchsat', 'saved'))
    les = json.load(open(ex / 'hello_lock' / 'lesson.json'))
    les['runs'] = les['runs'][:1]
    json.dump(les, open(ex / 'hello_lock' / 'lesson.json', 'w'))
    er = json.load(open(ex / 'hello_lock' / 'expected_results.json'))
    er = {k: v for k, v in er.items() if k == 'glitchsat.yaml'}
    json.dump(er, open(ex / 'hello_lock' / 'expected_results.json', 'w'))
    script = os.path.join(PKG, 'scripts', 'run_examples.py')
    r = subprocess.run([sys.executable, script, '--check', '--quick', '--examples', str(ex)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    er['glitchsat.yaml']['checks']['open_without_code']['min_faults'] = 2
    json.dump(er, open(ex / 'hello_lock' / 'expected_results.json', 'w'))
    r = subprocess.run([sys.executable, script, '--check', '--quick', '--examples', str(ex)], capture_output=True, text=True)
    assert r.returncode == 1 and 'DIFFERS' in r.stdout
    (ex / 'hello_lock' / 'rtl' / 'hello_lock.v').write_text('module broken(')
    r = subprocess.run([sys.executable, script, '--check', '--quick', '--examples', str(ex)], capture_output=True, text=True)
    assert r.returncode == 1 and 'error now' in r.stdout


# ================================================================ should / nice

@needs_yosys
def test_black_box_boundary_is_in_the_text_report(project):
    p = project('''
        glitchsat: 1
        design: {sources: [missing_module.v], top: uses_ip, blackboxes: [{module: secret_ip, stub: secret_ip_stub.v}]}
        clock: clk
        reset: none
        checks: [{id: c, bad: "y"}]
        faults: {max_faults: 1, horizon: 3}
        analyses: [validate, min_faults]
        ''', copy=['missing_module.v', 'secret_ip_stub.v'])
    rep, _ = run_project(p)
    from glitchsat_byod.report import plain
    t = plain(rep)
    assert 'Coverage boundary' in t and 'u_ip.y' in t and 'free black-box outputs' in t
    assert any(x['id'] == 'blackbox' for x in rep['checks'][0]['what_to_do'])


@needs_yosys
def test_redact_leaks_nothing(tmp_path):
    os.makedirs(tmp_path / 'rtl')
    (tmp_path / 'rtl' / 'zebra_pkg_file.v').write_text(textwrap.dedent('''
        module quokka_unlock_core(input clk, input rst_n, input [7:0] narwhal_token_i, input [7:0] axolotl_try_i,
                                  output reg pangolin_open_o);
          always @(posedge clk or negedge rst_n)
            if (!rst_n) pangolin_open_o <= 1'b0;
            else if (axolotl_try_i == narwhal_token_i) pangolin_open_o <= 1'b1;
        endmodule
        '''))
    (tmp_path / 'glitchsat.yaml').write_text(textwrap.dedent('''
        glitchsat: 1
        name: capybara_project
        design: {sources: [rtl/zebra_pkg_file.v], top: quokka_unlock_core}
        clock: clk
        reset: {port: rst_n, active: low}
        inputs: {attacker: [axolotl_try_i], secret: [narwhal_token_i]}
        checks:
          - id: wombat_opens
            bad: "pangolin_open_o"
            must_hold: ["axolotl_try_i != 8'hC7"]
        faults: {max_faults: 1, horizon: 3}
        analyses: [validate, min_faults, attack_surface]
        '''))
    rc, out, err = sh(['run', '--redact', '--quick'], cwd=tmp_path)
    assert rc == 1, err
    stem = 'glitchsat'
    texts = [out, open(tmp_path / '.glitchsat' / 'default' / 'report.json').read(),
             open(tmp_path / '.glitchsat' / 'default' / 'report.txt').read()]
    for t in texts:
        for w in ('zebra', 'quokka', 'narwhal', 'axolotl', 'pangolin', 'capybara', 'wombat', str(tmp_path), 'C7', "8'hC7"):
            assert w not in t, (w, t[:3000])
    rep = json.loads(texts[1])
    w = rep['checks'][0]['analyses']['min_faults'].get('witness') or {}
    for p, iv in (w.get('inputs') or {}).items():
        if rep['design']['roles'].get(p) == 'secret':
            assert iv['values'] == ['<secret>']
    assert all(s['path'].startswith('file_') for s in rep['provenance']['sources'])
    assert rep['checks'][0]['id'] == 'check_01'


@needs_yosys
def test_lock_records_the_question_and_has_one_file_per_project(tmp_path):
    p = lock_src(tmp_path)
    run_project(p)
    lk = json.load(open(tmp_path / 'glitchsat.lock'))
    assert lk['checks']['c']['horizon'] == 4 and lk['checks']['c']['max_faults'] == 1
    assert lk['faults']['types'] == ['flip'] and lk['project_sha256'] and lk['glitchsat_version']
    t = open(p).read().replace('horizon: 4', 'horizon: 5')
    open(p, 'w').write(t)
    rep, _ = run_project(p)
    assert 'checks' in rep['lock']['changed_since_last_run'] and 'project_sha256' in rep['lock']['changed_since_last_run']
    shutil.copy(p, tmp_path / 'other.yaml')
    rep2, spec2 = run_project(str(tmp_path / 'other.yaml'))
    assert rep2['lock']['path'] == 'other.lock' and rep2['lock']['changed_since_last_run'] == []
    assert spec2['work'].endswith(os.path.join('.glitchsat', 'other', 'default'))


def test_lock_hashes_include_files(tmp_path):
    from glitchsat_byod.run import files_read
    os.makedirs(tmp_path / 'inc')
    (tmp_path / 'inc' / 'defs.svh').write_text('`define X 1\n')
    (tmp_path / 'top.sv').write_text('`include "defs.svh"\nmodule top(input clk); endmodule\n')
    spec = dict(sources=[str(tmp_path / 'top.sv')], include_dirs=[str(tmp_path / 'inc')], blackboxes=[], checks=[],
                raw={}, base=str(tmp_path))
    assert str(tmp_path / 'inc' / 'defs.svh') in files_read(spec)


@needs_yosys
def test_counter_template_catches_a_stuck_retry_counter(project):
    base = '''
        glitchsat: 1
        design: {sources: [pin_retry.v], top: pin_retry}
        clock: clk
        reset: {port: rst_n, active: low}
        inputs: {attacker: [try_i, pin_i]}
        checks:
          - id: tries
            template: counter_skip
            params: {counter: tries_o, step: -1, alarm: alarm_o, alarm_latency: 1%s}
        faults: {max_faults: 2, horizon: 5}
        analyses: [validate, min_faults]
        '''
    rep, _ = run_project(project(base % '', copy=['pin_retry.v']))
    jump = rep['checks'][0]['analyses']['min_faults']
    rep, _ = run_project(project(base % ', must_step_when: "try_i && pin_i != 4\'h9 && tries_o != 0"', copy=['pin_retry.v']))
    stuck = rep['checks'][0]['analyses']['min_faults']
    assert stuck['min_faults'] == 1, stuck            # a wrong try that is not counted: one glitch on the shared enable
    assert jump['min_faults'] == 2, jump              # a jump needs a second glitch to silence the alarm


@needs_yosys
def test_check_resolves_names(tmp_path):
    p = lock_src(tmp_path)
    rc, out, err = sh(['check', p])
    assert rc == 0 and 'Names checked' in out, out + err
    t = open(p).read()
    open(p, 'w').write(t.replace('clock: clk', 'clock: clock'))
    rc, out, err = sh(['check', p])
    assert rc == 3 and 'GS011' in err and "did you mean `clk`" in err
    open(p, 'w').write(t.replace('bad: "open_o"', 'bad: "opn_o"'))
    rc, out, err = sh(['check', p])
    assert rc == 3 and 'opn_o' in err and 'did you mean `open_o`' in err


def test_check_without_yosys_says_names_are_not_checked(tmp_path):
    p = lock_src(tmp_path)
    env = {k: v for k, v in os.environ.items() if k not in ('GLITCHSAT_YOSYS', 'GLITCHSAT_YOSYS_SLANG')}
    env['PATH'] = os.pathsep.join(d for d in env.get('PATH', '').split(os.pathsep) if not os.path.isfile(os.path.join(d, 'yosys')))
    rc, out, err = sh(['check', p], env=env)
    assert rc == 2 and 'Names NOT checked' in out, out + err


def test_gs021_help_does_not_send_users_to_another_yosys_path():
    t = explain('GS021')
    assert 'Every input path needs Yosys' in t and 'Or give a gate-level netlist' not in t


@needs_yosys
def test_undriven_net_is_gs044(project):
    p = project('''
        glitchsat: 1
        design: {sources: [undriven.v], top: undriven_top}
        clock: clk
        reset: none
        powerup: zero
        checks: [{id: c, bad: "y"}]
        faults: {max_faults: 1, horizon: 3}
        ''', copy=['undriven.v'])
    with pytest.raises(GSError) as e:
        run_project(p)
    assert e.value.code == 'GS044' and 'chk' in e.value.msg


def test_import_synfi_reads_fimodels(tmp_path):
    (tmp_path / 'fm.json').write_text(json.dumps({'fimodels': {'rnd_ctr': {
        'simultaneous_faults': 2, 'fault_locations': {'u_ctr.cnt_q_reg': 'flip'},
        'output_values': {'key_expand_round_o': {'O': {'0': 1}}}, 'alert_values': {'alert_o': {'O': {'0': 0}}},
        'node_fault_mapping': {}, 'stages': {}}}}))
    rc, out, err = sh(['import-synfi', 'fm.json', '--out', 'c.yaml'], cwd=tmp_path)
    assert rc == 0, err
    import yaml
    d = yaml.safe_load((tmp_path / 'c.yaml').read_text())
    c = d['checks'][0]
    assert c['id'] == 'rnd_ctr' and c['bad'] == '(key_expand_round_o[0] == 1)' and c['must_hold'] == ['(alert_o[0] == 0)']
    assert d['faults']['max_faults'] == 2 and d['faults']['include'] == ['u_ctr.cnt_q_reg']
    assert 'node_fault_mapping' in err and 'stages' in err
    rc, out, err = sh(['check', 'c.yaml'], cwd=tmp_path)
    assert rc == 3 and ('GS002' in err or 'GS003' in err)


@needs_yosys
def test_hardened_lock_names_the_remedy(tmp_path):
    shutil.copytree(os.path.join(EXAMPLES, 'hello_lock'), tmp_path / 'hl', ignore=shutil.ignore_patterns('.glitchsat', '*.lock', 'saved'))
    p = str(tmp_path / 'hl' / 'glitchsat_hardened.yaml')
    t = open(p).read().replace('max_faults: 3 ', 'max_faults: 1 ')
    open(p, 'w').write(t)
    rep, _ = run_project(p, only=['validate', 'min_faults', 'survival', 'merge_lint'])
    todo = ' '.join(x['text'] for x in rep['checks'][0]['what_to_do'])
    assert 'keep_hierarchy' in todo and 'dont_touch' in todo and 'placement' in todo
    from glitchsat_byod.report import plain
    t = plain(rep)
    assert 'What to do:' in t and 'Weakest build (synth): 1 fault' in t


def test_studio_shows_saved_results_without_yosys(monkeypatch):
    import importlib.util as ilu
    sp = ilu.spec_from_file_location('byod_view_s', os.path.join(PKG, 'tools', 'studio', 'byod_view.py'))
    bv = ilu.module_from_spec(sp); sp.loader.exec_module(bv)
    monkeypatch.setattr(bv, '_TOOLS', {'y': dict(yosys=False, why='Yosys was not found')})
    ex = bv.examples()
    assert ex['tools']['yosys'] is False
    hl = next(x for x in ex['examples'] if x['id'] == 'hello_lock')
    assert all(r['saved'] for r in hl['runs'])
    r = bv.saved(dict(ex='hello_lock', file='glitchsat.yaml', task=''))
    assert r['recorded'] and r['report']['label'] == 'RECORDED' and 'ANSWER' in r['plain']
    assert bv.start_run(dict(example='hello_lock', file='glitchsat.yaml')).get('code') == 'GS021'
    assert 'error' in bv.saved(dict(ex='../etc', file='glitchsat.yaml'))


SKY = '$GLITCHSAT_LIBS/sky130hd/sky130_fd_sc_hd__tt_025C_1v80.lib'


@needs_yosys
@pytest.mark.skipif(not have_lib('sky130hd'), reason='sky130 not fetched')
def test_clear_preset_flop_reference_and_gs046(tmp_path):
    (tmp_path / 'nl.v').write_text(textwrap.dedent('''
        module tamp(input clk, input d, input set_n, input rst_n2, output tamper_o, output qn);
          sky130_fd_sc_hd__dfbbp_1 u_ff (.CLK(clk), .D(d), .SET_B(set_n), .RESET_B(rst_n2), .Q(tamper_o), .Q_N(qn));
        endmodule
        '''))
    (tmp_path / 'glitchsat.yaml').write_text(textwrap.dedent('''
        glitchsat: 1
        design: {sources: [nl.v], top: tamp, frontend: netlist, liberty: [%s]}
        clock: clk
        reset: none
        powerup: zero
        checks: [{id: c, bad: "tamper_o && !d"}]
        faults: {max_faults: 1, horizon: 3}
        analyses: [validate, min_faults]
        ''' % SKY))
    ys = [FL.Yosys(c) for c in (os.environ.get('GLITCHSAT_YOSYS_SLANG'), shutil.which('yosys')) if c and os.path.isfile(c)]
    new = [y for y in ys if y.vnum >= (0, 71)]
    old = [y for y in ys if y.vnum < (0, 71)]
    if new:
        env = dict(os.environ, GLITCHSAT_YOSYS=new[0].path)
        rc, out, err = sh(['run'], cwd=tmp_path, env=env)
        assert 'Checked (netlist)' in out and 'GS050' not in err, out + err
    if old:
        env = {k: v for k, v in os.environ.items() if k not in ('GLITCHSAT_YOSYS_SLANG',)}
        env['GLITCHSAT_YOSYS'] = old[0].path
        env['PATH'] = os.path.dirname(old[0].path) + os.pathsep + env.get('PATH', '')
        rc, out, err = sh(['run'], cwd=tmp_path, env=env)
        assert rc == 3 and 'GS046' in err, out + err


@needs_yosys
@pytest.mark.skipif(not have_lib('sky130hd'), reason='sky130 not fetched')
def test_scan_enable_driven_by_attacker_is_reported(project):
    nl = '''
    module scan2(input clk, input d, input si, input shift_i, output q);
      sky130_fd_sc_hd__sdfxtp_1 u_ff (.CLK(clk), .D(d), .SCD(si), .SCE(shift_i), .Q(q));
    endmodule
    '''
    p = project('''
        glitchsat: 1
        design: {sources: [scan2.v], top: scan2, frontend: netlist, liberty: [%s]}
        clock: clk
        reset: none
        powerup: zero
        checks: [{id: c, bad: "q && !$past(d)"}]
        faults: {max_faults: 1, horizon: 3}
        analyses: [validate, min_faults]
        ''' % SKY, files={'scan2.v': nl})
    rep, _ = run_project(p)
    from glitchsat_byod.report import plain
    t = plain(rep)
    assert 'scan enable of 1 flip-flop is driven by attacker input `shift_i`' in t
    assert any(w['code'] == 'GS073' for w in rep['warnings'])
