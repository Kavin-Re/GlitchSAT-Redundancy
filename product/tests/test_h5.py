"""Yosys >= 0.38 emits $scopeinfo cells after flatten; they are hierarchy metadata and are skipped."""
import copy, json, os
import pytest
from faultbound_wt import _engine
from faultbound_wt.cli import example_dir

V2 = os.path.join(example_dir(), "v2.json")


def _write(tmp_path, doc, name):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return str(p)


def _doc():
    return json.load(open(V2))


def test_scopeinfo_is_skipped_same_netlist_stats(tmp_path):
    doc = _doc()
    top = next(iter(doc["modules"]))
    base = _engine.Netlist(_write(tmp_path, doc, "a.json"), top)
    d2 = copy.deepcopy(doc)
    d2["modules"][top]["cells"]["c0_scope"] = {"hide_name": 1, "type": "$scopeinfo", "parameters": {"TYPE": "module"},
                                                "attributes": {"hdlname": "x"}, "port_directions": {}, "connections": {}}
    with_si = _engine.Netlist(_write(tmp_path, d2, "b.json"), top)
    assert with_si.stats() == base.stats()
    assert with_si.drivers == base.drivers and with_si.dffs == base.dffs


def test_unknown_cell_type_still_errors(tmp_path):
    doc = _doc()
    top = next(iter(doc["modules"]))
    doc["modules"][top]["cells"]["zz"] = {"type": "$mystery", "port_directions": {}, "connections": {}}
    with pytest.raises(_engine.NetlistError):
        _engine.Netlist(_write(tmp_path, doc, "c.json"), top)


def test_scopeinfo_with_output_port_is_not_ignored(tmp_path):
    doc = _doc()
    top = next(iter(doc["modules"]))
    doc["modules"][top]["cells"]["zz"] = {"type": "$scopeinfo", "port_directions": {"Y": "output"}, "connections": {"Y": [9999]}}
    with pytest.raises(_engine.NetlistError):
        _engine.Netlist(_write(tmp_path, doc, "d.json"), top)
