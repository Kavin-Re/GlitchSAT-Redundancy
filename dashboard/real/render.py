#!/usr/bin/env python3
"""Render Yosys write_json gate-level netlists to SVG/PNG via Graphviz dot. Nothing is hand-drawn."""
import json, subprocess, sys
FAULT = {  # nets flipped by the solver (glitchsat results, cycle 1)
 'v0': ['$flatten\\c.$abc$175$new_n13_'],
 'v1': ['ok'],
 'v2': ['word[0]','$flatten\\c1.$abc$251$new_n10_','$flatten\\c2.$abc$251$new_n10_'],
}
SHORT = {'$flatten\\c.$abc$175$new_n13_':'new_n13_'}
def short(n): return SHORT.get(n, n.split('$')[-1].replace('\\','') if n.startswith('$flatten') else n)
def render(v):
    m = json.load(open(f'netlists/{v}.json'))['modules'][v]
    names = {}
    for n, nd in m['netnames'].items():
        for i, b in enumerate(nd['bits']):
            if isinstance(b, int): names.setdefault(b, []).append((n, i, len(nd['bits']), nd['hide_name']))
    fbits = {}
    for fn in FAULT[v]:
        if fn in m['netnames']: bl = m['netnames'][fn]['bits']
        else:
            base, idx = fn[:-1].split('['); bl = [m['netnames'][base]['bits'][int(idx)]]
        for b in bl: fbits[b] = fn
    drv = {}; out = ['digraph G{rankdir=LR;bgcolor="white";nodesep=0.15;ranksep=0.35;node [fontname="Helvetica",fontsize=9];edge [arrowsize=0.5];',
      f'label="{v.upper()} gate-level netlist (Yosys {v}.json, generated)  |  red = net flipped by solver: {", ".join(short(f) for f in FAULT[v])}";labelloc=t;fontname="Helvetica";fontsize=13;']
    cells = m['cells']; ports = m['ports']
    for p, pd in ports.items():
        for i, b in enumerate(pd['bits']):
            nid = f'p_{p}_{i}'
            if pd['direction'] == 'input':
                drv[b] = nid
                out.append(f'{nid} [label="{p}[{i}]" shape=cds style=filled fillcolor="#dfe9f5"];' if len(pd['bits'])>1 else f'{nid} [label="{p}" shape=cds style=filled fillcolor="#dfe9f5"];')
    for c, cd in cells.items():
        t = cd['type'].strip('$_')
        isff = 'DFF' in t
        for p, d in cd['port_directions'].items():
            if d == 'output':
                for b in cd['connections'][p]: drv[b] = 'c_' + str(abs(hash(c)))
    cid = lambda c: 'c_' + str(abs(hash(c)))
    for c, cd in cells.items():
        t = cd['type'].strip('$_'); isff = 'DFF' in t
        yb = cd['connections']['Q' if isff else 'Y'][0]
        hit = yb in fbits
        nm = [n for n, i, l, h in names.get(yb, []) if not h]
        lab = ('FF' if isff else t) + (f'\\n{nm[0]}' if nm and not hit else '')
        if hit: lab += f'\\nFLIP {short(fbits[yb])}'
        if isff: st = 'shape=box style="filled" fillcolor="#ffe6a8"'
        else: st = 'shape=ellipse style=filled fillcolor="#eeeeee"'
        if hit: st = 'shape=ellipse style=filled fillcolor="#e03030" fontcolor=white penwidth=2.5 color="#900000"'
        out.append(f'{cid(c)} [label="{lab}" {st}];')
    for p, pd in ports.items():
        if pd['direction'] == 'output':
            for i, b in enumerate(pd['bits']):
                nid = f'o_{p}_{i}'
                lab = f'{p}[{i}]' if len(pd['bits'])>1 else p
                out.append(f'{nid} [label="{lab}" shape=cds style=filled fillcolor="#d9f0d9"];')
                if b in drv: out.append(f'{drv[b]} -> {nid}' + (' [color="#e03030" penwidth=2.5]' if b in fbits else '') + ';')
    for c, cd in cells.items():
        for p, d in cd['port_directions'].items():
            if d != 'input' or p == 'C': continue
            for b in cd['connections'][p]:
                if b in drv:
                    red = b in fbits
                    out.append(f'{drv[b]} -> {cid(c)}' + (' [color="#e03030" penwidth=2.5]' if red else ' [color="#555555"]') + ';')
    out.append('}')
    open(f'{v}.dot', 'w').write('\n'.join(out))
    for fmt, extra in (('svg', []), ('png', ['-Gdpi=160'])):
        subprocess.run(['dot', f'-T{fmt}', *extra, f'{v}.dot', '-o', f'{v}.{fmt}'], check=True)
    print(v, len(cells), 'cells,', sum('DFF' in c['type'] for c in cells.values()), 'flops')
for v in ('v0','v1','v2'): render(v)
