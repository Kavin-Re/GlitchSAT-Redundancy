"""Every injection SYNFI made (results/synfi_reference) gets the same verdict from GlitchSAT's model."""
import json, os
import pytest
from conftest import REAL, load, spec
from glitchsat_real import synfi_model as sm

RUNS = [('E1', 'aes_fsm_fe_s1', True), ('E2', 'aes_fsm_fs_s1', True), ('E2', 'aes_fsm_fs_s2', True),
        ('E3', 'aes_ctrl_fd_s1', True), ('E3', 'aes_ctrl_fd_s2_fl', False), ('E3', 'aes_ctrl_fd_s2_l2000', True),
        ('E4', 'ibex_pc_fe_s1', True), ('E5', 'ibex_pc_fs_s1', True), ('E5', 'ibex_pc_fs_s2_l2000', True)]
_cache = {}


@pytest.mark.parametrize('eid,run,auto', RUNS)
def test_agreement(eid, run, auto, lib):
    p = os.path.join(REAL, 'results', 'synfi_reference', run + '.json')
    if not os.path.exists(p):
        pytest.skip('reference run missing: scripts/run_all_synfi_reference.sh')
    ref = json.load(open(p))
    net, fm = spec(eid)
    key = (eid, auto)
    if key not in _cache:
        doc, top = load(net)
        _cache[key] = sm.Model(doc, top, fm, lib=lib, auto_fl=auto)
    m = _cache[key]
    bad = [r for r in ref['results'] if m.check([(f['location'], f['mapping']) for f in r['faults']]) != r['sat']]
    assert not bad, bad[:3]
    if auto and ref['simultaneous_faults'] == 1:
        assert {f['location'] for r in ref['results'] for f in r['faults']} == set(m.locs)
