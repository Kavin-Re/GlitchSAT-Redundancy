#!/usr/bin/env python3
"""Reads layout/v_designs/out_patched/{v1,v2}.def + {v1,v2}_pnr.v (post-route netlist) +
the sky130_fd_sc_hd LEF (cell sizes), and writes:
  - /tmp/work_layout/nl/<d>_layout.json : the PLACED sky130 netlist decomposed into B3-format primitive gates (AND/OR/NOT/MUX/DFF);
    every primitive is named '<instance>::<k>' so each primitive maps to exactly one placed cell (MEASURED name mapping).
    sky130 cell functions taken from the liberty file (checked by hand, see report).
  - layout_geometry_<d>.json : per-cell coordinates, rail rows, taps, strap structure (MEASURED from DEF).
  - domains_<d>.json : domain families (lists of CELL names; the engine maps cell -> primitives).
Usage: python3 layout_extract.py [v1 v2]
"""
import re, sys, json, math, itertools, collections, os
ROOT = 'layout/v_designs/out_patched'
LEF = '/tmp/mm_root/envs/eda/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef'
OUT = os.path.dirname(os.path.abspath(__file__))
NLDIR = '/tmp/work_layout/nl'

# ------------------------------------------------------------------ LEF sizes
def lef_sizes():
    sz = {}; cur = None
    for l in open(LEF):
        m = re.match(r'\s*MACRO (\S+)', l)
        if m: cur = m.group(1)
        m = re.match(r'\s*SIZE ([\d.]+) BY ([\d.]+)', l)
        if m and cur: sz[cur] = (float(m.group(1)), float(m.group(2))); cur = None
    return sz

# ------------------------------------------------------------------ DEF
def parse_def(path):
    t = open(path).read()
    die = re.search(r'DIEAREA \( (\d+) (\d+) \) \( (\d+) (\d+) \)', t).groups()
    rows = [(m[0], int(m[1]) / 1000, int(m[2]) / 1000, m[3]) for m in re.findall(r'ROW (\S+) unithd (\d+) (\d+) (\S+)', t)]
    comps = {}
    for m in re.finditer(r'- (\S+) (\S+) \+ (?:SOURCE \w+ \+ )?(PLACED|FIXED) \( (\d+) (\d+) \) (\S+) ;', t):
        comps[m[1]] = dict(master=m[2], x=int(m[4]) / 1000, y=int(m[5]) / 1000, orient=m[6], status=m[3])
    sp = t[t.index('SPECIALNETS'):t.index('END SPECIALNETS')]
    nets = {}
    for blk in re.split(r'\n    - ', sp)[1:]:
        name = blk.split()[0]
        segs = []
        for m in re.finditer(r'(met\d) (\d+) \+ SHAPE (STRIPE|FOLLOWPIN) \( (\d+) (\d+) \) (?:\( (\d+) (\d+) \))?', blk):
            segs.append(dict(layer=m[1], width=int(m[2]) / 1000, shape=m[3], x1=int(m[4]) / 1000, y1=int(m[5]) / 1000,
                             x2=int(m[6]) / 1000 if m[6] else None, y2=int(m[7]) / 1000 if m[7] else None))
        vias = [dict(via=m[3], x=int(m[1]) / 1000, y=int(m[2]) / 1000, layer=m[4]) for m in
                re.finditer(r'(\d+) (\d+)\) ?(via\S*)', '') ]
        # via stacks: 'NEW metN 0 + SHAPE STRIPE ( x y ) viaK'
        vias = [dict(layer=m[1], x=int(m[2]) / 1000, y=int(m[3]) / 1000, via=m[4]) for m in
                re.finditer(r'(met\d) 0 \+ SHAPE STRIPE \( (\d+) (\d+) \) (via\S+)', blk)]
        nets[name] = dict(segs=segs, vias=vias)
    return dict(die=[int(x) / 1000 for x in die], rows=rows, comps=comps, special=nets)

