#!/usr/bin/env python3
"""Dump SYNFI's own extracted target graph (fi_injector.extract_graph, unmodified) as JSON: nodes with
parent cell, type, stage, and edges with ports/pins. Reference for GlitchSAT's region extraction tests."""
import json, os, sys, pickle, importlib.util
REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REAL, 'shims'), os.path.join(REAL, 'synfi')]
import fi_injector

def main(pickle_path, spec_path, out):
    spec = json.load(open(spec_path))
    name, fm = next(iter(spec['fimodels'].items()))
    cl = fi_injector.load_cell_lib_module(type('A', (), {'cell_lib_path': os.path.join(REAL, 'synfi', 'cell_lib_nangate45_autogen.py')}))
    g = fi_injector.read_circuit(pickle_path)
    tg = fi_injector.extract_graph(g, fm, cl, 1, False)
    nodes = {n: dict(parent=d['node'].parent_name, type=d['node'].type, stage=d['node'].stage) for n, d in tg.nodes(data=True)}
    edges = [dict(src=u, dst=v, out_port=d['edge'].out_port, out_pin=d['edge'].out_pin, in_port=d['edge'].in_port,
                  in_pin=d['edge'].in_pin, wire=d['edge'].wire) for u, v, d in tg.edges(data=True)]
    json.dump(dict(model=name, nodes=nodes, edges=edges), open(out, 'w'), indent=1)
    import collections
    print(out, len(nodes), 'nodes', collections.Counter((v['type'] if v['type'] in ('input','output','in_node','out_node') else 'cell', v['stage']) for v in nodes.values()))

if __name__ == '__main__':
    main(*sys.argv[1:4])
