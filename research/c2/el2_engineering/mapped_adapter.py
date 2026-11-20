#!/usr/bin/env python3
"""Adapter: Yosys-mapped sky130 Verilog -> fault-injection model checking (z3).

Does NOT edit scripts/. Reads
  * a mapped, possibly hierarchical Verilog netlist (Yosys write_verilog -noattr output),
  * the sky130_fd_sc_hd liberty file (DATA: cell `function` strings, area),
  * optionally an OpenROAD DEF (cell placement) for the locality experiment.
Fault model (MODELLED, not physics): a fault flips, for one clock cycle, the OUTPUT net of a standard cell
(combinational cell output or flop Q).  One cell = one fault site (internal transistor nodes are not modelled).
Locality mode: one 'glitch' = a disc of radius r (um) around a centre; it flips every cell output within the disc.
Same attack goal as scripts/glitchsat.py: boot_word == 0x96 at some cycle < N with sig != 0xC3 (held constant).
Flop initial state is NOT in the mapped Verilog (dfflibmap drops init), so it is supplied here from the RTL (F0 / 0).
"""
import re, json, sys, time, collections, math
from z3 import (Solver, Bool, BoolVal, BitVec, Extract, And, Or, Not, Xor, If, PbLe, sat, unsat, is_true, simplify)

# ------------------------------------------------------------------ liberty
def load_lib(path, wanted=None):
    t = open(path).read()
    cells = {}
    idx = [(m.start(), m.group(1)) for m in re.finditer(r'\n\s*cell \("([^"]+)"\)', t)]
    for i, (s, name) in enumerate(idx):
        if wanted and name not in wanted:
            continue
        e = idx[i + 1][0] if i + 1 < len(idx) else len(t)
        body = t[s:e]
        am = re.search(r'\n\s*area : ([0-9.]+)', body); area = float(am.group(1)) if am else 0.0
        pins = {}
        pidx = [(m.start(), m.group(1)) for m in re.finditer(r'\n\s*pin \("([^"]+)"\)', body)]
        for j, (ps, pn) in enumerate(pidx):
            pe = pidx[j + 1][0] if j + 1 < len(pidx) else len(body)
            pb = body[ps:pe]
            d = re.search(r'direction : "(\w+)"', pb)
            f = re.search(r'\n\s*function : "([^"]*)"', pb)
            pins[pn] = dict(dir=d.group(1) if d else None, func=f.group(1) if f else None)
        seq = bool(re.search(r'\n\s*ff \(', body))
        cells[name] = dict(area=area, pins=pins, seq=seq)
    return cells


def parse_func(s):
    """liberty boolean function -> nested tuple tree: ('v',name) ('not',x) ('and',a,b) ('or',a,b)"""
    toks = re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[!&|*+()^]|[01]', s)
    pos = [0]
    def peek(): return toks[pos[0]] if pos[0] < len(toks) else None
    def nxt(): pos[0] += 1; return toks[pos[0] - 1]
    def p_or():
        a = p_xor()
        while peek() in ('|', '+'):
            nxt(); a = ('or', a, p_xor())
        return a
    def p_xor():
        a = p_and()
        while peek() == '^':
            nxt(); a = ('xor', a, p_and())
        return a
    def p_and():
        a = p_un()
        while peek() in ('&', '*'):
            nxt(); a = ('and', a, p_un())
        return a
    def p_un():
        t = nxt()
        if t == '!': return ('not', p_un())
        if t == '(':
            a = p_or(); assert nxt() == ')'; return a
        if t in '01' and len(t) == 1 and t.isdigit(): return ('c', t == '1')
        return ('v', t)
    r = p_or(); assert pos[0] == len(toks), s
    return r


def ev(tree, env, simp=True):
    k = tree[0]
    if k == 'v': return env[tree[1]]
    if k == 'c': return BoolVal(tree[1])
    if k == 'not': return Not(ev(tree[1], env))
    a, b = ev(tree[1], env), ev(tree[2], env)
    return {'and': And, 'or': Or, 'xor': Xor}[k](a, b)


def tt_eval(tree, env):  # python-bool evaluator for self-test
    k = tree[0]
    if k == 'v': return env[tree[1]]
    if k == 'c': return tree[1]
    if k == 'not': return not tt_eval(tree[1], env)
    a, b = tt_eval(tree[1], env), tt_eval(tree[2], env)
    return {'and': a and b, 'or': a or b, 'xor': a != b}[k]

# ------------------------------------------------------------------ verilog (Yosys write_verilog style)
def strip_comments(t):
    return re.sub(r'/\*.*?\*/', '', t, flags=re.S)


