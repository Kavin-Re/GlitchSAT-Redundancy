"""Gate-level netlist -> GlitchSAT primitive circuit (AND, OR, XOR, NOT, MUX, D flip-flop).

Input: one flat module in Yosys JSON form (what `write_json` produces, or what `vnetlist.read` makes from structural
Verilog). Cells can be
  * Yosys internal gates and flip-flops ($_AND_ ... $_AOI4_, $_DFF_*, $_DFFE_*, $_SDFF*_, $_DFFSR*_),
  * standard cells of a Liberty library (functions read by `liberty.py`),
  * declared black boxes (their outputs become free inputs; reported as a coverage boundary),
  * $assert / $assume cells (they become properties, not logic).
Anything else stops the import with an error that names the cell: nothing is skipped silently.

Fault sites (the same for every flow and every library):
  * a combinational cell: one site per output pin (a standard cell with an internal network of primitives still has
    one site per output pin; the primitives inside are not sites);
  * a flip-flop: exactly one site, its STORED VALUE. The flop's output pins (Q, QN) and its own next-state logic
    (the hold path of an enable flop, e.g. $_DFFE_ or sky130 edfxtp) all read that value, so a flip persists until
    the flop loads a new value, exactly as a flipped Q does in a D flip-flop with an explicit hold multiplexer. The
    output pins are not separate sites. Asynchronous clear/preset still override the value while they are active.
Every Yosys flow ends with `dffunmap` (flows.NORMALISE), so enable and synchronous-reset logic of Yosys flops is
explicit gates (sites of their own) in every flow, as in the `plain` flow.
"""
import collections
import re

from . import liberty as LIB
from .errors import GSError

NATIVE = {'$_AND_': 'AND', '$_OR_': 'OR', '$_XOR_': 'XOR', '$_NOT_': 'NOT', '$_MUX_': 'MUX'}

# Functions of the other Yosys fine-grained gates (yosys/techlibs/common/simcells.v)
_YGATES = {
    '$_BUF_': ('A', 'A'), '$_NAND_': ('A B', '!(A&B)'), '$_NOR_': ('A B', '!(A|B)'), '$_XNOR_': ('A B', '!(A^B)'),
    '$_ANDNOT_': ('A B', 'A&!B'), '$_ORNOT_': ('A B', 'A|!B'), '$_NMUX_': ('A B S', '!((B&S)|(A&!S))'),
    '$_AOI3_': ('A B C', '!((A&B)|C)'), '$_OAI3_': ('A B C', '!((A|B)&C)'),
    '$_AOI4_': ('A B C D', '!((A&B)|(C&D))'), '$_OAI4_': ('A B C D', '!((A|B)&(C|D))'),
}


def _mk_cell(name, inputs, outputs, ff=None):
    c = LIB.Cell(name)
    c.inputs = list(inputs)
    c.outputs = {p: LIB.parse_expr(f) for p, f in outputs.items()}
    if ff:
        c.kind = 'ff'
        c.ff = ff
    return c


