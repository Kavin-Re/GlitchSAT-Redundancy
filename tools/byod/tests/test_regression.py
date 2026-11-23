"""Regression suite: one design per frontend, per difficult cell or flop kind, and per silent-weakening case.
Every silent weakening must be an error that names the problem (never a quiet change of the question)."""
import json
import os

import pytest

from conftest import needs_yosys, have_lib, DESIGNS
from glitchsat_byod.errors import GSError, EXPLAIN
from glitchsat_byod.run import run_project

pytestmark = needs_yosys

BASE = '''
glitchsat: 1
design: {sources: [%s], top: %s}
%s
checks:
  - id: c
    bad: "%s"
%s
faults: {max_faults: %d, horizon: %d}
analyses: [validate, min_faults]
'''


def mk(project, src, top, bad, extra='', check_extra='', k=2, n=6, copy=None, files=None):
    return project(BASE % (src, top, extra, bad, check_extra, k, n), copy=copy or [src], files=files)


def code_of(path, **kw):
    with pytest.raises(GSError) as e:
        run_project(path, **kw)
    return e.value


# ---------------------------------------------------------------- silent-weakening cases are errors
def test_missing_module_is_an_error(project):
    e = code_of(mk(project, 'missing_module.v', 'uses_ip', 'y', 'clock: clk\nreset: none'))
    assert e.code == 'GS023' and 'secret_ip' in e.msg and 'blackboxes' in e.help


def test_declared_blackbox_becomes_free_input(project):
    p = mk(project, 'missing_module.v', 'uses_ip', 'y', 'clock: clk\nreset: none',
           copy=['missing_module.v', 'secret_ip_stub.v'])
    txt = open(p).read().replace('top: uses_ip}', 'top: uses_ip, blackboxes: [{module: secret_ip, stub: secret_ip_stub.v}]}')
    open(p, 'w').write(txt)
    rep, spec = run_project(p)
    fl = rep['flows']['plain']
    assert fl['blackbox_outputs'] == [dict(cell='u_ip', pin='y')]
    # the black-box output is free: the bad condition y is reachable with 0 faults, and the report says so
    assert rep['checks'][0]['analyses']['min_faults']['verdict'] == 'FAILS_WITHOUT_FAULTS'
    assert rep['provenance']['flows']['plain']['blackboxes']


def test_selector_matching_nothing_is_an_error(project):
    p = mk(project, 'fsm.v', 'pw_fsm', 'open_o', 'clock: clk\nreset: {port: rst_n, active: low}',
           check_extra='')
    open(p, 'a').write('')
    txt = open(p).read().replace('faults: {', 'faults: {exclude: ["u_nothere.*"], ')
    open(p, 'w').write(txt)
    e = code_of(p)
    assert e.code == 'GS018' and 'u_nothere' in e.msg


def test_unknown_port_in_condition(project):
    e = code_of(mk(project, 'fsm.v', 'pw_fsm', 'opn_o', 'clock: clk'))
    assert e.code == 'GS011' and 'open_o' in e.note


def test_unknown_probe(project):
    e = code_of(mk(project, 'fsm.v', 'pw_fsm', 'u_x.state_q == 2', 'clock: clk'))
    assert e.code == 'GS017'


def test_latch_is_refused(project):
    e = code_of(mk(project, 'latch.v', 'has_latch', 'q', 'clock: none\nreset: none'))
    assert e.code in ('GS036', 'GS012'), e.render()


def test_gated_clock_is_refused(project):
    e = code_of(mk(project, 'gated_clock.v', 'gated', 'q', 'clock: clk\nreset: none'))
    assert e.code == 'GS013'


def test_unknown_yaml_key_suggests(project):
    p = mk(project, 'fsm.v', 'pw_fsm', 'open_o', 'clock: clk')
    txt = open(p).read().replace('faults: {', 'fault: {')
    open(p, 'w').write(txt)
    e = code_of(p)
    assert e.code == 'GS002' and 'faults' in e.msg, e.render()


def test_tab_and_yaml_errors(project):
    p = project('glitchsat: 1\ndesign:\n\tsources: [x.v]\n')
    assert code_of(p).code == 'GS001'
    p = project('glitchsat: 1\nchecks:\n  - id: c\n    bad: !open\n')
    assert code_of(p).code in ('GS001', 'GS002')


def test_assertions_dropped(project):
    p = project('''
        glitchsat: 1
        design: {sources: [fsm.v], top: pw_fsm}
        clock: clk
        checks: [{id: c, assertions: props.sv}]
        faults: {max_faults: 1, horizon: 4}
        analyses: [min_faults]
        ''', copy=['fsm.v'], files={'props.sv': 'module props(input open_o);\nendmodule\n'})
    assert code_of(p).code == 'GS024'


