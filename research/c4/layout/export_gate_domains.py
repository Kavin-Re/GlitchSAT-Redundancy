#!/usr/bin/env python3
"""Writes domains_<d>_gates.json: the same domain families as domains_<d>.json but as groups of
B3-engine objects: gates0 = list of netlist cell names (primitive '<cell>::k' whose output net is the placed cell's OUTPUT pin net) and
d0_flops = list of flop cell names (their Q net ids are the engine's d0 sites). Feed: bp.Event(name, gates0={net ids}, d0={Q ids}) with
net ids from nl.drivers (see run_domains.py ev())."""
import json, sys
sys.path.insert(0, '/tmp/work_layout')
import faultpack as fp
for d in sys.argv[1:] or ['v1', 'v2', 'v2_wi']:
    nl = fp.Netlist(f'/tmp/work_layout/nl/{d}_layout.json', d)
    dom = json.load(open(f'domains_{d}.json'))
    out_prim, flops = {}, set(c for c, _, _ in nl.dffs)
    for y, (cn, t, con) in nl.drivers.items():
        if y in nl.names: out_prim.setdefault(cn.split('::')[0], []).append(cn)
    fams = {}
    for f, groups in dom['families'].items():
        fams[f] = {g: dict(gates0=sorted(p for c in cs for p in out_prim.get(c, [])), d0_flops=sorted(c for c in cs if c in flops)) for g, cs in groups.items()}
    json.dump(dict(design=d, label='Derived from domains_%s.json (MEASURED placement; strap/tap families INFERRED). Netlist: nl/%s_layout.json (decomposition of out_patched/%s_pnr.v)' % (d, d, d.split('_')[0]),
                   n_out_prims=sum(len(v) for v in out_prim.values()), families=fams), open(f'domains_{d}_gates.json', 'w'), indent=1)
    print(d, 'ok')