def _yosys_cells():
    cells = {}
    for t, (ins, f) in _YGATES.items():
        cells[t] = _mk_cell(t, ins.split(), {'Y': f})
    pol = lambda p, x: x if p == 'P' else '!' + x
    for C in 'PN':
        def ffd(nxt, clear=None, preset=None, ins=('C', 'D')):
            return dict(iq='IQ', iqn='IQN', next_state=LIB.parse_expr(nxt), clocked_on=LIB.parse_expr('C'),
                        clear=LIB.parse_expr(clear) if clear else None, preset=LIB.parse_expr(preset) if preset else None,
                        cpv1='L', cpv2='H', edge='pos' if C == 'P' else 'neg', clock_pin='C')
        cells['$_DFF_%s_' % C] = _mk_cell('$_DFF_%s_' % C, ['C', 'D'], {'Q': 'IQ'}, ffd('D'))
        for E in 'PN':
            cells['$_DFFE_%s%s_' % (C, E)] = _mk_cell('$_DFFE_%s%s_' % (C, E), ['C', 'D', 'E'], {'Q': 'IQ'},
                                                      ffd('(D&%s)|(IQ&!(%s))' % (pol(E, 'E'), pol(E, 'E'))))
        for R in 'PN':
            for V in '01':
                r = pol(R, 'R')
                kw = dict(clear=r) if V == '0' else dict(preset=r)
                cells['$_DFF_%s%s%s_' % (C, R, V)] = _mk_cell('$_DFF_%s%s%s_' % (C, R, V), ['C', 'D', 'R'], {'Q': 'IQ'}, ffd('D', **kw))
                cells['$_SDFF_%s%s%s_' % (C, R, V)] = _mk_cell('$_SDFF_%s%s%s_' % (C, R, V), ['C', 'D', 'R'], {'Q': 'IQ'},
                                                              ffd('(D&!(%s))|%s' % (r, r) if V == '1' else 'D&!(%s)' % r))
                for E in 'PN':
                    e = pol(E, 'E')
                    cells['$_DFFE_%s%s%s%s_' % (C, R, V, E)] = _mk_cell('$_DFFE_%s%s%s%s_' % (C, R, V, E), ['C', 'D', 'E', 'R'], {'Q': 'IQ'},
                                                                       ffd('(D&%s)|(IQ&!(%s))' % (e, e), **kw))
                    hold = '(D&%s)|(IQ&!(%s))' % (e, e)
                    rv = '1' if V == '1' else '0'
                    # $_SDFFE_: reset has priority over enable; $_SDFFCE_: reset only when enabled
                    cells['$_SDFFE_%s%s%s%s_' % (C, R, V, E)] = _mk_cell(
                        '$_SDFFE_%s%s%s%s_' % (C, R, V, E), ['C', 'D', 'E', 'R'], {'Q': 'IQ'},
                        ffd('(%s&%s)|(!(%s)&(%s))' % (r, rv, r, hold)))
                    cells['$_SDFFCE_%s%s%s%s_' % (C, R, V, E)] = _mk_cell(
                        '$_SDFFCE_%s%s%s%s_' % (C, R, V, E), ['C', 'D', 'E', 'R'], {'Q': 'IQ'},
                        ffd('(%s&((%s&%s)|(!(%s)&D)))|(!(%s)&IQ)' % (e, r, rv, r, e)))
        for S in 'PN':
            for R in 'PN':
                cells['$_DFFSR_%s%s%s_' % (C, S, R)] = _mk_cell('$_DFFSR_%s%s%s_' % (C, S, R), ['C', 'D', 'R', 'S'], {'Q': 'IQ'},
                                                               ffd('D', clear=pol(R, 'R'), preset=pol(S, 'S')))
                for E in 'PN':
                    e = pol(E, 'E')
                    cells['$_DFFSRE_%s%s%s%s_' % (C, S, R, E)] = _mk_cell(
                        '$_DFFSRE_%s%s%s%s_' % (C, S, R, E), ['C', 'D', 'E', 'R', 'S'], {'Q': 'IQ'},
                        ffd('(D&%s)|(IQ&!(%s))' % (e, e), clear=pol(R, 'R'), preset=pol(S, 'S')))
    # Yosys $_DFFSR_: reset has priority over set (simcells.v); clear_preset_var1 = L encodes that.
    return cells


YOSYS_CELLS = _yosys_cells()
REJECT = {'$_DLATCH_': 'latch', '$_SR_': 'set-reset latch', '$_ALDFF_': 'flip-flop with asynchronous load',
          '$mem': 'memory', '$mem_v2': 'memory', '$memrd': 'memory', '$memwr': 'memory'}


