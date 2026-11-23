"""Plain-words findings: patterns (a)-(d) on small examples, the seven parts of every finding, severity rules,
honesty, wording, SARIF and the real result files of the modules."""
import importlib.util
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
EXT = os.path.dirname(MOD)
sys.path.insert(0, MOD)
import plain_findings as PF  # noqa: E402

PARTS = ('severity', 'statement', 'why', 'where', 'sure', 'next', 'how')


def complete(f):
    """Every finding has the seven parts, each filled (or saying honestly what is missing)."""
    assert all(k in f for k in PARTS), [k for k in PARTS if k not in f]
    s = f['severity']
    assert s['level'] in PF.LEVELS and s['icon'] and s['rationale'] and s['urgency'] and 'estimate' in s['estimate_note']
    assert f['statement'] and f['why']['title'] and f['why']['text'] and f['why']['detected'] in ('yes', 'likely')
    assert f['where']['text'] and (f['where']['available'] or f['where'].get('missing_note') or 'nothing' in f['where']['text']
                                   or 'ordinary use' in f['where']['text'])
    assert f['sure']['label'] and f['sure']['plain']
    assert f['next']['fixes'] and f['next']['check_cmd']
    h = f['how']
    assert len(h['steps']) == 6 and h['spot_next'] and h['replay']
    assert h['trace'] or h['trace_note']            # a real trace, or an honest note that none is stored
    assert [p['tag'] for p in f['patterns']] == ['(a)', '(b)', '(c)', '(d)']
    return True


def byod_check(**kw):
    c = dict(id='c', bad='open_o', explain='The lock opens without the code', must_hold=['!(try_i && code_i == 8\'hA5)'],
             horizon=6, max_faults=3, goal='lock_bypass', what_to_do=[],
             analyses=dict(min_faults=dict(verdict='ATTACK_FOUND', min_faults=1, proved_minimum=True,
                                           witness=dict(faults=[dict(cycle=2, site='open_q (flip-flop stored value)', type='flip',
                                                                     src='lock.v:12')], inputs={'code_i': {'values': ['0x00']}},
                                                        hit_cycle=3, replayed=True))))
    for k, v in kw.items():
        c['analyses'][k] = v
    return c


# ---------------------------------------------------------------------------------------------- patterns

def test_pattern_d_single_point_and_critical_boot_bypass():
    f = PF.from_byod_check(byod_check(), {})
    assert complete(f)
    assert f['why']['id'] == 'single_point' and f['severity']['level'] == 'Critical'
    assert f['where']['file'] == 'lock.v' and f['where']['line'] == 12 and f['where']['cycle'] == 2
    assert f['how']['replay']['replayed'] is True and 'glitchsat run' in f['next']['check_cmd']


def test_pattern_a_removed_redundancy_in_the_build():
    c = byod_check()
    c['analyses']['min_faults']['min_faults'] = 3
    c['analyses']['survival'] = dict(rows=[dict(flow='plain', min_faults=3), dict(flow='synth', min_faults=1)])
    c['analyses']['merge_lint'] = dict(countermeasures=[dict(title='3 copies of cmp', stages=[
        dict(stage='plain', verdict='SURVIVED'), dict(stage='synth', verdict='REMOVED')])])
    f = PF.from_byod_check(c, {})
    assert complete(f) and f['why']['id'] == 'removed_redundancy'
    assert f['severity']['level'] == 'Critical'          # the weakest build (1 glitch) and a removed protection
    assert 'synth' in f['statement'] and any('keep_hierarchy' in x for x in f['next']['fixes'])
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert st['(a)'].startswith('yes')


