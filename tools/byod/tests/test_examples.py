"""The gallery: every example and variant gives the stored result (verdict and minimum number of faults), and the
analysed netlist matches the RTL in simulation. Full runs (all analyses): scripts/run_examples.py."""
import json
import os

import pytest

from conftest import EXAMPLES, needs_yosys, have_lib, copy_example
from glitchsat_byod.run import run_project
from glitchsat_byod.flows import find_yosys
from glitchsat_byod.errors import GSError

CASES = []
for name in sorted(os.listdir(EXAMPLES)):
    p = os.path.join(EXAMPLES, name, 'expected_results.json')
    if os.path.isfile(p):
        for key, v in json.load(open(p)).items():
            f, _, task = key.partition(' --task ')
            CASES.append((name, f, task or None, v))


def _can_run(name):
    if name == 'sky130_lock' and not have_lib('sky130hd'):
        return 'sky130 library not fetched'
    if name == 'opentitan_count':
        if not os.path.isfile(os.path.join(EXAMPLES, name, 'ot', 'prim_count.sv')):
            return 'OpenTitan sources not fetched (sh fetch_ot.sh)'
        try:
            find_yosys(need_slang=True)
        except GSError:
            return 'no Yosys with read_slang'
    return None


@needs_yosys
@pytest.mark.parametrize('name,f,task,exp', CASES, ids=['%s:%s:%s' % (c[0], c[1], c[2]) for c in CASES])
def test_example(name, f, task, exp, tmp_path):
    why = _can_run(name)
    if why:
        pytest.skip(why)
    rep, _ = run_project(os.path.join(copy_example(name, tmp_path), f), task, only=['validate', 'min_faults', 'survival'], quick=True)
    for c in rep['checks']:
        e = exp['checks'][c['id']]
        mf = c['analyses']['min_faults']
        assert (mf['verdict'], mf.get('min_faults')) == (e['verdict'], e['min_faults'])
        for fl, x in c['flows'].items():
            assert x['validation']['mismatch'] is None
        if 'survival' in e:
            got = {r['flow']: r.get('min_faults') if r.get('min_faults') is not None else r['verdict'] for r in c['analyses']['survival']['rows']}
            assert got == e['survival']