def test_every_code_has_an_explanation():
    import re
    src = ''
    d = os.path.join(os.path.dirname(DESIGNS), '..', 'glitchsat_byod')
    for f in os.listdir(d):
        if f.endswith('.py'):
            src += open(os.path.join(d, f)).read()
    used = set(re.findall(r"'(GS\d{3})'", src))
    assert used <= set(EXPLAIN), used - set(EXPLAIN)


# ---------------------------------------------------------------- frontends and difficult flops
def test_fsm_with_probe_and_validation(project):
    p = mk(project, 'fsm.v', 'pw_fsm', 'open_o', 'clock: clk\nreset: {port: rst_n, active: low}',
           check_extra='    must_hold: ["!(state_o == 2\'d1 && pw_i == 4\'h9)"]', k=2, n=6)
    rep, _ = run_project(p)
    mf = rep['checks'][0]['analyses']['min_faults']
    assert mf['verdict'] == 'ATTACK_FOUND' and mf['min_faults'] == 1
    assert rep['checks'][0]['flows']['plain']['validation']['mismatch'] is None


def test_internal_signal_probe(project):
    p = mk(project, 'fsm.v', 'pw_fsm', "state_q == 2'd2", 'clock: clk\nreset: {port: rst_n, active: low}\ninputs: {fixed: {go_i: 0}}')
    rep, _ = run_project(p)
    mf = rep['checks'][0]['analyses']['min_faults']
    assert mf['verdict'] == 'ATTACK_FOUND'
    p2 = mk(project, 'fsm.v', 'pw_fsm', "u_none.state_q == 2'd2", 'clock: clk')
    assert code_of(p2).code == 'GS017'


def test_enable_syncreset_asyncset_flops_validate(project):
    p = mk(project, 'enflop.v', 'enflop', 'q == 2\'b11 && !en', 'clock: clk\nreset: none\npowerup: zero', n=5)
    txt = open(p).read().replace('analyses: [validate, min_faults]', 'analyses: [validate, min_faults]\nflows: [plain, synth]')
    open(p, 'w').write(txt)
    rep, _ = run_project(p)
    for fl in ('plain', 'synth'):
        assert rep['checks'][0]['flows'][fl]['validation']['mismatch'] is None
    assert rep['checks'][0]['analyses']['min_faults']['verdict'] in ('ATTACK_FOUND', 'FAILS_WITHOUT_FAULTS')


def test_json_netlist_frontend(project, tmp_path):
    p = mk(project, 'counter.v', 'ctr', '!$initial && cnt_o != $past(cnt_o)', 'clock: clk\nreset: {port: rst_n, active: low}\ninputs: {fixed: {inc_i: 0}}',
           check_extra='    detected_by: err_o', k=3, n=4)
    rep, spec = run_project(p)
    m1 = rep['checks'][0]['analyses']['min_faults']['min_faults']
    nl = os.path.join(spec['base'], rep['flows']['plain']['netlist'])
    q = project(open(p).read().replace('sources: [counter.v]', 'sources: [%s], frontend: json' % nl))
    rep2, _ = run_project(q)
    assert rep2['checks'][0]['analyses']['min_faults']['min_faults'] == m1 == 2


def test_set_reset_fault_types(project):
    src = os.path.join(os.path.dirname(DESIGNS), '..', 'examples', 'hello_lock', 'rtl', 'hello_lock.v')
    base = '''
        glitchsat: 1
        design: {sources: [%s], top: hello_lock}
        clock: clk
        reset: {port: rst_n, active: low}
        checks: [{id: c, bad: "open_o", must_hold: ["!(try_i && code_i == 8'hA5)"]}]
        faults: {max_faults: 2, horizon: 5, types: [%s]}
        analyses: [min_faults]
        '''
    files = {'hello_lock.v': open(src).read()}           # a copy inside the project: sources must lie in its folder
    r_set, _ = run_project(project(base % ('hello_lock.v', 'set'), files=files))
    assert r_set['checks'][0]['analyses']['min_faults']['min_faults'] == 1
    r_rst, _ = run_project(project(base % ('hello_lock.v', 'reset'), files=files))
    # forcing wires to 0 can still open the lock through the comparator logic (a NOT output forced to 0 ...)
    assert r_rst['checks'][0]['analyses']['min_faults']['verdict'] in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND')
    w = r_set['checks'][0]['analyses']['min_faults']['witness']
    assert w['faults'][0]['type'] == 'set' and w['replayed']