# ------------------------------------------------------------------ Verilog (post-route)
def parse_v(path):
    t = open(path).read()
    ports = {}
    for m in re.finditer(r'^\s*(input|output)\s*(\[(\d+):0\])?\s*(\w+);', t, re.M):
        ports[m[4]] = (m[1], int(m[3]) + 1 if m[3] else 1)
    cells = []
    for m in re.finditer(r'^\s*(sky130_fd_sc_hd__\w+)\s+(\\?\S+)\s*\((.*?)\);', t, re.M | re.S):
        pins = dict((p, n.strip()) for p, n in re.findall(r'\.(\w+)\(([^)]*)\)', m[3]))
        cells.append((m[1], m[2].lstrip('\\'), pins))
    return ports, cells

class B:
    def __init__(s): s.n = 100; s.ids = {}; s.cells = {}
    def net(s, name):
        if name in ('1\'b0', 'x'): return '0'
        if name == "1'b1": return '1'
        if name not in s.ids: s.n += 1; s.ids[name] = s.n
        return s.ids[name]
    def new(s): s.n += 1; return s.n
    def gate(s, inst, k, ty, y, **ins):
        con = {p: [v] for p, v in ins.items()}; con['Y'] = [y]
        s.cells[f'{inst}::{k}'] = dict(hide_name=1, type=ty, parameters={}, attributes={},
                                      port_directions={**{p: 'input' for p in ins}, 'Y': 'output'}, connections=con)

def decompose(b, master, inst, pins):
    f = master.replace('sky130_fd_sc_hd__', '')
    n = lambda p: b.net(pins[p])
    out = lambda: b.net(pins.get('Y') or pins['X'])
    A = lambda k, y, x1, x2: b.gate(inst, k, '$_AND_', y, A=x1, B=x2)
    O = lambda k, y, x1, x2: b.gate(inst, k, '$_OR_', y, A=x1, B=x2)
    N = lambda k, y, x1: b.gate(inst, k, '$_NOT_', y, A=x1)
    if f.startswith('inv'): N(0, out(), n('A'))
    elif f.startswith('nand2b'): nb = b.new(); N(0, nb, n('B')); O(1, out(), n('A_N'), nb)
    elif f.startswith('nand3b'):
        nb, nc, o1 = b.new(), b.new(), b.new(); N(0, nb, n('B')); N(1, nc, n('C')); O(2, o1, nb, nc); O(3, out(), n('A_N'), o1)
    elif f.startswith('nand3'):
        t1, t2 = b.new(), b.new(); A(0, t1, n('A'), n('B')); A(1, t2, t1, n('C')); N(2, out(), t2)
    elif f.startswith('a21bo_'):
        t, nb = b.new(), b.new(); A(0, t, n('A1'), n('A2')); N(1, nb, n('B1_N')); O(2, out(), t, nb)
    elif f.startswith('o21ai'):
        o, a = b.new(), b.new(); O(0, o, n('A1'), n('A2')); A(1, a, o, n('B1')); N(2, out(), a)
    elif f.startswith('o21a'):
        o = b.new(); O(0, o, n('A1'), n('A2')); A(1, out(), o, n('B1'))
    elif f.startswith('nand2'): t = b.new(); A(0, t, n('A'), n('B')); N(1, out(), t)
    elif f.startswith('nand4bb'):
        nc, nd, o1, o2 = b.new(), b.new(), b.new(), b.new()
        N(0, nc, n('C')); N(1, nd, n('D')); O(2, o1, n('A_N'), n('B_N')); O(3, o2, nc, nd); O(4, out(), o1, o2)
    elif f.startswith('nand4'):
        t1, t2, t3 = b.new(), b.new(), b.new(); A(0, t1, n('A'), n('B')); A(1, t2, n('C'), n('D')); A(2, t3, t1, t2); N(3, out(), t3)
    elif f.startswith('nor4bb'):
        o, a, na, o2 = b.new(), b.new(), b.new(), b.new()
        O(0, o, n('A'), n('B')); A(1, a, n('C_N'), n('D_N')); N(2, na, a); O(3, o2, o, na); N(4, out(), o2)
    elif f.startswith('nor4'):
        o1, o2, o3 = b.new(), b.new(), b.new(); O(0, o1, n('A'), n('B')); O(1, o2, n('C'), n('D')); O(2, o3, o1, o2); N(3, out(), o3)
    elif f.startswith('nor2'): o = b.new(); O(0, o, n('A'), n('B')); N(1, out(), o)
    elif f.startswith('and2'): A(0, out(), n('A'), n('B'))
    elif f.startswith('and4'):
        t1, t2 = b.new(), b.new(); A(0, t1, n('A'), n('B')); A(1, t2, n('C'), n('D')); A(2, out(), t1, t2)
    elif f.startswith('a21o'): t = b.new(); A(0, t, n('A1'), n('A2')); O(1, out(), t, n('B1'))
    elif f.startswith('a2bb2oi'):
        o, a, na = b.new(), b.new(), b.new(); O(0, o, n('A1_N'), n('A2_N')); A(1, a, n('B1'), n('B2')); N(2, na, a); A(3, out(), o, na)
    elif f.startswith('a22o'):
        t1, t2 = b.new(), b.new(); A(0, t1, n('A1'), n('A2')); A(1, t2, n('B1'), n('B2')); O(2, out(), t1, t2)
    elif f.startswith('a21boi'):
        t, nt = b.new(), b.new(); A(0, t, n('A1'), n('A2')); N(1, nt, t); A(2, out(), nt, n('B1_N'))
    elif f.startswith('mux2'): b.gate(inst, 0, '$_MUX_', out(), A=n('A0'), B=n('A1'), S=n('S'))
    else: raise ValueError(master)