def split_top(s):
    out, d, cur = [], 0, ''
    for ch in s:
        if ch in '{(': d += 1
        if ch in '})': d -= 1
        if ch == ',' and d == 0: out.append(cur.strip()); cur = ''
        else: cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


class Mod:
    pass


def parse_verilog(path):
    t = strip_comments(open(path).read())
    mods = {}
    for m in re.finditer(r'\bmodule\s+(\S+?)\s*\((.*?)\);(.*?)\bendmodule', t, flags=re.S):
        name, plist, body = m.group(1).lstrip('\\'), m.group(2), m.group(3)
        M = Mod(); M.name = name; M.ports = [p.strip() for p in plist.split(',') if p.strip()]
        M.width = {}; M.dir = {}; M.insts = []; M.assigns = []
        for st in body.split(';'):
            st = st.strip()
            if not st: continue
            mm = re.match(r'(input|output|wire)\s*(\[(\d+):(\d+)\])?\s*(\S+)$', st)
            if mm:
                w = int(mm.group(3)) - int(mm.group(4)) + 1 if mm.group(2) else 1
                M.width[mm.group(5)] = w
                if mm.group(1) != 'wire': M.dir[mm.group(5)] = mm.group(1)
                continue
            mm = re.match(r'assign\s+(.*?)\s*=\s*(.*)$', st, flags=re.S)
            if mm:
                M.assigns.append((mm.group(1), mm.group(2))); continue
            mm = re.match(r'(\S+)\s+(\S+)\s*\((.*)\)$', st, flags=re.S)
            if mm:
                pins = {}
                for pc in split_top(mm.group(3)):
                    pm = re.match(r'\.(\w+)\s*\((.*)\)$', pc, flags=re.S)
                    pins[pm.group(1)] = pm.group(2).strip()
                M.insts.append((mm.group(1), mm.group(2), pins)); continue
            raise Exception('unparsed statement: ' + st[:80])
        mods[name] = M
    return mods


def expr_bits(expr, M):
    """expression -> list of bit names, MSB first.  Bit name = 'net' (scalar) or 'net[i]'."""
    expr = expr.strip()
    if expr.startswith('{') and expr.endswith('}'):
        out = []
        for p in split_top(expr[1:-1]): out += expr_bits(p, M)
        return out
    mm = re.match(r"(\d+)'[bBhHdD]([0-9a-fA-FxXzZ_]+)$", expr)
    if mm:
        n = int(mm.group(1)); base = expr[expr.index("'") + 1].lower(); s = mm.group(2)
        v = int(s, {'b': 2, 'h': 16, 'd': 10}[base])
        return ['1' if (v >> i) & 1 else '0' for i in range(n - 1, -1, -1)]
    mm = re.match(r'(\S+?)\[(\d+):(\d+)\]$', expr)
    if mm:
        return [f'{mm.group(1)}[{i}]' for i in range(int(mm.group(2)), int(mm.group(3)) - 1, -1)]
    mm = re.match(r'(\S+?)\[(\d+)\]$', expr)
    if mm: return [expr]
    w = M.width.get(expr, 1)
    if w == 1: return [expr]
    return [f'{expr}[{i}]' for i in range(w - 1, -1, -1)]


class Flat:
    pass


def flatten(mods, top):
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b: parent[b] = a
    cells = []   # (fullname, type, {pin: netbit})
    def nm(prefix, b):
        return b if b in ('0', '1') else prefix + b
    def elab(mname, prefix):
        M = mods[mname]
        for lhs, rhs in M.assigns:
            L, R = expr_bits(lhs, M), expr_bits(rhs, M)
            assert len(L) == len(R), (lhs, rhs)
            for a, b in zip(L, R): union(nm(prefix, a), nm(prefix, b))
        for typ, iname, pins in M.insts:
            if typ in mods:
                C = mods[typ]
                for pn, ex in pins.items():
                    pb = expr_bits(pn if C.width.get(pn, 1) == 1 else pn, C)
                    eb = expr_bits(ex, M)
                    assert len(pb) == len(eb), (iname, pn)
                    for a, b in zip(pb, eb): union(nm(prefix + iname + '/', a), nm(prefix, b))
                elab(typ, prefix + iname + '/')
            else:
                cells.append((prefix + iname, typ, {p: nm(prefix, expr_bits(e, M)[0]) for p, e in pins.items()}))
    elab(top, '')
    F = Flat(); F.cells = cells; F.find = find; F.parent = parent; F.top = mods[top]; F.mods = mods
    return F

# ------------------------------------------------------------------ build glitchsat-style netlist
class Net:
    pass


