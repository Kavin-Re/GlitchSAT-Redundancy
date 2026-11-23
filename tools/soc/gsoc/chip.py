"""Whole-chip netlist loader: Yosys JSON (flattened, gate level) -> one gscale Circuit plus what a chip adds.

What is read
  gates     the Yosys gate library ($_AND_ ... $_OAI4_). Each cell has ONE fault site: its output. Cells that are
            not one of the five primitives of the engine are split into primitives whose inner nets are not fault
            sites, so the number of fault sites equals the number of cells.
  flops     every fine-grained Yosys flop type: plain, clock enable, synchronous reset, asynchronous reset and
            combinations. The Q output is the fault site. Enable and reset become (fault-free) logic on D.
            An asynchronous reset is modelled as a reset that takes effect at the next clock edge (the usual
            async2sync abstraction): a fault on the reset tree therefore still resets the flops it reaches.
  clocks    the clock net of every flop is recorded. Flops on the reference clock tick every cycle. Flops on any
            other clock net (a second domain, a gated or divided clock) get a free "tick" input per clock net
            and cycle: they may or may not load. Every real schedule of such a clock that is not faster than
            the reference clock is one of the allowed behaviours, so "no attack" results stay valid.
            A standard clock gate (latch + AND on the reference clock) is recognised and modelled exactly:
            its domain ticks in the cycles in which the gate enable is 1.
  memories  cells that are not gates or flops ($mem_v2 left by `memory -nomap`, latches, vendor macros) are
            black boxes: their outputs become free values, new in every cycle. Whatever the memory holds is one
            of the allowed behaviours. Their inputs are sinks.
  x bits    a constant x in the netlist is a free value, new in every cycle.

Free values are an over-approximation: a "no attack with up to k faults" result on the model implies the same
for the chip under the fault model; an attack that relies on a free value is reported with that dependence.
"""
import json
import re

from . import gscale

G = gscale()
C = G.circuit
AND, OR, XOR, NOT, MUX = C.AND, C.OR, C.XOR, C.NOT, C.MUX


class ChipError(Exception):
    pass


# type -> (pins, builder). builder(new, *ins) returns (op, fanins) of the OUTPUT gate; `new(op, fanins)` creates an
# inner gate that is not a fault site.
_GATES = {
    '$_BUF_': (('A',), lambda n, a: (AND, (a, '1'))),
    '$_NOT_': (('A',), lambda n, a: (NOT, (a,))),
    '$_AND_': (('A', 'B'), lambda n, a, b: (AND, (a, b))),
    '$_OR_': (('A', 'B'), lambda n, a, b: (OR, (a, b))),
    '$_XOR_': (('A', 'B'), lambda n, a, b: (XOR, (a, b))),
    '$_MUX_': (('A', 'B', 'S'), lambda n, a, b, s: (MUX, (s, b, a))),
    '$_NAND_': (('A', 'B'), lambda n, a, b: (NOT, (n(AND, (a, b)),))),
    '$_NOR_': (('A', 'B'), lambda n, a, b: (NOT, (n(OR, (a, b)),))),
    '$_XNOR_': (('A', 'B'), lambda n, a, b: (NOT, (n(XOR, (a, b)),))),
    '$_ANDNOT_': (('A', 'B'), lambda n, a, b: (AND, (a, n(NOT, (b,))))),
    '$_ORNOT_': (('A', 'B'), lambda n, a, b: (OR, (a, n(NOT, (b,))))),
    '$_NMUX_': (('A', 'B', 'S'), lambda n, a, b, s: (NOT, (n(MUX, (s, b, a)),))),
    '$_AOI3_': (('A', 'B', 'C'), lambda n, a, b, c: (NOT, (n(OR, (n(AND, (a, b)), c)),))),
    '$_OAI3_': (('A', 'B', 'C'), lambda n, a, b, c: (NOT, (n(AND, (n(OR, (a, b)), c)),))),
    '$_AOI4_': (('A', 'B', 'C', 'D'), lambda n, a, b, c, d: (NOT, (n(OR, (n(AND, (a, b)), n(AND, (c, d)))),))),
    '$_OAI4_': (('A', 'B', 'C', 'D'), lambda n, a, b, c, d: (NOT, (n(AND, (n(OR, (a, b)), n(OR, (c, d)))),))),
}