def test_pattern_a_compiler_removed_a_check_and_b_aliasing_and_d_branch():
    fw = dict(model_text={'skip': 'instruction skip', 'brinv': 'branch inversion'},
              cells=[dict(variant='rom_x', opt='O0', mode='plain', tampered='2', witness=[]),
                     dict(variant='rom_x', opt='O2', mode='plain', tampered='1',
                          witness=[dict(model='brinv', pc='0x10', file='rom_x.c', line=7, asm='c.beqz a2, 0x20', effect='branch inverted')]),
                     dict(variant='rom_y', opt='O2', mode='plain', tampered='1',
                          witness=[dict(model='skip', pc='0x40', file='rom_y.c', line=9, asm='lw\ta0, -0x10(s0)', effect='instruction skipped')])],
              redundancy=[dict(variant='rom_x', opt='O0', mode='plain', mac_compares=2), dict(variant='rom_x', opt='O2', mode='plain', mac_compares=1),
                          dict(variant='rom_y', opt='O0', mode='plain', mac_compares=1), dict(variant='rom_y', opt='O2', mode='plain', mac_compares=1)])
    fs = {f['tech']['variant']: f for f in PF.from_firmware(fw)}
    assert all(complete(f) for f in fs.values())
    x = {p['tag']: p['status'] for p in fs['rom_x']['patterns']}
    assert fs['rom_x']['why']['id'] == 'removed_redundancy' and x['(a)'].startswith('yes') and x['(d)'].startswith('yes')
    y = fs['rom_y']
    assert y['why']['id'] == 'aliasing' and y['why']['detected'] == 'likely' and 'cannot be confirmed' in y['why']['evidence']
    assert y['where']['line'] == 9 and 'lw a0' in y['where']['instruction']


def test_pattern_c_delay_only_and_honest_when_unknown():
    base = dict(model_text={'skip': 'instruction skip'}, redundancy=[],
                cells=[dict(variant='rom_delay', opt='O0', mode='plain', tampered='1',
                            witness=[dict(model='skip', pc='0x1', file='d.c', line=3, asm='c.li a0, 0', effect='instruction skipped')])])
    yes = dict(base, random_delay=dict(seeds=8, rows=[dict(build='rom_delay-O0-plain-hw', seeds_with_any_single_skip=8)]))
    f = PF.from_firmware(yes, opt='O0')[0]
    assert complete(f) and f['why']['id'] == 'delay_only' and 'sampled' in ' '.join(f['severity']['rationale']) and f['sure']['label'] == 'SAMPLED'
    unknown = PF.from_firmware(base, opt='O0')[0]
    c = {p['tag']: p['status'] for p in unknown['patterns']}
    assert c['(c)'].startswith('cannot tell')          # no random-delay runs: say so instead of guessing


def test_hardware_says_which_patterns_do_not_apply():
    f = PF.from_byod_check(byod_check(), {})
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert st['(b)'].startswith('does not apply') and st['(c)'].startswith('does not apply')


# ---------------------------------------------------------------------------------------------- severity

def test_severity_rules():
    assert PF.severity(1, 'boot')['level'] == 'Critical'
    alarm3 = PF.severity(3, 'alarm')
    assert PF.LEVELS.index(alarm3['level']) < PF.LEVELS.index('High')
    assert PF.severity(None, 'boot')['level'] == 'Info'
    assert PF.severity(2, 'boot', 'removed')['level'] == 'Critical'
    s = PF.severity(1, 'boot', label='SAMPLED')
    assert any('might be worse or better' in r for r in s['rationale'])
    for lv in PF.LEVELS:                                   # colour is never the only signal: a word and an icon too
        assert PF.ICON[lv] and lv in PF.URGENCY
    assert PF.severity(1, 'key')['comparison']['lesson'] == 6
    assert PF.severity(3, 'alarm')['comparison'] is None   # no honest comparison: none is invented
    assert 'CVSS' not in json.dumps(PF.severity(1, 'boot'))


def test_summary_line():
    a = PF.from_byod_check(byod_check(), {})
    b = PF.from_byod_check(dict(byod_check(), goal='alarm_suppress',
                                analyses=dict(min_faults=dict(verdict='NO_ATTACK_UP_TO_BOUND'))), {})
    line = PF.summary_line([b, a])
    assert line.startswith('1 critical, 1 info') and 'Start with the critical one' in line


# ---------------------------------------------------------------------------------------------- real data