def build_netlist(vpath, top, lib, init_spec):
    mods = parse_verilog(vpath)
    F = flatten(mods, top)
    T = mods[top]
    ids = {}
    def nid(b):
        if b == '0': return '0'
        if b == '1': return '1'
        r = F.find(b)
        if r not in ids: ids[r] = len(ids) + 2
        return ids[r]
    N = Net(); N.drivers = {}; N.dffs = []; N.cellinfo = {}; N.names = {}
    for cn, typ, pins in F.cells:
        if typ not in lib: raise Exception('cell not in liberty: ' + typ)
        li = lib[typ]
        outs = [p for p, d in li['pins'].items() if d['dir'] == 'output']
        assert len(outs) == 1, (typ, outs)
        op = outs[0]
        out = nid(pins[op])
        if li['seq']:
            N.dffs.append((cn, nid(pins['D']), out))
        else:
            ins = {p: nid(n) for p, n in pins.items() if p != op}
            N.drivers[out] = (cn, typ, ins, parse_func(li['pins'][op]['func']))
        N.cellinfo[cn] = dict(type=typ, out=out, seq=li['seq'], area=li['area'])
    N.ports = {}
    for p in T.ports:
        bits = [nid(b) for b in reversed(expr_bits(p, T))]
        N.ports[p] = dict(direction=T.dir[p], bits=bits)
    # names: prefer public names
    for r, i in ids.items():
        pass
    allnames = collections.defaultdict(list)
    for b in list(F.parent.keys()): allnames[nid(b)].append(b)
    for i, ns in allnames.items():
        ns = [n for n in ns if '/' not in n and not n.startswith('_')] or [n for n in ns if '/' not in n] or ns
        N.names[i] = sorted(ns, key=lambda s: (len(s), s))[0]
    N.dq = {q: d for _, d, q in N.dffs}
    N.qs = [q for _, _, q in N.dffs]
    # init
    N.init = {q: False for q in N.qs}
    for pname, val in init_spec.items():
        bits = N.ports[pname]['bits'] if pname in N.ports else None
        if bits is None: continue
        for i, b in enumerate(bits):
            if b in N.init: N.init[b] = bool((val >> i) & 1)
    return N


# ------------------------------------------------------------------ cone / distance (same idea as glitchsat)
def coi_dist(N, goal_bits):
    dist = {}; dq = collections.deque()
    for b in goal_bits:
        if isinstance(b, int): dist[b] = 0; dq.append(b)
    while dq:
        b = dq.popleft()
        if b in N.drivers: nxt = [(f, dist[b]) for f in N.drivers[b][2].values()]
        elif b in N.dq: nxt = [(N.dq[b], dist[b] + 1)]
        else: nxt = []
        for f, d in nxt:
            if isinstance(f, int) and (f not in dist or d < dist[f]): dist[f] = d; dq.append(f)
    return dist

# ------------------------------------------------------------------ model
def build(N, T, goal_out='boot_word', goal_value=0x96, attack_in='sig', key=0xC3, cover=None, bad_only=True, fixed_in=None, allowed=None, amo=False):
    """cover: None -> one fault var per cell output (cell-output flips).
       cover: dict site_id -> list of glitch ids (locality mode); returns glitch vars G."""
    ports = N.ports
    goal_bits = ports[goal_out]['bits']
    inputs = {p: BitVec(f'in_{p}', len(v['bits'])) for p, v in ports.items() if v['direction'] == 'input' and p != 'clk'}
    inbit = {}
    for p, v in ports.items():
        if p in inputs:
            for i, b in enumerate(v['bits']): inbit[b] = Extract(i, i, inputs[p]) == 1
    dist = coi_dist(N, goal_bits)
    sites = [b for b in list(N.qs) + list(N.drivers.keys()) if b in dist and (allowed is None or b in allowed)]
    if cover is None:
        G = {(t, b): Bool(f'f_{t}_{b}') for t in range(T) for b in sites if t + dist[b] <= T - 1}
        flip = {k: v for k, v in G.items()}
    else:
        gl = sorted({g for b in sites for g in cover.get(b, [])})
        G = {(t, g): Bool(f'g_{t}_{g}') for t in range(T) for g in gl}
        flip = {}
        for t in range(T):
            for b in sites:
                if t + dist[b] > T - 1: continue
                gs = [G[(t, g)] for g in cover.get(b, [])]
                if gs: flip[(t, b)] = gs[0] if len(gs) == 1 else Xor(*gs) if len(gs) == 2 else _xorn(gs)
    state = {q: BoolVal(N.init[q]) for q in N.qs}
    hits = []
    for t in range(T):
        val = {}
        def get(b):
            if b == '0': return BoolVal(False)
            if b == '1': return BoolVal(True)
            if b in val: return val[b]
            if b in inbit: return inbit[b]
            if b in state: v = state[b]
            else:
                cn, ty, ins, tree = N.drivers[b]
                v = ev(tree, {p: get(n) for p, n in ins.items()})
            if (t, b) in flip: v = Xor(v, flip[(t, b)])
            v = simplify(v); val[b] = v; return v
        nxt = {q: get(d) for q, d in N.dq.items()}
        w = [get(b) for b in goal_bits]
        hits.append(And(*[w[i] == BoolVal(bool((goal_value >> i) & 1)) for i in range(len(w))]))
        state = nxt
    s = Solver(); s.add(Or(*hits))
    if amo and cover is not None:
        for t in range(T):
            row = [G[(tt, g)] for (tt, g) in G if tt == t]
            if len(row) > 1: s.add(PbLe([(x, 1) for x in row], 1))
    ain = inputs[attack_in]
    if bad_only: s.add(ain != key)
    if fixed_in is not None: s.add(ain == fixed_in)
    return s, G, inputs