class Builder:
    """Wraps a gscale Circuit: fresh nets, gates, and per-cell bookkeeping."""

    def __init__(self, circ, first_free):
        self.c = circ
        self.next = first_free
        self.log = []                # nets created since the last mark

    def new(self):
        n = self.next; self.next += 1; return n

    def gate(self, op, fi):
        n = self.new()
        self.c.gates[n] = (op, tuple(fi))
        self.log.append(n)
        return n

    def is_gate(self, n):
        return n in self.c.gates

    def mark(self):
        self.log = []

    def rename(self, old, new):
        """Give the gate `old` (created since mark) the net id `new`; rewrite the references made since mark."""
        g = self.c.gates.pop(old)
        self.c.gates[new] = g
        for n in self.log:
            if n in self.c.gates:
                op, fi = self.c.gates[n]
                if old in fi:
                    self.c.gates[n] = (op, tuple(new if x == old else x for x in fi))
        for q, (d, i) in list(self.c.flops.items()):
            if d == old:
                self.c.flops[q] = (new, i)
        self.log = [new if x == old else x for x in self.log]


_JUNK = re.compile(r'[A-Za-z_]+\.(cc|h|v|sv):\d+(\.\d+-\d+\.\d+)?(:[A-Za-z_]+)?')


def _scope(cellname):
    """Hierarchy path of a flattened Yosys cell name: '$flatten\\u_a.\\u_b.$abc$..' -> 'u_a.u_b'."""
    s = _JUNK.sub('', cellname)
    if s.startswith('$flatten'):
        s = s[len('$flatten'):]
    s = s.replace('\\', '')
    parts = s.split('.')
    if len(parts) <= 1:
        return ''
    scope = [p for p in parts[:-1] if p and not p.startswith('$')]
    return '.'.join(scope)


def pretty_cell(cellname):
    sc = _scope(cellname)
    leaf = _JUNK.sub('', cellname).replace('\\', '').split('.')[-1]
    if leaf.startswith('$'):
        m = re.search(r'\$(\d+)$', leaf)
        leaf = '#' + (m.group(1) if m else '?')
    return (sc + '.' if sc else '') + leaf


class Imported:
    """Result of an import. circ: gscale Circuit (design only, flops with power-up value from `init`, None = unknown)."""

    def __init__(self):
        self.circ = None
        self.site_info = {}      # net -> dict(kind gate|flop, cell, type, scope, name, attrs)
        self.flop_init = {}      # stored-value net -> True/False/None
        self.flop_cell = {}      # stored-value net -> cell name
        self.clock_nets = set()
        self.edges = collections.Counter()
        self.blackbox_outputs = []   # (cell, pin, net)
        self.blackbox_inputs = []    # (cell, pin, net)
        self.asserts = []            # dict(kind assert|assume, a, en, cell, src)
        self.counts = collections.Counter()
        self.risks = collections.Counter()
        self.scan_enable_nets = set()
        self.skipped = collections.Counter()     # cell type -> number of cells without function (fillers, taps, ...)
        self.port_bits = {}
        self.stored = {}             # flop net -> its stored-value net (the flop's fault site)
        self.scan_flops = 0
        self.flop_pins = {}          # flop output-pin net -> flop net


