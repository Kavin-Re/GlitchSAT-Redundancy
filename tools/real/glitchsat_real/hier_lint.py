"""Cell-ownership redundancy lint for flattened netlists that keep hierarchy prefixes in cell names.

Question: after synthesis, are the intended redundant instances (e.g. the three rails gen_fsm[0..2] of OpenTitan's
aes_cipher_control) still separate logic, or did an optimisation pass (opt_merge / ABC structural hashing) fold
cells of one instance into another?

Each Nangate cell gets an owner from its name (regex with one group, default r'gen_fsm\\[(\\d+)\\]'); cells without
a match are 'top'. Reported, structurally (no solver):
  cross_copy_reads : nets driven by a cell of copy A and read by a cell of copy B != A. A merge by synthesis shows up
                     here (the surviving cell keeps one instance's name, the other instance reads it).
  shared_drivers   : 'top' cells (and input ports) read by two or more copies. Logic in front of the copies; this
                     can be intended (inputs that the RTL does not replicate) or a merge into the parent.
  copies           : cells and flops per copy, and a structural signature (sorted cell-type histogram) per copy;
                     equal signatures mean the copies are replicas that still exist as separate cells.
This complements ext/surface merge_lint.py, whose copy cones include all upstream logic and therefore count
intended shared inputs as shared nets.
"""
import collections
import re

from . import nangate as ng


def lint(doc, top, copy_regex=r'gen_fsm\[(\d+)\]'):
    m = doc['modules'][top]
    rx = re.compile(copy_regex)
    owner = {}
    for cn in m['cells']:
        mm = rx.search(cn)
        owner[cn] = mm.group(1) if mm else 'top'
    drv, readers = {}, collections.defaultdict(set)
    for p, x in m['ports'].items():
        if x['direction'] == 'input':
            for b in x['bits']:
                if isinstance(b, int):
                    drv[b] = ('port', p)
    for cn, c in m['cells'].items():
        if c['type'] in ng.NO_LOGIC:
            continue
        for pin, d in c['port_directions'].items():
            for b in c['connections'].get(pin, []):
                if not isinstance(b, int):
                    continue
                if d == 'output':
                    drv[b] = ('cell', cn)
                elif pin != ng.CLOCK_PIN:
                    readers[b].add(cn)
    cross, shared = [], []
    for b, rs in readers.items():
        if b not in drv:
            continue
        kind, src = drv[b]
        ro = {owner[r] for r in rs} - {'top'}
        so = owner.get(src, 'top') if kind == 'cell' else 'port'
        if so not in ('top', 'port'):
            others = ro - {so}
            if others:
                cross.append(dict(net=b, driver=src, driver_copy=so, reader_copies=sorted(others)))
        elif len(ro) >= 2:
            shared.append(dict(net=b, driver=src, kind=kind,
                               driver_type=m['cells'][src]['type'] if kind == 'cell' else 'input port',
                               reader_copies=sorted(ro)))
    copies = collections.defaultdict(lambda: dict(cells=0, flops=0, types=collections.Counter()))
    for cn, c in m['cells'].items():
        o = owner[cn]
        if o == 'top':
            continue
        copies[o]['cells'] += 1
        copies[o]['flops'] += c['type'] in ng.FLOP_PINS
        copies[o]['types'][c['type']] += 1
    sig = {o: tuple(sorted(v['types'].items())) for o, v in copies.items()}
    groups = collections.defaultdict(list)
    for o, s_ in sig.items():
        groups[s_].append(o)
    shared_cells = sorted({s['driver'] for s in shared if s['kind'] == 'cell'})
    shared_ports = sorted({s['driver'] for s in shared if s['kind'] == 'port'})
    verdict = 'merged_cells' if cross else ('separate_with_shared_inputs' if shared else 'separate')
    return dict(schema='glitchsat-hier-lint/1', top=top, copy_regex=copy_regex, verdict=verdict,
                copies={o: dict(cells=v['cells'], flops=v['flops']) for o, v in sorted(copies.items())},
                identical_signatures=[sorted(g) for g in groups.values() if len(g) > 1],
                cross_copy_reads=len(cross), cross_examples=cross[:10],
                shared_driver_nets=len(shared), shared_driver_cells=len(shared_cells),
                shared_driver_ports=shared_ports,
                shared_cell_types=dict(collections.Counter(m['cells'][c]['type'] for c in shared_cells).most_common()),
                shared_examples=shared[:10])