def _xorn(gs):
    r = gs[0]
    for g in gs[1:]: r = Xor(r, g)
    return r


def solve(N, T, k, cover=None, minimize=True, timeout_ms=0, **kw):
    t0 = time.time()
    s, G, inputs = build(N, T, cover=cover, **kw)
    if timeout_ms: s.set('timeout', timeout_ms)
    allf = list(G.values())
    if allf: s.add(PbLe([(f, 1) for f in allf], k))
    r = s.check()
    if r == unsat: return 'NO_ATTACK_UP_TO_BOUND', None, time.time() - t0
    if r != sat: return 'UNKNOWN', None, time.time() - t0
    ext = lambda m: [kk for kk, f in G.items() if is_true(m.eval(f, model_completion=True))]
    mod = s.model(); best = ext(mod)
    while minimize and best:
        s.push(); s.add(PbLe([(f, 1) for f in allf], len(best) - 1))
        if s.check() == sat: mod = s.model(); best = ext(mod); s.pop()
        else: s.pop(); break
    atk = {p: mod.eval(v, model_completion=True).as_long() for p, v in inputs.items()}
    return 'ATTACK_FOUND', dict(faults=sorted(best), inputs=atk), time.time() - t0


def honest(N, T, **kw):
    v, res, _ = solve(N, T, 0, minimize=False, bad_only=False, fixed_in=0xC3, **kw)
    return v == 'ATTACK_FOUND'


def self_test_cells(lib):
    """truth-table sanity: every used combinational cell's parsed function is a total boolean function of its inputs."""
    for n, c in lib.items():
        if c['seq']: continue
        for p, d in c['pins'].items():
            if d['dir'] == 'output' and d['func']:
                tr = parse_func(d['func'])
                ins = [q for q, dd in c['pins'].items() if dd['dir'] == 'input']
                try:
                    for m in range(1 << len(ins)):
                        tt_eval(tr, {q: bool(m >> i & 1) for i, q in enumerate(ins)})
                except KeyError:
                    pass  # internal-state pin (latches/ICG), not used here
    return True

# ------------------------------------------------------------------ placement
def read_def(path, lib, cellinfo):
    t = open(path).read()
    dbu = int(re.search(r'UNITS DISTANCE MICRONS (\d+)', t).group(1))
    pos = {}
    for m in re.finditer(r'-\s+(\S+)\s+(sky130_fd_sc_hd__\w+).*?\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)', t):
        name, typ, x, y, orient = m.group(1).replace('\\', ''), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5)
        area = lib[typ]['area'] if typ in lib else 0
        w = area / 2.72
        pos[name] = ((int(x) / dbu) + w / 2, (int(y) / dbu) + 2.72 / 2, typ)
    return pos


def cover_by_radius(N, pos, r, include_seq=True):
    """glitch centre = each logic cell centre (dedup by identical coverage). cover[site] = [glitch ids]."""
    cells = {cn: ci for cn, ci in N.cellinfo.items() if cn in pos}
    cen = {cn: pos[cn][:2] for cn in cells}
    cover = collections.defaultdict(list); seen = {}
    for cn in cells:
        cx, cy = cen[cn]
        cov = tuple(sorted(cells[d]['out'] for d in cells if (include_seq or not cells[d]['seq']) and math.hypot(cen[d][0] - cx, cen[d][1] - cy) <= r))
        if cov in seen: continue
        seen[cov] = cn
        for o in cov: cover[o].append(cn)
    return cover, len(seen)
