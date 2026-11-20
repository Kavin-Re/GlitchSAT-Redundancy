#!/usr/bin/env python3
"""RUN2 adapter (own code): add a constant-1 'alert' output (NOT of const 0) to a Yosys JSON gate netlist so
that k-FRP, which requires an alert signal, can read it. Usage: addalert.py in.json top out.json"""
import json, sys
src, top, out = sys.argv[1:4]
d = json.load(open(src)); m = d['modules'][top]
nb = max(x for p in m['ports'].values() for x in p['bits'] if isinstance(x, int))
for c in m['cells'].values():
    for p in c['connections'].values():
        for x in p:
            if isinstance(x, int): nb = max(nb, x)
nb += 1
m['cells']['alert_const'] = {'hide_name': 0, 'type': '$_NOT_', 'parameters': {}, 'attributes': {},
    'port_directions': {'A': 'input', 'Y': 'output'}, 'connections': {'A': ['0'], 'Y': [nb]}}
m['ports']['alert'] = {'direction': 'output', 'bits': [nb]}
m['netnames']['alert'] = {'hide_name': 0, 'bits': [nb], 'attributes': {}}
json.dump(d, open(out, 'w'), indent=1)