def build_nl(d, ports, cells):
    b = B(); dffs = {}
    pb = {}
    for p, (dr, w) in ports.items():
        pb[p] = {'direction': dr, 'bits': [b.net(p if w == 1 else f'{p}[{i}]') for i in range(w)]}
    logic = [c for c in cells if not re.search(r'__(tap|fill|decap|clkbuf)', c[0])]
    for master, inst, pins in logic:
        if 'dfxtp' in master:
            dffs[inst] = dict(hide_name=1, type='$_DFF_P_', parameters={}, attributes={},
                              port_directions={'C': 'input', 'D': 'input', 'Q': 'output'},
                              connections={'C': [b.net('clk')], 'D': [b.net(pins['D'])], 'Q': [b.net(pins['Q'])]})
        else: decompose(b, master, inst, pins)
    cl = {**b.cells, **{f'{k}': v for k, v in dffs.items()}}
    netnames = {}
    for name, i in b.ids.items(): netnames[name] = dict(bits=[i], attributes={})
    # init: no reset in the layout netlist; the RTL says st = 8'hF0 -> ASSUMPTION carried from rtl (documented)
    bw = pb['boot_word']['bits']
    netnames['st_init'] = dict(bits=bw, attributes={'init': '11110000'})
    mod = dict(attributes={'top': '1'}, ports=pb, cells=cl, netnames=netnames)
    return {'creator': 'layout_extract.py from sky130 post-route netlist', 'modules': {d: mod}}

