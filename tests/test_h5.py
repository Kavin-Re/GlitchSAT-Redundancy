"""glitchsat.Netlist skips $scopeinfo (Yosys >= 0.38) and gives the same verdict; unknown cells still error."""
import copy, json, os, sys
import pytest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import glitchsat as g

SRC = os.path.join(ROOT, 'reference/spike_netlists/v2.json')

def _w(tmp_path, doc, n):
    p = tmp_path / n; p.write_text(json.dumps(doc)); return str(p)

def test_scopeinfo_same_verdict(tmp_path):
    doc = json.load(open(SRC)); d2 = copy.deepcopy(doc)
    d2['modules']['v2']['cells']['c0'] = {'type': '$scopeinfo', 'parameters': {'TYPE': 'module'}, 'attributes': {}, 'port_directions': {}, 'connections': {}}
    a = g.Netlist(_w(tmp_path, doc, 'a.json'), 'v2'); b = g.Netlist(_w(tmp_path, d2, 'b.json'), 'v2')
    assert a.stats() == b.stats()
    assert g.solve(a, 6, 2)[0] == g.solve(b, 6, 2)[0] == 'NO_ATTACK_UP_TO_BOUND'

def test_unknown_cell_still_errors(tmp_path):
    doc = json.load(open(SRC))
    doc['modules']['v2']['cells']['zz'] = {'type': '$mystery', 'port_directions': {}, 'connections': {}}
    with pytest.raises(g.NetlistError):
        g.Netlist(_w(tmp_path, doc, 'c.json'), 'v2')

def test_scopeinfo_with_output_not_ignored(tmp_path):
    doc = json.load(open(SRC))
    doc['modules']['v2']['cells']['zz'] = {'type': '$scopeinfo', 'port_directions': {'Q': 'output'}, 'connections': {'Q': [99999]}}
    with pytest.raises(g.NetlistError):
        g.Netlist(_w(tmp_path, doc, 'd.json'), 'v2')
