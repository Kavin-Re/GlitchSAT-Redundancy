"""Checks added with the second independent review (REVIEW_2_FIXES.md): a run without an answer is never reported as
"nothing to fix", and "what the attacker gets" comes from the check's goal, not from its wording."""
import json
import os
import subprocess
import sys

import pytest
import yaml

from conftest import PKG, needs_yosys
from glitchsat_byod import templates as TPL
from glitchsat_byod.report import plain_findings_module

GS = os.path.join(PKG, 'glitchsat')


@needs_yosys
def test_inconclusive_run_exits_2_and_says_no_answer(example):
    """hello_lock with a must-hold condition that can never be true: the engine answers VACUOUS (GS052), exit 2.
    The plain summary must say there is no answer, never "nothing to fix" or "computed exactly"."""
    if plain_findings_module() is None:
        pytest.skip('findings module not found next to this folder')
    d = example('hello_lock')
    p = os.path.join(d, 'glitchsat.yaml')
    doc = yaml.safe_load(open(p))
    doc['checks'][0]['must_hold'] = ["1'b0"]
    yaml.safe_dump(doc, open(p, 'w'), sort_keys=False)
    r = subprocess.run([sys.executable, GS, 'run', 'glitchsat.yaml', '--quick'], cwd=d, capture_output=True, text=True, timeout=300)
    assert r.returncode == 2, (r.returncode, r.stdout[-2000:], r.stderr[-2000:])
    head = r.stdout.split('Technical details')[0]
    assert 'What we found and what it means' in head
    assert 'no answer' in head and 'not a pass' in head and 'We could not get an answer' in head, head
    assert 'nothing to fix' not in head.lower() and 'computed exactly' not in head.lower(), head
    assert '[? UNKNOWN' in head and 'INFO]' not in head and 'LOW]' not in head
    rep = json.load(open(os.path.join(d, '.glitchsat', 'default', 'report.json')))
    f = rep['plain_findings'][0]
    assert f['severity']['level'] == 'Unknown' and f['severity']['words'].startswith('Unknown')
    assert 'must-hold' in f['statement'] and f['severity']['no_answer']['try_next']


def test_every_template_has_a_goal_and_the_snippets_state_it():
    here = PKG
    tdir = os.path.join(here, 'templates')
    for t in TPL.NAMES:
        if t != 'custom':
            assert TPL.GOAL[t] in TPL.GOALS, t
        y = yaml.safe_load(open(os.path.join(tdir, t + '.yaml')))
        assert y['checks'][0].get('goal') in TPL.GOALS, t
    sch = json.load(open(os.path.join(here, 'schema', 'glitchsat.schema.json')))
    assert set(sch['$defs']['check']['properties']['goal']['enum']) == set(TPL.GOALS)


def test_project_carries_the_goal_and_rejects_an_unknown_one(tmp_path):
    from glitchsat_byod.project import load
    from glitchsat_byod.errors import GSError
    v = tmp_path / 'a.v'
    v.write_text('module a(input clk, input rst, output reg o); always @(posedge clk) o <= rst; endmodule\n')
    base = dict(glitchsat=1, name='a', design=dict(sources=['a.v'], top='a'), clock='clk', reset=dict(port='rst', active='high'),
                checks=[dict(id='c1', bad='o', goal='key_leak'), dict(id='c2', template='secure_boot_wrong_key',
                                                                        params=dict(accept='o', key_input='rst', good_key="1'b0"))])
    p = tmp_path / 'glitchsat.yaml'
    p.write_text(yaml.safe_dump(base))
    spec, _ = load(str(p))
    g = {c['id']: (c['goal'], c['goal_source']) for c in spec['checks']}
    assert g == {'c1': ('key_leak', 'stated'), 'c2': ('boot_accept', 'template')}
    base['checks'][0]['goal'] = 'world_domination'
    p.write_text(yaml.safe_dump(base))
    with pytest.raises(GSError):
        load(str(p))