# Yosys fine-grained flop names: $_DFF_P_, $_DFFE_PP_, $_DFF_PN0_, $_DFFE_PN0P_, $_SDFF_PP0_, $_SDFFE_PP0P_,
# $_SDFFCE_PP0P_.  Groups: clock polarity, [reset polarity, reset value], [enable polarity].
_FF = [
    (re.compile(r'^\$_DFF_([NP])_$'), 'plain'),
    (re.compile(r'^\$_DFFE_([NP])([NP])_$'), 'en'),
    (re.compile(r'^\$_DFF_([NP])([NP])([01])_$'), 'arst'),
    (re.compile(r'^\$_DFFE_([NP])([NP])([01])([NP])_$'), 'arst_en'),
    (re.compile(r'^\$_SDFF_([NP])([NP])([01])_$'), 'srst'),
    (re.compile(r'^\$_SDFFE_([NP])([NP])([01])([NP])_$'), 'srst_en'),
    (re.compile(r'^\$_SDFFCE_([NP])([NP])([01])([NP])_$'), 'srst_ce'),
    (re.compile(r'^\$_ALDFF_([NP])([NP])_$'), 'aload'),
    (re.compile(r'^\$_ALDFFE_([NP])([NP])([NP])_$'), 'aload_en'),
]


def flop_kind(t):
    for rx, kind in _FF:
        m = rx.match(t or '')
        if m:
            return kind, m.groups()
    return None, None


class Chip:
    """circ: gscale Circuit of the whole chip. sites: nets that may be flipped (cell outputs). info: counts and
    assumptions. Free values (black-box outputs, x bits, clock ticks) are extra entries of circ.inputs whose
    port name starts with '$free'."""

    def __init__(self, name):
        self.name = name
        self.circ = C.Circuit()
        self.sites = set()
        self.free = {}            # net -> reason ('blackbox:<cell>', 'x', 'tick:<clock net name>')
        self.reset_value = {}     # flop q -> bool: value loaded by its own reset (async or sync), when it has one
        self.init_attr = {}       # flop q -> bool: Verilog `initial` value, when the netlist carries one
        self.flop_clock = {}      # flop q -> (clock net, polarity)
        self.flop_type = {}       # flop q -> yosys type
        self.bits = {}            # public name -> list of nets
        self.aliases = {}         # net -> every public name of that net (synthesis can merge several names)
        self.info = {}
        self._next = 0

    def new_net(self, name=None):
        self._next += 1
        if name:
            self.circ.names[self._next] = name
        return self._next

    def net(self, spec):
        """'name' (1-bit), 'name[i]' -> one net id. Hierarchy separators are dots, as Yosys writes after flatten."""
        m = re.match(r'^(.*)\[(\d+)\]$', spec)
        if spec in self.bits and len(self.bits[spec]) == 1:
            return self.bits[spec][0]
        if m and m.group(1) in self.bits:
            v = self.bits[m.group(1)]
            i = int(m.group(2))
            if i >= len(v):
                raise ChipError('%s: index out of range (width %d)' % (spec, len(v)))
            return v[i]
        if spec in self.bits:
            raise ChipError('%s is %d bits wide; give an index or use word()' % (spec, len(self.bits[spec])))
        raise ChipError('no net named %r in %s (names of nets removed by synthesis are not available; goals should '
                        'name ports, registers or nets marked (* keep *))' % (spec, self.name))

    def word(self, name):
        if name not in self.bits:
            raise ChipError('no net named %r in %s' % (name, self.name))
        return list(self.bits[name])

    def stats(self):
        return dict(self.info)


def _top(doc, top):
    mods = doc.get('modules') if isinstance(doc, dict) else None
    if not isinstance(mods, dict) or not mods:
        raise ChipError('not a Yosys JSON netlist (no modules)')
    if top is None:
        tops = [n for n, m in mods.items() if str((m.get('attributes') or {}).get('top', '0')).strip('0') != '']
        if len(tops) != 1:
            raise ChipError('give the top module (modules: %s)' % sorted(mods)[:20])
        top = tops[0]
    if top not in mods:
        raise ChipError('no module %r' % top)
    return top, mods[top], mods


