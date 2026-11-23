"""Merge lint and structural survival across flows, by ext/checker (check-survival).

Each flow's netlist is handed to the checker in one common form: the primitive circuit GlitchSAT analyses, written
as a Yosys JSON netlist of $_AND_/$_OR_/$_XOR_/$_NOT_/$_MUX_ gates and $_DFF_P_ flip-flops, with hierarchy names kept
in the cell names. So the same lint runs on Yosys gates, Nangate45, sky130 or any Liberty-mapped netlist. The RTL
(Verilog only) is scanned for intended redundancy (copies, sparse encodings, shadow registers, alarms) and, with Yosys,
elaborated as the "as written" reference stage."""
import json
import os
import sys

from .engine import checker_dir


def export_json(R, top, path):
    c = R.circ
    cells, nets = {}, {}
    for p, (d, bits) in c.ports.items():
        pass
    ports = {p: dict(direction=d, bits=list(b)) for p, (d, b) in c.ports.items()}
    for y, (op, fi) in c.gates.items():
        si = R.site_info.get(y)
        sc = (si['scope'] + '.') if si and si['scope'] else ''
        nm = '%sg%d' % (sc, y)
        if op == 'MUX':
            con = dict(S=[fi[0]], B=[fi[1]], A=[fi[2]], Y=[y])
        elif op == 'NOT':
            con = dict(A=[fi[0]], Y=[y])
        else:
            con = dict(A=[fi[0]], B=[fi[1]], Y=[y])
        cells[nm] = dict(type='$_%s_' % op, connections=con, port_directions={k: ('output' if k == 'Y' else 'input') for k in con})
    clk = None
    for p, (d, bits) in c.ports.items():
        if d == 'input' and not any(isinstance(b, int) and b in c.inputs for b in bits):
            clk = bits[0]
    if clk is None:
        clk = max([n for n in c.gates] + [n for n in c.flops] + [1]) + 1
        ports['gs_clk'] = dict(direction='input', bits=[clk])
    for q, (d, i) in c.flops.items():
        cn = R.flop_cell.get(q, 'q%d' % q)
        sc = (__import__('glitchsat_byod.netlist', fromlist=['x'])._scope(cn) + '.') if cn else ''
        cells['%sff%d' % (sc if sc != '.' else '', q)] = dict(type='$_DFF_P_', connections=dict(C=[clk], D=[d], Q=[q]),
                                                              port_directions=dict(C='input', D='input', Q='output'))
    names = {n: str(nm) for n, nm in c.names.items() if isinstance(n, int)}
    # a flip-flop's stored value carries the register name (the Q pin net is a buffer of it in the fault model)
    for q, qf in getattr(R, 'stored', {}).items():
        y = (R.site_info.get(qf) or {}).get('label_net')
        if y in names and c.gates.get(y) == ('AND', (qf, qf)):
            names[q] = names[y]
            names[y] = names[y] + '_q'
    groups = {}
    import re as _re
    for n, nm in names.items():
        nm = nm.replace(' ', '_')
        m = _re.match(r'^(.*)\[(\d+)\]$', nm)
        if m:
            groups.setdefault(m.group(1), {})[int(m.group(2))] = n
        else:
            nets.setdefault(nm, dict(bits=[n], attributes={}))
    for base, bits in groups.items():
        if base in nets:
            continue
        w = max(bits) + 1
        if len(bits) == w:
            nets[base] = dict(bits=[bits[i] for i in range(w)], attributes={})
        else:
            for i, n in bits.items():
                nets['%s[%d]' % (base, i)] = dict(bits=[n], attributes={})
    for q in c.flops:
        iv = R.flop_init.get(q)
        if iv is not None:
            nets['gs_state_%d' % q] = dict(bits=[q], attributes={'init': '1' if iv else '0'})
    doc = dict(creator='GlitchSAT byod export', modules={top: dict(ports=ports, cells=cells, netnames=nets)})
    with open(path, 'w') as f:
        json.dump(doc, f)
    return path


_CACHE = {}


def run(spec, flows, main):
    key = (spec['path'], spec['task'], tuple(flows))
    if key in _CACHE:
        return _CACHE[key]
    try:
        d = checker_dir()
    except ImportError as e:
        return dict(verdict='NOT_RUN', why=str(e))
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        from survival import pipeline
    except Exception as e:                      # noqa: BLE001
        return dict(verdict='NOT_RUN', why='ext/checker could not be loaded: %s' % e)
    work = os.path.join(spec['work'], 'lint')
    os.makedirs(work, exist_ok=True)
    stages = []
    top = spec['top_resolved']
    for fl, (R, s, info) in flows.items():
        p = export_json(R, top, os.path.join(work, '%s.json' % fl))
        stages.append(dict(name=fl, netlist=p))
    rtl = [p for p in spec['sources'] if p.endswith(('.v', '.sv'))]
    auto = bool(rtl) and all(p.endswith('.v') for p in spec['sources']) and not spec['params'] and not spec['defines']
    cfg = dict(name=spec['name'], top=top, intent=dict(rtl=rtl, reference='auto' if auto else 'none'), stages=stages,
               policy=dict(fail_on='weakened'))
    logs = []
    try:
        rep = pipeline.run(cfg, work, workdir=os.path.join(work, 'tmp'), want_margin=False, log=logs.append)
    except Exception as e:                      # noqa: BLE001
        out = dict(verdict='NOT_RUN', why='checker failed: %s: %s' % (type(e).__name__, e))
        _CACHE[key] = out
        return out
    cms = []
    dropped = []
    ports = set(spec.get('top_ports') or [])
    leaves = {str(n).split('.')[-1] for n in spec.get('design_names') or []}
    for c in rep.get('countermeasures', []):
        if c.get('kind') in ('sparse_encoding', 'mubi'):
            reg = str(c.get('id') or '').split(':', 1)[-1].split('.')[-1]
            if reg and (reg in ports or reg not in leaves):
                dropped.append('`%s` is %s, not a register of the design; not reported as a protection'
                               % (reg, 'a top-level port' if reg in ports else 'not a signal (a type or parameter name)'))
                continue
        cms.append(dict(id=c.get('id'), title=c.get('title'), kind=c.get('kind'), source=c.get('source') or c.get('where'), verdict=c.get('verdict'),
                        stages=[dict(stage=r.get('stage'), verdict=r.get('verdict'), evidence=(r.get('evidence') or [])[:4],
                                     cause=r.get('cause'), fix=(r.get('fix') or [])[:2]) for r in c.get('stages', [])]))
    out = dict(label='MEASURED (structure)', tool='ext/checker check-survival %s' % rep.get('tool', {}).get('version'),
               verdict=rep.get('summary', {}).get('verdict'), counts=rep.get('summary', {}).get('counts'),
               countermeasures=cms, notes=(rep.get('notes', [])[:10] + dropped))
    _CACHE[key] = out
    return out