def test_validation_catches_a_wrong_netlist(project, monkeypatch):
    """Break the analysed circuit on purpose: the simulation check must refuse it (GS050)."""
    from glitchsat_byod import compose as CO
    orig = CO.compose

    def broken(*a, **kw):
        X = orig(*a, **kw)
        if kw.get('mode') == 'from_powerup':
            for y, (op, fi) in list(X.circ.gates.items()):
                if op == 'AND' and y in X.out_bits.get('open_o', []):
                    X.circ.gates[y] = ('OR', fi)
                    break
            else:
                b = X.out_bits['open_o'][0]
                X.circ.gates[b] = ('NOT', X.circ.gates[b][1][:1]) if b in X.circ.gates else X.circ.gates.get(b)
        return X
    monkeypatch.setattr(CO, 'compose', broken)
    src = os.path.join(os.path.dirname(DESIGNS), '..', 'examples', 'hello_lock', 'rtl', 'hello_lock.v')
    p = project('''
        glitchsat: 1
        design: {sources: [%s], top: hello_lock}
        clock: clk
        reset: {port: rst_n, active: low}
        checks: [{id: c, bad: "open_o"}]
        faults: {max_faults: 1, horizon: 4}
        analyses: [validate]
        ''' % 'hello_lock.v', files={'hello_lock.v': open(src).read()})
    with pytest.raises(GSError) as e:
        run_project(p)
    assert e.value.code == 'GS050'


@pytest.mark.skipif(not have_lib('sky130hd'), reason='sky130 not fetched')
def test_sky130_scan_flop_risk_reported(project, tmp_path):
    """A netlist with a sky130 scan flop: the scan-enable is tied by the user, the risk is reported."""
    nl = '''
    module scan1(input clk, input d, input si, input se, output q);
      sky130_fd_sc_hd__sdfxtp_1 u_ff (.CLK(clk), .D(d), .SCD(si), .SCE(se), .Q(q));
    endmodule
    '''
    p = project('''
        glitchsat: 1
        design: {sources: [scan1.v], top: scan1, frontend: netlist, liberty: [$GLITCHSAT_LIBS/sky130hd/sky130_fd_sc_hd__tt_025C_1v80.lib]}
        clock: clk
        reset: none
        powerup: zero
        inputs: {fixed: {se: 0, si: 0}}
        checks: [{id: c, bad: "q && !$past(d)"}]
        faults: {max_faults: 1, horizon: 3}
        analyses: [validate, min_faults]
        ''', files={'scan1.v': nl})
    rep, _ = run_project(p)
    assert any('scan' in r for r in rep['flows']['netlist']['risks'])
    assert rep['flows']['netlist']['cells_checked']['sky130_fd_sc_hd__sdfxtp_1'] == 16
    assert rep['checks'][0]['flows']['netlist']['validation']['mismatch'] is None
    assert rep['checks'][0]['analyses']['min_faults']['min_faults'] == 1


@pytest.mark.skipif(not all(have_lib(n) for n in ('nangate45', 'sky130hd', 'ihp-sg13g2', 'gf180mcu')), reason='libraries not fetched')
def test_four_standard_cell_flows(project):
    """The same RTL mapped to Nangate45, sky130, IHP SG13G2 and GF180MCU cells: every mapped netlist matches the RTL in
    simulation, and the survival table shows that `synth -flatten` merges the three checks in every library."""
    src = os.path.join(os.path.dirname(DESIGNS), '..', 'examples', 'hello_lock', 'rtl', 'hello_lock_hardened.v')
    p = project('''
        glitchsat: 1
        design: {sources: [%s], top: hello_lock_hardened}
        clock: clk
        reset: {port: rst_n, active: low}
        inputs: {attacker: [code_i, try_i]}
        checks: [{id: c, bad: "open_o == 3'b111", must_hold: ["!(try_i && code_i == 8'hA5)"]}]
        faults: {max_faults: 2, horizon: 6}
        flows: [plain, nangate45, sky130hd, ihp-sg13g2, gf180mcu]
        analyses: [validate, min_faults, survival]
        ''' % src)
    rep, _ = run_project(p)
    c = rep['checks'][0]
    rows = {r['flow']: r for r in c['analyses']['survival']['rows']}
    assert rows['plain']['verdict'] == 'NO_ATTACK_UP_TO_BOUND'
    for fl in ('nangate45', 'sky130hd', 'ihp-sg13g2', 'gf180mcu'):
        assert c['flows'][fl]['validation']['mismatch'] is None
        assert rows[fl]['min_faults'] == 1 and 'WEAKER' in rows[fl]['change']
        assert rep['flows'][fl]['cells_checked']


def test_second_clock_is_refused(project):
    e = code_of(mk(project, 'two_clocks.v', 'two_clocks', 'qa && qb', 'clock: clk_a\nreset: none\npowerup: zero'))
    assert e.code == 'GS013' and 'clk_a' in e.msg