def load(path_or_doc, top=None, clock=None, name=None):
    """clock: name of the reference clock input port (default: the clock net that drives most flops)."""
    doc = path_or_doc
    if isinstance(doc, str):
        with open(doc) as f:
            doc = json.load(f)
    top, m, mods = _top(doc, top)
    ch = Chip(name or top)
    c = ch.circ
    mx = 1
    for x in m['netnames'].values():
        for b in x['bits']:
            if isinstance(b, int) and b > mx:
                mx = b
    for cell in m['cells'].values():
        for v in (cell.get('connections') or {}).values():
            for b in v:
                if isinstance(b, int) and b > mx:
                    mx = b
    ch._next = mx

    for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
        nm = n.lstrip('\\')
        bits = list(x['bits'])
        if not n.startswith('$'):
            ch.bits[nm] = bits
        for i, b in enumerate(bits):
            if isinstance(b, int):
                c.names.setdefault(b, '%s[%d]' % (nm, i) if len(bits) > 1 else nm)
                if not n.startswith('$'):
                    ch.aliases.setdefault(b, []).append('%s[%d]' % (nm, i) if len(bits) > 1 else nm)
        iv = (x.get('attributes') or {}).get('init')
        if isinstance(iv, str):
            for i, chx in enumerate(reversed(iv)):
                if i < len(bits) and chx in '01' and isinstance(bits[i], int):
                    ch.init_attr[bits[i]] = chx == '1'
    for p, v in m['ports'].items():
        c.ports[p] = (v.get('direction'), list(v['bits']))
        if v.get('direction') in ('input', 'inout'):
            for i, b in enumerate(v['bits']):
                if isinstance(b, int):
                    c.inputs[b] = (p, i)

    xnets = {}

    def fix(b, cell):
        """A constant x/z read by a cell becomes a free value (one per reading cell pin is not needed: one per cell)."""
        if isinstance(b, int) or b in ('0', '1'):
            return b
        key = cell
        if key not in xnets:
            n = ch.new_net('$x$%s' % cell)
            xnets[key] = n
            c.inputs[n] = ('$free$x', len(xnets) - 1)
            ch.free[n] = 'x'
        return xnets[key]

    def driven(net, cell):
        if not isinstance(net, int):
            raise ChipError('cell %s drives a constant' % cell)
        if net in c.gates or net in c.flops or net in c.inputs:
            raise ChipError('net %s has more than one driver (cell %s)' % (c.name(net), cell))

    counts = {}
    flops_raw = []
    blackboxes = {}
    nfree = 0
    for cn, cell in m['cells'].items():
        t, con = cell.get('type'), cell.get('connections') or {}
        if t == '$scopeinfo':
            continue
        counts[t] = counts.get(t, 0) + 1
        if t in _GATES:
            pins, build = _GATES[t]
            try:
                ins = [fix(con[p][0], cn) for p in pins]
                y = con['Y'][0]
            except (KeyError, IndexError):
                raise ChipError('cell %s (%s): missing pin' % (cn, t))
            driven(y, cn)

            def inner(op, fi, cn=cn):
                n = ch.new_net()
                c.gates[n] = (op, tuple(fi))
                c.cell[n] = cn
                return n
            op, fi = build(inner, *ins)
            c.gates[y] = (op, tuple(fi))
            c.cell[y] = cn
            ch.sites.add(y)
            continue
        kind, grp = flop_kind(t)
        if kind:
            flops_raw.append((cn, t, kind, grp, con))
            continue
        if t in mods and not (mods[t].get('attributes') or {}).get('blackbox'):
            raise ChipError('module %s still instantiates %s: the loader needs a flattened netlist' % (top, t))
        # black box: outputs are free values
        dirs = cell.get('port_directions') or {}
        outs = 0
        for p, v in con.items():
            if dirs.get(p) == 'output' or (not dirs and p in ('Y', 'Q', 'RD_DATA')):
                for i, b in enumerate(v):
                    if isinstance(b, int):
                        driven(b, cn)
                        c.inputs[b] = ('$free$bb', nfree)
                        nfree += 1
                        ch.free[b] = 'blackbox:%s' % cn
                        c.cell[b] = cn
                        outs += 1
        par = cell.get('parameters') or {}
        bb = dict(type=t, output_bits=outs)
        if t == '$mem_v2':
            def pint(k):
                v = par.get(k, 0)
                return int(v, 2) if isinstance(v, str) else int(v)
            bb.update(words=pint('SIZE'), width=pint('WIDTH'), memid=str(par.get('MEMID', '')).lstrip('\\'))
        blackboxes[cn] = bb

    # clocks
    clk_count = {}
    for cn, t, kind, grp, con in flops_raw:
        ck = con.get('C', [None])[0]
        clk_count[(ck, grp[0])] = clk_count.get((ck, grp[0]), 0) + len(con.get('Q', []))
    ref = None
    if clock is not None:
        if clock not in c.ports:
            raise ChipError('clock port %r not found' % clock)
        ref = (c.ports[clock][1][0], 'P')
        if ref not in clk_count and (ref[0], 'N') in clk_count:
            ref = (ref[0], 'N')
    elif clk_count:
        ref = max(clk_count.items(), key=lambda kv: kv[1])[0]
    ticks = {}
    # Recognised clock gate: a latch that is transparent while the reference clock is low, ANDed with the reference
    # clock. The gated clock has an edge exactly in the cycles in which the latch input (the enable) is 1, so the
    # enable itself is the tick of that domain: no free value is needed.
    raw = m['cells']
    by_out = {}
    for cn, cell in raw.items():
        if cell.get('type') in ('$_AND_', '$_DLATCH_N_'):
            con = cell.get('connections') or {}
            o = (con.get('Y') or con.get('Q') or [None])[0]
            if isinstance(o, int): by_out[o] = (cn, cell)
    gated = {}
    for (ck, pol) in clk_count:
        if ref is None or (ck, pol) == ref or pol != 'P' or ref[1] != 'P' or ck not in by_out:
            continue
        cn, cell = by_out[ck]
        if cell['type'] != '$_AND_':
            continue
        a, b2 = cell['connections']['A'][0], cell['connections']['B'][0]
        other = a if b2 == ref[0] else (b2 if a == ref[0] else None)
        if other is None or other not in by_out or by_out[other][1]['type'] != '$_DLATCH_N_':
            continue
        lc = by_out[other][1]['connections']
        if lc['E'][0] != ref[0] or not isinstance(lc['D'][0], int):
            continue
        ticks[(ck, pol)] = lc['D'][0]
        gated[c.name(ck)] = dict(enable=c.name(lc['D'][0]), latch=by_out[other][0], flops=clk_count[(ck, pol)])
        if by_out[other][0] in blackboxes:
            blackboxes[by_out[other][0]]['role'] = 'clock-gate latch (modelled: the gated domain ticks when its enable is 1)'

    def tick(ck, pol):
        if (ck, pol) == ref:
            return None
        if (ck, pol) not in ticks:
            n = ch.new_net('$tick$%s%s' % (c.name(ck) if isinstance(ck, int) else ck, '' if pol == 'P' else '$neg'))
            c.inputs[n] = ('$free$tick', len(ticks))
            ch.free[n] = 'tick:%s' % (c.name(ck) if isinstance(ck, int) else ck)
            ticks[(ck, pol)] = n
        return ticks[(ck, pol)]

    def gate(op, fi, cn):
        n = ch.new_net()
        c.gates[n] = (op, tuple(fi))
        c.cell[n] = cn
        return n

    def lit(b, pol, cn):
        return b if pol == 'P' else gate(NOT, (b,), cn)

    n_arst = n_srst = n_en = n_plain = 0
    arst_nets = {}
    for cn, t, kind, grp, con in flops_raw:
        D, Q = con.get('D', []), con.get('Q', [])
        if len(D) != len(Q) or not Q:
            raise ChipError('flop %s (%s): D/Q missing' % (cn, t))
        ck = con.get('C', [None])[0]
        tk = tick(ck, grp[0])
        for i, (d, q) in enumerate(zip(D, Q)):
            driven(q, cn)
            d = fix(d, cn)
            name = cn if len(Q) == 1 else '%s[%d]' % (cn, i)
            rv = None
            late = None                       # asynchronous part: applied outside the clock tick
            if kind == 'plain':
                n_plain += 1
            elif kind == 'en':
                d = gate(MUX, (lit(fix(con['E'][0], cn), grp[1], cn), d, q), name); n_en += 1
            elif kind == 'srst':
                r = lit(fix(con['R'][0], cn), grp[1], cn); rv = grp[2] == '1'
                d = gate(MUX, (r, '1' if rv else '0', d), name)
            elif kind == 'srst_en':                    # reset wins over enable
                r = lit(fix(con['R'][0], cn), grp[1], cn); rv = grp[2] == '1'
                e = lit(fix(con['E'][0], cn), grp[3], cn)
                d = gate(MUX, (r, '1' if rv else '0', gate(MUX, (e, d, q), name)), name)
            elif kind == 'srst_ce':                    # enable gates the reset as well
                r = lit(fix(con['R'][0], cn), grp[1], cn); rv = grp[2] == '1'
                e = lit(fix(con['E'][0], cn), grp[3], cn)
                d = gate(MUX, (e, gate(MUX, (r, '1' if rv else '0', d), name), q), name)
            elif kind in ('arst', 'arst_en'):
                if kind == 'arst_en':
                    d = gate(MUX, (lit(fix(con['E'][0], cn), grp[3], cn), d, q), name)
                rv = grp[2] == '1'
                late = (lit(fix(con['R'][0], cn), grp[1], cn), '1' if rv else '0')
            elif kind in ('aload', 'aload_en'):
                if kind == 'aload_en':
                    d = gate(MUX, (lit(fix(con['E'][0], cn), grp[2], cn), d, q), name)
                late = (lit(fix(con['L'][0], cn), grp[1], cn), fix(con['AD'][i], cn))
            if kind.startswith('arst') or kind.startswith('aload'):
                n_arst += 1
                rn = con['R'][0] if 'R' in con else con['L'][0]
                arst_nets[rn] = arst_nets.get(rn, 0) + 1
            elif kind.startswith('srst'):
                n_srst += 1
            if tk is not None:
                d = gate(MUX, (tk, d, q), name)
            if late is not None:                       # async reset / load does not wait for the clock
                d = gate(MUX, (late[0], late[1], d), name)
            c.flops[q] = (d, False)
            c.cell[q] = name
            ch.sites.add(q)
            ch.flop_clock[q] = (ck, grp[0])
            ch.flop_type[q] = t
            if rv is not None:
                ch.reset_value[q] = rv

    # undriven nets that are read: free values (reported)
    undriven = 0
    for b, (op, fi) in list(c.gates.items()):
        for f in fi:
            if isinstance(f, int) and f not in c.gates and f not in c.flops and f not in c.inputs:
                c.inputs[f] = ('$free$undriven', undriven)
                ch.free[f] = 'undriven'
                undriven += 1
    for q, (d, _) in list(c.flops.items()):
        if isinstance(d, int) and d not in c.gates and d not in c.flops and d not in c.inputs:
            c.inputs[d] = ('$free$undriven', undriven)
            ch.free[d] = 'undriven'
            undriven += 1

    dom = {}
    for (ck, pol), n in clk_count.items():
        dom['%s%s' % (c.name(ck) if isinstance(ck, int) else str(ck), '' if pol == 'P' else ' (negative edge)')] = n
    ch.info = dict(
        top=top, cells=len(ch.sites), gates=len(ch.sites) - len(c.flops), flops=len(c.flops),
        primitive_gates=len(c.gates), cell_types=dict(sorted(counts.items())),
        input_bits=sum(1 for b, (p, i) in c.inputs.items() if not p.startswith('$free')),
        output_bits=sum(len(v[1]) for v in c.ports.values() if v[0] == 'output'),
        clock_domains=dict(sorted(dom.items(), key=lambda kv: -kv[1])),
        reference_clock=(c.name(ref[0]) if ref and isinstance(ref[0], int) else None),
        flops_off_reference_clock=sum(n for k, n in clk_count.items() if k != ref),
        clock_gates_modelled=gated,
        flops_on_free_tick_clocks=sum(n for k, n in clk_count.items() if k != ref and c.name(k[0]) not in gated),
        flops_plain=n_plain, flops_enable_only=n_en, flops_async_reset=n_arst, flops_sync_reset=n_srst,
        flops_with_initial=len([q for q in c.flops if q in ch.init_attr]),
        async_reset_nets={(c.name(k) if isinstance(k, int) else str(k)): v for k, v in arst_nets.items()},
        blackboxes=blackboxes, blackbox_output_bits=nfree, x_readers=len(xnets), undriven_bits=undriven,
        memory_bits_blackboxed=sum(b.get('words', 0) * b.get('width', 0) for b in blackboxes.values()),
    )
    return ch