def import_module(mod, top, lib=None, blackboxes=(), clock_ports=None, where='netlist', allow_x=False):
    """mod: Yosys JSON module dict. lib: liberty.Library or None. Returns Imported."""
    from .engine import gscale
    circuit = gscale().circuit
    c = circuit.Circuit()
    R = Imported()
    ports = mod.get('ports') or {}
    cells = mod.get('cells') or {}
    maxid = 1
    for p in ports.values():
        for b in p['bits']:
            if isinstance(b, int): maxid = max(maxid, b)
    for cv in cells.values():
        for v in (cv.get('connections') or {}).values():
            for b in v:
                if isinstance(b, int): maxid = max(maxid, b)
    for nn in (mod.get('netnames') or {}).values():
        for b in nn['bits']:
            if isinstance(b, int): maxid = max(maxid, b)
    B = Builder(c, maxid + 1)
    clock_ports = set(clock_ports or ())
    driven = {}
    for p, v in ports.items():
        c.ports[p] = (v['direction'], list(v['bits']))
        R.port_bits[p] = list(v['bits'])
        if v['direction'] == 'inout':
            raise GSError('GS031', 'port `%s` of `%s` is inout' % (p, top), help='inout (bidirectional) ports are not modelled; '
                          'split it into an input and an output in a small wrapper module, or leave it out of the analysis')
        if v['direction'] == 'input' and p not in clock_ports:
            for i, b in enumerate(v['bits']):
                if isinstance(b, int):
                    c.inputs[b] = (p, i); driven[b] = 'port ' + p
    # names
    for n, x in sorted((mod.get('netnames') or {}).items(), key=lambda kv: (kv[1].get('hide_name', 0), kv[0].startswith('$'), len(kv[0]), kv[0])):
        for i, b in enumerate(x['bits']):
            if isinstance(b, int) and b not in c.names:
                nm = n.replace('$flatten\\', '').replace('\\', '')
                c.names[b] = '%s[%d]' % (nm, i) if len(x['bits']) > 1 else nm
    init_of = {}
    for n, x in (mod.get('netnames') or {}).items():
        iv = (x.get('attributes') or {}).get('init')
        if iv is None:
            continue
        if isinstance(iv, int):
            iv = format(iv, 'b').zfill(len(x['bits']))
        iv = str(iv)
        for i, ch in enumerate(reversed(iv)):
            if i < len(x['bits']) and isinstance(x['bits'][i], int) and ch in '01':
                init_of[x['bits'][i]] = ch == '1'
    bb = set(blackboxes or ())

    def claim(net, cn):
        if not isinstance(net, int):
            raise GSError('GS032', 'cell `%s` drives a constant or unknown net %r' % (pretty_cell(cn), net))
        if net in driven:
            raise GSError('GS033', 'net `%s` has two drivers: %s and cell `%s`' % (c.name(net), driven[net], pretty_cell(cn)),
                          help='a gate-level netlist must have one driver per net; check for shorted outputs or a port '
                               'that is both driven inside and declared as an input')
        driven[net] = 'cell `%s`' % pretty_cell(cn)

    def conn(cv, pin):
        v = (cv.get('connections') or {}).get(pin)
        if v is None:
            return None
        if len(v) != 1:
            raise GSError('GS034', 'pin %s of a cell is %d bits wide; only 1-bit pins are modelled' % (pin, len(v)))
        b = v[0]
        if b in ('x', 'z'):
            return 'x'
        return b

    xnet = []

    def netval(b, cn, pin):
        if b == 'x' and allow_x:
            if not xnet:
                xnet.append(B.new()); c.inputs[xnet[0]] = ('__x__', 0); c.names[xnet[0]] = 'x (undefined)'
            return xnet[0]
        if b == 'x':
            raise GSError('GS035', 'pin %s of cell `%s` is connected to an undefined value (x/z)' % (pin, pretty_cell(cn)),
                          help='tie the pin to 0 or 1 in the design; an x would otherwise silently act as 0')
        return b

    for cn, cv in cells.items():
        t = cv.get('type')
        attrs = cv.get('attributes') or {}
        scope = _scope(cn)
        if t == '$scopeinfo':
            continue
        if t in ('$assert', '$assume', '$cover', '$live', '$fair', '$check'):
            if t in ('$assert', '$assume'):
                R.asserts.append(dict(kind=t[1:], a=conn(cv, 'A'), en=conn(cv, 'EN'), cell=cn, src=attrs.get('src', '')))
            R.counts[t] += 1
            continue
        if t in NATIVE:
            op = NATIVE[t]
            y = conn(cv, 'Y')
            claim(y, cn)
            if op == 'MUX':
                fi = (netval(conn(cv, 'S'), cn, 'S'), netval(conn(cv, 'B'), cn, 'B'), netval(conn(cv, 'A'), cn, 'A'))
            elif op == 'NOT':
                fi = (netval(conn(cv, 'A'), cn, 'A'),)
            else:
                fi = (netval(conn(cv, 'A'), cn, 'A'), netval(conn(cv, 'B'), cn, 'B'))
            c.gates[y] = (op, fi)
            R.site_info[y] = dict(kind='gate', cell=cn, type=t, scope=scope, attrs=attrs)
            R.counts['gate'] += 1
            continue
        if t in REJECT or t.startswith('$_DLATCH') or t.startswith('$_SR_') or t.startswith('$_ALDFF'):
            raise GSError('GS036', 'cell `%s` is a %s (%s)' % (pretty_cell(cn), REJECT.get(t, 'latch or async-load flop'), t),
                          help='only edge-triggered flip-flops and combinational gates are modelled. Latches usually come '
                               'from an incomplete `always @*` (add a default assignment); memories need `memory_map` '
                               '(the built-in flows run it)')
        cell = YOSYS_CELLS.get(t) or (lib.cells.get(t) if lib else None)
        if (t in bb or t.lstrip('\\') in bb) and t not in YOSYS_CELLS:     # a declared black box wins over the library
            dirs = cv.get('port_directions') or {}
            if not dirs:
                raise GSError('GS037', 'black box `%s` (instance `%s`) has no port directions' % (t, pretty_cell(cn)),
                              help='give a stub module (ports only) in `design.blackboxes[].stub` so the directions are known')
            for pin, bits in (cv.get('connections') or {}).items():
                for i, b in enumerate(bits):
                    if dirs.get(pin) == 'output':
                        claim(b, cn)
                        c.inputs[b] = ('%s.%s' % (pretty_cell(cn), pin), i)
                        R.blackbox_outputs.append((cn, '%s[%d]' % (pin, i) if len(bits) > 1 else pin, b))
                    else:
                        R.blackbox_inputs.append((cn, '%s[%d]' % (pin, i) if len(bits) > 1 else pin, b))
            R.counts['blackbox'] += 1
            continue
        if cell is None:
            if t.startswith('$'):
                raise GSError('GS038', 'cell `%s` has the Yosys type %s, which is not a gate-level cell' % (pretty_cell(cn), t),
                              help='the netlist is not fully mapped: run `techmap; opt_clean` (or use a built-in flow) before the analysis')
            raise GSError('GS039', 'cell type `%s` (instance `%s`) is not in any Liberty file and not a declared black box' % (t, pretty_cell(cn)),
                          help='add the standard-cell library under `design.liberty`, or declare the module under '
                               '`design.blackboxes` (its outputs then become free inputs and the report says so)')
        if cell.kind == 'none':
            R.skipped[t] += 1
            continue
        if cell.kind == 'unsupported':
            raise GSError('GS040', 'cell `%s` of type `%s` cannot be modelled: %s' % (pretty_cell(cn), t, cell.why),
                          help=('gated clocks are not modelled: synthesise without clock gating (no ICG cells) for the analysis'
                                if 'statetable' in str(cell.why) or 'clock' in str(cell.why) else
                                'use a synthesis flow without this cell (e.g. no latches), mark it `dont_use`, or declare its '
                                'module under `design.blackboxes` (its outputs then become free inputs)'))
        for r in cell.risks:
            R.risks[r] += 1
        scanned = False
        for sp in cell.scan_pins:
            v = conn(cv, sp)
            if v not in (None, '0', '1'):
                R.scan_enable_nets.add(v); scanned = True
        R.scan_flops += int(scanned)
        pins = {}
        for p in cell.inputs:
            v = conn(cv, p)
            if v is None:
                raise GSError('GS041', 'input pin %s of cell `%s` (%s) is not connected' % (p, pretty_cell(cn), t),
                              help='connect it or tie it to 0/1 in the netlist')
            pins[p] = v
        if cell.kind == 'ff':
            ck = pins.pop(cell.ff['clock_pin'])
            R.clock_nets.add(ck)
            R.edges[cell.ff['edge']] += 1
            for p, v in pins.items():
                pins[p] = netval(v, cn, p)
            q = B.new()
            B.mark()
            qf = B.gate('AND', (q, q))          # the stored value as seen by everything: the flop's one fault site
            d, outs = LIB.ff_parts(B, cell, pins, qf)
            c.flops[q] = (d, False)
            # power-up value: the netlist's init attribute on any output of the flop
            iv = None
            for p, a in cell.outputs.items():
                ob = conn(cv, p)
                if isinstance(ob, int) and ob in init_of:
                    iv = init_of[ob] if a == ('var', cell.ff['iq']) else (not init_of[ob] if a == ('var', cell.ff['iqn']) else iv)
            R.flop_init[q] = iv
            R.flop_cell[q] = cn
            R.counts['flop'] += 1
            kind = 'flop'
        else:
            for p, v in pins.items():
                pins[p] = netval(v, cn, p)
            B.mark()
            outs = LIB.map_comb(B, cell, pins)
            R.counts['gate'] += 1
            kind = 'gate'
        used = set()
        label_net = None
        for p, n in outs.items():
            ob = conn(cv, p)
            if ob is None:
                continue             # unconnected output pin: its logic stays dangling (not observed)
            claim(ob, cn)
            if n in used or n not in B.log or n == (qf if kind == 'flop' else None):
                n = B.gate('AND', (n, n))
            used.add(n)
            B.rename(n, ob)
            if kind == 'flop':
                R.flop_pins[ob] = q
                if label_net is None or cell.outputs[p] == ('var', cell.ff['iq']):
                    label_net = ob
            else:
                R.site_info[ob] = dict(kind=kind, cell=cn, type=t, scope=scope, pin=p, attrs=attrs)
        if kind == 'flop':
            R.site_info[qf] = dict(kind='flop', cell=cn, type=t, scope=scope, pin='stored', attrs=attrs, label_net=label_net)
            R.stored[q] = qf
            c.names.setdefault(q, ((c.names.get(conn(cv, 'Q')) if isinstance(conn(cv, 'Q'), int) else None) or pretty_cell(cn)) + ' (stored)')
    _check_driven(c, R, top)
    R.circ = c
    R.next_free = B.next
    return R