# ------------------------------------------------------------------ geometry / domains
def analyse(d, swaps=None, tag=''):
    """swaps: list of (cellA, cellB) of the SAME master whose placements (x, y, orient) are exchanged: a hypothetical 'what-if' placement
    (routing not redone, legality only in the sense of identical footprints). Output names get the suffix tag."""
    sz = lef_sizes()
    D = parse_def(f'{ROOT}/{d}.def')
    ports, cells = parse_v(f'{ROOT}/{d}_pnr.v')
    for a, b in (swaps or []):
        ca, cb = D['comps'][a], D['comps'][b]; assert ca['master'] == cb['master'], (a, b)
        for k in ('x', 'y', 'orient'): ca[k], cb[k] = cb[k], ca[k]
    d0, d = d, d + tag
    nl = build_nl(d, ports, cells)
    os.makedirs(NLDIR, exist_ok=True)
    json.dump(nl, open(f'{NLDIR}/{d}_layout.json', 'w'))
    comps = D['comps']
    for k, c in comps.items():
        w, h = sz[c['master']]; c['w'], c['h'] = w, h; c['cx'], c['cy'] = c['x'] + w / 2, c['y'] + h / 2
        c['kind'] = ('tap' if 'tapvpwr' in c['master'] else 'fill' if re.search('fill|decap', c['master'])
                     else 'clkbuf' if 'clkbuf' in c['master'] else 'flop' if 'dfxtp' in c['master'] else 'gate')
    rows = D['rows']
    rowy = {round(y, 3): (n, o) for n, x, y, o in [(r[0], r[1], r[2], r[3]) for r in rows]}
    # rail index: row r (0..7): orient N -> VGND bottom, VPWR top; FS -> VPWR bottom, VGND top
    row_of = {}
    rail = {}
    for n, x, y, o in rows:
        r = int(n.split('_')[1]); row_of[round(y, 3)] = r
        bot, top = (y, y + 2.72)
        vpwr_y, vgnd_y = (top, bot) if o == 'N' else (bot, top)
        rail[r] = dict(row=r, y0=y, orient=o, vpwr_y=round(vpwr_y, 3), vgnd_y=round(vgnd_y, 3))
    for k, c in comps.items(): c['row'] = row_of[round(c['y'], 3)]; c['vpwr_y'] = rail[c['row']]['vpwr_y']; c['vgnd_y'] = rail[c['row']]['vgnd_y']
    # strap structure (MEASURED from SPECIALNETS)
    sp = D['special']
    straps = {}
    for net, v in sp.items():
        st = [s for s in v['segs'] if s['shape'] == 'STRIPE' and s['x2'] is not None]
        fp = [s for s in v['segs'] if s['shape'] == 'FOLLOWPIN']
        straps[net] = dict(met5=[(s['y1'], s['x1'], s['x2']) for s in st if s['layer'] == 'met5'],
                           met4=[(s['x1'], s['y1'], s['y2']) for s in st if s['layer'] == 'met4'],
                           met1_rails=[(s['y1'], s['x1'], s['x2']) for s in fp],
                           via_met1_points=sorted({(v2['x'], v2['y']) for v2 in v['vias'] if v2['layer'] == 'met1'}))
    vp_x = straps['VPWR']['met4'][0][0]; vg_x = straps['VGND']['met4'][0][0]
    for c in comps.values():
        c['d_vpwr_strap'] = abs(c['cx'] - vp_x); c['d_vgnd_strap'] = abs(c['cx'] - vg_x)
    logic = {k: c for k, c in comps.items() if c['kind'] in ('gate', 'flop')}
    taps = {k: c for k, c in comps.items() if c['kind'] == 'tap'}
    # copies: by hierarchical instance prefix c0/ c1/ c2/ (MEASURED naming from keep_hierarchy cmp8)
    copy_of = {k: k.split('/')[0] for k in logic if re.match(r'c\d/', k)}
    copies = collections.defaultdict(list)
    for k, cp in copy_of.items(): copies[cp].append(k)
    dist = lambda a, b: math.hypot(a['cx'] - b['cx'], a['cy'] - b['cy'])
    # nearest tap per cell
    for k, c in logic.items():
        ts = sorted((dist(c, t), tk) for tk, t in taps.items())
        c['tap_nearest'] = (ts[0][1], round(ts[0][0], 3))
        same = sorted((abs(c['cx'] - t['cx']), tk) for tk, t in taps.items() if t['row'] == c['row'])
        # taps in the row pair sharing this cell's VPWR rail (shared nwell)
        pair = sorted((dist(c, t), tk) for tk, t in taps.items() if t['vpwr_y'] == c['vpwr_y'])
        c['tap_same_row'] = (same[0][1], round(same[0][0], 3)) if same else None
        c['tap_same_vpwr_rail'] = (pair[0][1], round(pair[0][0], 3)) if pair else None
    # ---------- domain families (cell-name groups)
    fam = {}
    L = sorted(logic)
    # (a) row domains: all logic cells in one placement row (cells share both rails of the row)
    fam['row'] = {f'row{r}': sorted(k for k in L if logic[k]['row'] == r) for r in range(len(rows))}
    # (b) VPWR-rail domains: cells whose VPWR met1 rail is the same line (two rows share it)
    fam['vpwr_rail'] = {}
    for k in L: fam['vpwr_rail'].setdefault(f"vpwr_y{logic[k]['vpwr_y']}", []).append(k)
    fam['vgnd_rail'] = {}
    for k in L: fam['vgnd_rail'].setdefault(f"vgnd_y{logic[k]['vgnd_y']}", []).append(k)
    # (c) strap-based (INFERRED from the PDN geometry): VPWR rail x (side of its single met4 via column)
    fam['strap_branch'] = {}
    for k in L:
        c = logic[k]
        fam['strap_branch'].setdefault(f"vpwr_y{c['vpwr_y']}_{'L' if c['cx'] < vp_x else 'R'}of_met4_x{vp_x}", []).append(k)
    fam['strap_far'] = {}
    for thr in (5.0, 10.0):   # cells farther than thr um along the rail from the single met4 VPWR connection
        fam['strap_far'][f'vpwr_dx_gt{thr}'] = sorted(k for k in L if logic[k]['d_vpwr_strap'] > thr)
        fam['strap_far'][f'vpwr_dx_le{thr}'] = sorted(k for k in L if logic[k]['d_vpwr_strap'] <= thr)
    # (d) radius domains: disc centered on each logic cell centre, cell included if its centre is within r
    for r in (2.0, 3.5, 5.0, 10.0):
        g = {}
        for k in L:
            S = tuple(sorted(j for j in L if dist(logic[k], logic[j]) <= r))
            g.setdefault(S, []).append(k)
        fam[f'radius_{r}'] = {f'r{r}_at_{v[0]}': list(S) for S, v in g.items()}
    fam['rail_all'] = {'all': L}
    # (e) nwell/tap-based (INFERRED): cells whose nearest tap is the same tap
    fam['tap_nearest'] = {}
    for k in L: fam['tap_nearest'].setdefault(f"tap_{logic[k]['tap_nearest'][0]}", []).append(k)
    # ---------- copy geometry
    geo = dict(design=d, die=D['die'], rows=list(rail.values()), n_logic=len(L), n_taps=len(taps),
               straps={k: dict(met5_y_x1_x2=v['met5'], met4_x_y1_y2=v['met4'], met1_rails_y_x1_x2=v['met1_rails'],
                               met1_via_stack_points=v['via_met1_points']) for k, v in straps.items()},
               taps={k: dict(x=t['cx'], y=t['cy'], row=t['row']) for k, t in taps.items()},
               cells={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in c.items()} for k, c in logic.items()},
               copies={k: sorted(v) for k, v in copies.items()})
    json.dump(geo, open(f'{OUT}/layout_geometry_{d}.json', 'w'), indent=1)
    meta = dict(design=d, label='MEASURED coordinates from DEF; rail structure MEASURED from DEF SPECIALNETS; '
                'strap_*/tap_nearest families are INFERRED domain definitions (no extraction of a power network). Group members are '
                'placed-cell instance names (sky130 cells from out_patched/%s_pnr.v). Engine mapping: cell -> primitives named "<cell>::k" in '
                'nl/%s_layout.json (flop cell -> its Q for D-capture).' % (d, d),
                families={f: groups for f, groups in fam.items()})
    json.dump(meta, open(f'{OUT}/domains_{d}.json', 'w'), indent=1)
    return D, comps, logic, taps, copies, fam, geo, dist, rail

if __name__ == '__main__':
    for d in (sys.argv[1:] or ['v1', 'v2']):
        r = analyse(d); print(d, 'logic cells', len(r[2]), 'taps', len(r[3]), 'copies', {k: len(v) for k, v in r[4].items()},
                               {f: len(g) for f, g in r[5].items()})