def test_real_module_results_give_complete_findings():
    n = 0
    p = os.path.join(EXT, 'soc', 'studio', 'explore_chip.json')
    if os.path.isfile(p):
        for c in json.load(open(p))['chips']:
            for f in PF.from_soc_chip(c):
                assert complete(f) and f['sure']['label'] == 'BOUNDED'
                n += 1
    p = os.path.join(EXT, 'firmware', 'results', 'studio_firmware.json')
    if os.path.isfile(p):
        d = json.load(open(p))
        for opt in d['opts']:
            for f in PF.from_firmware(d, opt=opt):
                assert complete(f)
                n += 1
        found_c = [f for f in PF.from_firmware(d, opt='O0') if f['why']['id'] == 'delay_only']
        assert found_c, 'the stored random-delay runs show pattern (c) at -O0'
    for root, _, files in os.walk(os.path.join(EXT, 'byod', 'examples')):
        for fn in files:
            if root.endswith('saved') and fn.endswith('.report.json'):
                for f in PF.from_byod_report(json.load(open(os.path.join(root, fn)))):
                    assert complete(f)
                    n += 1
    if not n:
        pytest.skip('no module results here')


def test_text_sarif_and_wording():
    fs = [PF.from_byod_check(byod_check(), {})]
    t = PF.to_text(fs)
    assert t.splitlines()[2].startswith('1 critical') and 'How we found it' in t and 'Spot it next time' in t
    s = PF.to_sarif(fs)
    r = s['runs'][0]['results'][0]
    assert r['level'] == 'error' and r['message']['text'].startswith('[Critical]')
    assert len(r['codeFlows'][0]['threadFlows'][0]['locations']) == 6 and r['locations'][0]['physicalLocation']['region']['startLine'] == 12
    spec = importlib.util.spec_from_file_location('check_wording', os.path.join(EXT, 'check_wording.py'))
    cw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cw)
    assert not cw.scan_text(t + json.dumps(s) + PF.severity_doc())
    assert not cw.scan([MOD])


def _code_flow_locations(sarif):
    for r in sarif['runs'][0]['results']:
        for cf in r.get('codeFlows', []):
            for tf in cf['threadFlows']:
                for tl in tf['locations']:
                    yield r, tl


def test_sarif_code_flow_steps_have_a_file_location():
    """GitHub code scanning rejects a code flow step without a physical location ("expected physical location"):
    every threadFlowLocation carries artifactLocation.uri and a region; a finding without a file has no code flow."""
    with_file = PF.from_byod_check(byod_check(), {})
    no_file = json.loads(json.dumps(with_file))
    no_file['where']['file'] = None
    s = PF.to_sarif([with_file, no_file])
    a, b = s['runs'][0]['results']
    assert len(a['codeFlows'][0]['threadFlows'][0]['locations']) == len(with_file['how']['steps'])
    assert 'codeFlows' not in b and 'locations' not in b and b['properties']['how_steps'] == no_file['how']['steps']
    n = 0
    for r, tl in _code_flow_locations(s):
        pl = tl['location']['physicalLocation']
        assert pl['artifactLocation']['uri'] and pl['region']['startLine'] >= 1, tl
        assert tl['location']['message']['text']
        n += 1
    assert n == len(with_file['how']['steps'])
    schema = os.environ.get('GLITCHSAT_SARIF_SCHEMA')    # optional: the full OASIS SARIF 2.1.0 schema file
    if schema and os.path.isfile(schema):
        jsonschema = pytest.importorskip('jsonschema')
        jsonschema.validate(s, json.load(open(schema)))


def test_reading_level_is_plain():
    """Statements, real-life lines and pattern texts: short sentences (grade 6-8 target: about 20 words or fewer)."""
    texts = [p['text'] for p in PF.PATTERNS.values()] + list(PF.URGENCY.values()) + list(PF.WHO.values())
    for t in texts:
        for sent in [x for x in t.replace('!', '.').split('. ') if x.strip()]:
            assert len(sent.split()) <= 32, sent


