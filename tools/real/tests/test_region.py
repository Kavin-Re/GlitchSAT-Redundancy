"""GlitchSAT's own region extraction == SYNFI's extracted target graph (stored node sets)."""
import json, os
import pytest
from conftest import REAL, spec, load
from glitchsat_real import region, synfi_model as sm

TG = json.load(open(os.path.join(REAL, 'tests', 'data', 'synfi_targets.json')))['targets']


@pytest.mark.parametrize('eid,key', [('E1', 'aes_fsm'), ('E3', 'aes_ctrl'), ('E4', 'ibex')])
def test_region_equals_synfi(eid, key, lib):
    net, fm = spec(eid)
    doc, top = load(net)
    g = region.CellGraph(doc, top)
    regs, _ = region.extract(g, fm)
    m = sm.Model(doc, top, fm, lib=lib)
    for st, ref in TG[key].items():
        mine = {x[3:] if x.startswith('in:') else x[4:] if x.startswith('out:') else x for x in regs[st]}
        ends_input = {p for p in fm['input_values']}
        assert mine == set(ref['nodes']) | (set(ref['side']) & ends_input & mine), st
        assert m.side_inputs[st] | (set(ref['side']) & ends_input) == set(ref['side']), st


@pytest.mark.parametrize('eid,ge', [('E1', 23.67), ('E3', 556.33), ('E4', 488.0)])
def test_target_size_equals_synfi_log(eid, ge, lib):
    net, fm = spec(eid)
    doc, top = load(net)
    assert sm.Model(doc, top, fm, lib=lib).region_ge() == ge