def _check_driven(c, R, top):
    """Every net a gate or flip-flop reads must be driven (GS044 instead of an engine traceback)."""
    drv = set(c.gates) | set(c.flops) | set(c.inputs) | {b for p, (d, bits) in c.ports.items() if d == 'input' for b in bits}
    used = [(f, 'gate') for y, (op, fi) in c.gates.items() for f in fi] + [(d, 'flip-flop') for q, (d, i) in c.flops.items()]
    for p, (d, bits) in c.ports.items():
        if d == 'output':
            used += [(b, 'output %s' % p) for b in bits]
    for n, who in used:
        if isinstance(n, int) and n not in drv:
            nm = c.names.get(n) or 'net %d' % n
            sc, _, leaf = str(nm).rpartition('.')
            raise GSError('GS044', 'net `%s` is used by a %s but is never driven' % (nm, who),
                          help='an output left unconnected or never assigned%s? Assign `%s` or tie it to 0/1'
                               % (' in instance `%s`' % sc if sc else ' in `%s`' % top, leaf or nm))


def stats(R):
    return dict(gate_cells=R.counts['gate'], flops=R.counts['flop'], primitives=len(R.circ.gates),
                blackboxes=R.counts['blackbox'], sites=len(R.site_info), skipped_no_function=dict(R.skipped))