# ---------------------------------------------------------------------------------------------- review 2 regressions

def _no_answer_ok(f):
    s = f['severity']
    assert s['level'] == PF.UNKNOWN and s['level'] not in ('Info', 'Low') and s['words'].startswith('Unknown')
    assert f['statement'].startswith('We could not get an answer') and s['no_answer']['try_next']
    assert f['why']['id'] == 'no_answer' and f['sure']['label'] == 'NO_ANSWER'
    assert len(f['how']['steps']) == 6 and f['next']['fixes'] and f['next']['check_cmd']
    t = PF.to_text([f])
    assert 'nothing to fix' not in t.lower() and 'computed exactly' not in t.lower(), t
    assert 'UNKNOWN' in t and PF.to_sarif([f])['runs'][0]['results'][0]['level'] == 'warning'
    return True


@pytest.mark.parametrize('verdict', ['VACUOUS', 'UNDECIDED', 'NOT_RUN', 'UNKNOWN', 'TIMEOUT', None, 'SOMETHING_NEW'])
def test_b1_inconclusive_runs_are_never_an_all_clear(verdict):
    c = byod_check()
    c['analyses']['min_faults'] = dict(verdict=verdict, why='GS052: the must-hold conditions can never all be true')
    f = PF.from_byod_check(c, {})
    assert _no_answer_ok(f)
    line = PF.summary_line([f])
    assert 'no answer' in line and 'not a pass' in line and 'nothing to fix' not in line
    # next to a real "none found" it still leads, and is counted on its own
    none = PF.from_byod_check(dict(byod_check(), analyses=dict(min_faults=dict(verdict='NO_ATTACK_UP_TO_BOUND'))), {})
    line = PF.summary_line([none, f])
    assert line.startswith('1 info, 1 with no answer') and 'nothing to fix' not in line


def test_b1_check_not_run_and_studio_timeout():
    f = PF.from_byod_check(dict(id='x', status='NOT_RUN', why='the masking analysis is not part of this release'), {})
    assert _no_answer_ok(f) and 'masking' in f['severity']['no_answer']['why']
    r = dict(verdict='UNKNOWN_TIMEOUT', _k=3, _cycles=6, _stop=dict(why='timeout'), _prov=dict(cli='python3 scripts/glitchsat.py check a.json --top t --k 3 --cycles 6'))
    f = PF.from_studio_result(r, dict(design='v2', goal='word'))[0]
    assert _no_answer_ok(f) and 'ran out of time' in f['statement'] and f['next']['check_cmd'].endswith('--cycles 6')


def test_b2_gain_comes_from_metadata_and_guesses_use_whole_words():
    assert PF.guess_gain('clock_div_ok', 'clk_div != 3') is None             # "clock" is not "lock"
    assert PF.guess_gain('stage_skip', 'stage == 2') is None                  # "stage" is not "tag"
    assert PF.guess_gain('decode_err', 'decode_o') is None                    # "decode" is not "code"; "err" is no alarm
    assert PF.guess_gain('open_without_code', 'open_o') == 'unlock'
    assert PF.guess_gain('x', 'lock_open && !key_ok') in ('key', 'unlock')
    stated = byod_check(); stated['goal'] = 'crash_only'; stated['id'] = 'leak_key'
    assert PF.gain_for_check(stated) == ('crash', 'stated')                    # an explicit goal always wins
    tpl = dict(id='accept_wrong_tag', template='secure_boot_wrong_key', bad='x')
    assert PF.gain_for_check(tpl) == ('boot', 'template')
    clk = dict(byod_check(), id='clock_divider_glitch', bad='clk_div_o != 3', explain='The clock divider skips a value')
    clk.pop('goal')
    f = PF.from_byod_check(clk, {})
    s = f['severity']
    assert s['gain'] is None and s['comparison'] is None and s['level'] == 'High'
    assert 'lock' not in ' '.join(s['rationale']).replace('clock', '')
    g = dict(byod_check(), id='open_without_code'); g.pop('goal')
    f = PF.from_byod_check(g, {})
    assert f['severity']['gain_source'] == 'guessed' and 'please confirm' in ' '.join(f['severity']['rationale'])
    assert f['severity']['comparison'] is None                                # no real-world story on a guess


SAVED = os.path.join(EXT, 'byod', 'examples')


def _saved(name, fn):
    p = os.path.join(SAVED, name, 'saved', fn)
    if not os.path.isfile(p):
        pytest.skip('gallery not here')
    return PF.from_byod_report(json.load(open(p)))


def test_b2_b3_gallery_secure_boot():
    f = _saved('secure_boot', 'glitchsat.report.json')[0]
    s = f['severity']
    txt = json.dumps(f)
    assert s['gain'] == 'boot' and 'Trezor' not in txt and 'secret key' not in txt
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert not st['(a)'].startswith('yes') and 'not built in this configuration' in st['(a)']
    assert f['why']['id'] == 'single_point' and 'says[0]' in f['where']['text'] and s['level'] == 'Critical'
    assert not any('removed by the build tool' in r for r in s['rationale'])


def test_b2_b3_gallery_opentitan_count_naive():
    f = _saved('opentitan_count', 'glitchsat.naive.report.json')[0]
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert not st['(a)'].startswith('yes') and 'not built in this configuration' in st['(a)']
    assert f['severity']['gain'] != 'alarm' and 'silence an alarm' not in json.dumps(f['severity'])
    assert not any('removed by the build tool' in r for r in f['severity']['rationale'])


def test_b3_gallery_hello_lock_hardened_still_yes():
    f = _saved('hello_lock', 'glitchsat_hardened.report.json')[0]
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert st['(a)'].startswith('yes') and f['why']['id'] == 'removed_redundancy'


@pytest.mark.parametrize('design', ['v2_rtl', 'v2e_rtl'])
def test_b3_studio_flag_goal_rebuilt(design):
    r = dict(verdict='ATTACK_FOUND', min_faults=1, _k=3, _cycles=6, _goal='flag', _src='live',
             faults=[dict(net='ok_q', plain='the open signal', cycle=4)],
             _ref=dict(design=design[:-4], goal='flag', verdict='ATTACK_FOUND', min=1),
             _prov=dict(cli='python3 scripts/glitchsat.py check x.v --top t --k 3 --cycles 6 --flow synth --goal-out boot_ok --goal-value 1'))
    f = PF.from_studio_result(r, dict(design=design, goal='flag'))[0]
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert not st['(a)'].startswith('yes') and f['why']['id'] == 'single_point'
    assert 'accept a wrong key' not in f['statement'] and 'stays shut' in f['statement']
    assert '--design' not in f['next']['check_cmd'] and '--top' in f['next']['check_cmd'] and '--goal-out boot_ok' in f['next']['check_cmd']
    r['_goal'] = 'word'; r['_ref'] = dict(goal='word', verdict='ATTACK_FOUND', min=3)
    f = PF.from_studio_result(r, dict(design=design, goal='word'))[0]
    st = {p['tag']: p['status'] for p in f['patterns']}
    assert st['(a)'].startswith('maybe') and not any('removed by the build tool' in x for x in f['severity']['rationale'])


def test_b3_firmware_fractional_compare_count_is_no_evidence():
    p = os.path.join(EXT, 'firmware', 'results', 'studio_firmware.json')
    if not os.path.isfile(p):
        pytest.skip('firmware results not here')
    d = json.load(open(p))
    for v in ('rom_compl', 'rom_triple', 'rom_double'):
        for f in PF.from_firmware(d, variants=[v], opt='Os'):
            st = {x['tag']: x['status'] for x in f['patterns']}
            assert not st['(a)'].startswith('yes'), (v, st['(a)'])
            assert not any('removed by the build tool' in x for x in f['severity']['rationale'])
    f = PF.from_firmware(d, variants=['rom_compl'], opt='Os')[0]
    assert f['severity']['level'] == 'High'          # 2 faults at -Os; not raised to Critical
