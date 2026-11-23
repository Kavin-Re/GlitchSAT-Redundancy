"""Flat gate-level netlists in the Yosys `write_json` shape used by scripts/glitchsat.py.

Cell types: $_AND_ $_OR_ $_XOR_ $_NOT_ $_MUX_ (pins A,B,[S],Y), also $_NAND_ $_NOR_ $_XNOR_ $_ANDNOT_ $_ORNOT_ $_BUF_ and $_DFF_P_ (pins C,D,Q). Net ids are integers >= 2;
the strings '0', '1', 'x' are constants. Nothing here needs Yosys, z3 or numpy.

`Builder` creates such netlists directly from Python (used by harden.spec to map a design description to gates) with
optional structural hashing, so that the amount of logic sharing is an explicit, documented modelling choice.
"""
import collections, hashlib, json

GATE_TYPES = ('$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_', '$_NAND_', '$_NOR_', '$_XNOR_', '$_ANDNOT_', '$_ORNOT_', '$_BUF_')
FLOP_TYPE = '$_DFF_P_'


class NetlistError(Exception):
    pass


class Netlist:
    """gates: {y: (type, a, b, s)} (b, s None when unused); flops: [(d, q, init)]; ports: {name: (dir, [bits])}."""

    def __init__(self, top='top'):
        self.top = top
        self.ports = collections.OrderedDict()
        self.gates = collections.OrderedDict()
        self.flops = []
        self.names = {}          # bit -> readable name
        self.cellnames = {}      # y or q -> cell name
        self.keep_cells = set()  # y bits whose cell carries keep=1 when written
        self.source = None

    # ---------------------------------------------------------------- loading / writing
    @classmethod
    def load(cls, path, top=None):
        with open(path) as f:
            j = json.load(f)
        mods = j.get('modules', {})
        if top is None:
            if len(mods) != 1:
                raise NetlistError(f'{path}: give --top (modules: {sorted(mods)})')
            top = next(iter(mods))
        if top not in mods:
            raise NetlistError(f'{path}: no module {top!r} (modules: {sorted(mods)})')
        m = mods[top]
        nl = cls(top)
        nl.source = path
        for pn, p in m.get('ports', {}).items():
            nl.ports[pn] = (p['direction'], list(p['bits']))
        for cn, c in m.get('cells', {}).items():
            t, con = c['type'], c['connections']
            if t == FLOP_TYPE:
                nl.flops.append([con['D'][0], con['Q'][0], 0])
                nl.cellnames[con['Q'][0]] = cn
            elif t in GATE_TYPES:
                y = con['Y'][0]
                nl.gates[y] = (t, con['A'][0], con['B'][0] if 'B' in con else None, con['S'][0] if 'S' in con else None)
                nl.cellnames[y] = cn
                if str(c.get('attributes', {}).get('keep', '0')).strip('0') not in ('',):
                    nl.keep_cells.add(y)
            else:
                raise NetlistError(f'{path}: unsupported cell type {t} (cell {cn}); supported: {GATE_TYPES + (FLOP_TYPE,)}')
        init = {}
        for n, x in m.get('netnames', {}).items():
            bits = x['bits']
            for i, b in enumerate(bits):
                if isinstance(b, int):
                    nm = f'{n}[{i}]' if len(bits) > 1 else n
                    old = nl.names.get(b)
                    if old is None or (old.startswith('$') and not nm.startswith('$')) or (x.get('hide_name', 0) == 0 and len(nm) < len(old) and not nm.startswith('$')):
                        nl.names[b] = nm
            iv = x.get('attributes', {}).get('init')
            if iv:
                for i, ch in enumerate(reversed(iv)):
                    if i < len(bits):
                        init[bits[i]] = 1 if ch == '1' else 0
        for f in nl.flops:
            f[2] = init.get(f[1], 0)
        nl.flops = [tuple(f) for f in nl.flops]
        return nl

    def to_json(self, creator='glitchsat harden (direct gate mapping, not Yosys output)'):
        cells, netnames = collections.OrderedDict(), collections.OrderedDict()
        clk = self.ports.get('clk', ('input', [None]))[1][0]
        for i, (d, q, init) in enumerate(self.flops):
            cn = self.cellnames.get(q, f'$dff${i}')
            cells[cn] = dict(hide_name=0, type=FLOP_TYPE, parameters={}, attributes={},
                             port_directions=dict(C='input', D='input', Q='output'),
                             connections=dict(C=[clk if clk is not None else '0'], D=[d], Q=[q]))
        for y, (t, a, b, s) in self.gates.items():
            cn = self.cellnames.get(y, f'$g${y}')
            con, pd = dict(A=[a]), dict(A='input')
            if b is not None:
                con['B'] = [b]; pd['B'] = 'input'
            if s is not None:
                con['S'] = [s]; pd['S'] = 'input'
            con['Y'] = [y]; pd['Y'] = 'output'
            cells[cn] = dict(hide_name=0, type=t, parameters={}, attributes=({'keep': '00000000000000000000000000000001'} if y in self.keep_cells else {}),
                             port_directions=pd, connections=con)
        initq = {q: init for _, q, init in self.flops}
        for b, n in sorted(self.names.items(), key=lambda kv: (str(kv[1]), kv[0])):
            at = {}
            if b in initq:
                at['init'] = '1' if initq[b] else '0'
            netnames[f'{n}'] = dict(hide_name=0, bits=[b], attributes=at)
        for q, init in initq.items():
            if q not in self.names:
                netnames[f'$q${q}'] = dict(hide_name=1, bits=[q], attributes={'init': '1' if init else '0'})
        ports = collections.OrderedDict((n, dict(direction=d, bits=list(bits))) for n, (d, bits) in self.ports.items())
        return dict(creator=creator, modules={self.top: dict(attributes={}, ports=ports, cells=cells, netnames=netnames)})

    def write(self, path, **kw):
        with open(path, 'w') as f:
            json.dump(self.to_json(**kw), f, indent=1)
        return path

    # ---------------------------------------------------------------- structure
    def input_bits(self, exclude=('clk',)):
        return [b for n, (d, bits) in self.ports.items() if d == 'input' and n not in exclude for b in bits if isinstance(b, int)]

    def fanins(self, y):
        t, a, b, s = self.gates[y]
        return [x for x in (a, b, s) if x is not None]

    def topo(self):
        """Gates in evaluation order (inputs before outputs). Raises on a combinational loop."""
        order, state = [], {}
        for root in self.gates:
            if root in state:
                continue
            stack = [(root, iter(self.fanins(root)))]
            state[root] = 1
            while stack:
                y, it = stack[-1]
                for x in it:
                    if x in self.gates:
                        st = state.get(x)
                        if st == 1:
                            raise NetlistError('combinational loop')
                        if st is None:
                            state[x] = 1
                            stack.append((x, iter(self.fanins(x))))
                            break
                else:
                    state[y] = 2
                    order.append(y)
                    stack.pop()
        return order

    def readers(self):
        """bit -> list of ('gate', y) / ('flop', q) / ('port', name) that read it."""
        r = collections.defaultdict(list)
        for y in self.gates:
            for x in set(self.fanins(y)):
                r[x].append(('gate', y))
        for d, q, _ in self.flops:
            r[d].append(('flop', q))
        for n, (dr, bits) in self.ports.items():
            if dr == 'output':
                for b in bits:
                    r[b].append(('port', n))
        return r

    def depth(self):
        """Longest gate path between flop Q / input and flop D / output (gate levels)."""
        dep = {}
        for y in self.topo():
            dep[y] = 1 + max([dep.get(x, 0) for x in self.fanins(y)] or [0])
        ends = [d for d, _, _ in self.flops] + [b for n, (dr, bits) in self.ports.items() if dr == 'output' for b in bits]
        return max([dep.get(e, 0) for e in ends] or [0])

    def stats(self):
        hist = collections.Counter(t for t, _, _, _ in self.gates.values())
        return dict(gates=len(self.gates), flops=len(self.flops), depth=self.depth(),
                    hist={k.strip('$_'): v for k, v in sorted(hist.items())})

    def name(self, b):
        return self.names.get(b, str(b))

    def sha256(self):
        return hashlib.sha256(json.dumps(self.to_json(), sort_keys=True).encode()).hexdigest()

    def copy(self):
        n = Netlist(self.top)
        n.ports = collections.OrderedDict((k, (d, list(b))) for k, (d, b) in self.ports.items())
        n.gates = collections.OrderedDict(self.gates)
        n.flops = list(self.flops)
        n.names = dict(self.names)
        n.cellnames = dict(self.cellnames)
        n.keep_cells = set(self.keep_cells)
        n.source = self.source
        return n

    def max_bit(self):
        m = 1
        for y, (t, a, b, s) in self.gates.items():
            for x in (y, a, b, s):
                if isinstance(x, int):
                    m = max(m, x)
        for d, q, _ in self.flops:
            for x in (d, q):
                if isinstance(x, int):
                    m = max(m, x)
        for _, bits in self.ports.values():
            for x in bits:
                if isinstance(x, int):
                    m = max(m, x)
        return m

    def to_verilog(self, module=None, keep=True, header=''):
        """Structural Verilog of exactly this netlist (one assign per gate). With keep=True every gate output wire
        carries (* keep *) so that the nets survive as named ports of the ABC step (it does not stop restructuring)."""
        module = module or self.top
        w = lambda b: {'0': "1'b0", '1': "1'b1", 'x': "1'b0"}.get(b) if isinstance(b, str) else f'n{b}'
        L = [header.rstrip('\n')] if header else []
        pl = []
        for n, (d, bits) in self.ports.items():
            rng = f'[{len(bits) - 1}:0] ' if len(bits) > 1 else ''
            pl.append(f'{d} {rng}{n}')
        L.append(f'module {module}({", ".join(pl)});')
        inb = {}
        for n, (d, bits) in self.ports.items():
            if d == 'input':
                for i, b in enumerate(bits):
                    inb[b] = f'{n}[{i}]' if len(bits) > 1 else n
        ww = lambda b: inb.get(b) or w(b)
        clk = 'clk' if 'clk' in self.ports else None
        for d, q, init in self.flops:
            L.append(f'  (* keep *) reg n{q}; initial n{q} = 1\'b{init};   // {self.name(q)}')
        for y in self.topo():
            t, a, b, s = self.gates[y]
            e = {'$_AND_': lambda: f'{ww(a)} & {ww(b)}', '$_OR_': lambda: f'{ww(a)} | {ww(b)}', '$_XOR_': lambda: f'{ww(a)} ^ {ww(b)}',
                 '$_NOT_': lambda: f'~{ww(a)}', '$_MUX_': lambda: f'{ww(s)} ? {ww(b)} : {ww(a)}',
                 '$_NAND_': lambda: f'~({ww(a)} & {ww(b)})', '$_NOR_': lambda: f'~({ww(a)} | {ww(b)})', '$_XNOR_': lambda: f'~({ww(a)} ^ {ww(b)})',
                 '$_ANDNOT_': lambda: f'{ww(a)} & ~{ww(b)}', '$_ORNOT_': lambda: f'{ww(a)} | ~{ww(b)}', '$_BUF_': lambda: f'{ww(a)}'}[t]()
            L.append(f'  {"(* keep *) " if keep else ""}wire n{y} = {e};   // {self.name(y)}')
        if self.flops:
            L.append(f'  always @(posedge {clk or "clk"}) begin')
            for d, q, _ in self.flops:
                L.append(f'    n{q} <= {ww(d)};')
            L.append('  end')
        for n, (d, bits) in self.ports.items():
            if d == 'output':
                if len(bits) > 1:
                    L.append(f'  assign {n} = {{{", ".join(ww(b) for b in reversed(bits))}}};')
                else:
                    L.append(f'  assign {n} = {ww(bits[0])};')
        L.append('endmodule')
        return '\n'.join(L) + '\n'


class Builder:
    """Build a Netlist gate by gate.

    share: 'scope'  structural hashing inside each scope (identical gate on identical inputs is created once). Scopes
                    model blocks that the flow keeps apart (a kept module instance); the top level is one scope.
                    This is the pessimistic default: every sharing an optimiser could get by hashing is present.
           'all'    structural hashing across scopes too: models `opt_merge` after flatten (copies collapse).
           'none'   no hashing: each use builds its own gates (optimistic: nothing is shared).
    Constants are always folded."""

    def __init__(self, top, share='scope'):
        assert share in ('scope', 'all', 'none')
        self.nl = Netlist(top)
        self.share = share
        self._next = 2
        self._hash = {}
        self._scope = ''
        self._uid = 0
        self.scope_of = {}     # gate bit -> scope label ('' = top)

    def _new(self, name=None):
        b = self._next
        self._next += 1
        if name:
            self.nl.names[b] = name
        return b

    def input(self, name, width=1):
        bits = [self._new(f'{name}[{i}]' if width > 1 else name) for i in range(width)]
        self.nl.ports[name] = ('input', bits)
        return bits

    def output(self, name, bits):
        self.nl.ports[name] = ('output', list(bits))

    def flop(self, name, init):
        q = self._new(name)
        self.nl.flops.append([None, q, int(init)])
        self.nl.cellnames[q] = f'$dff${name}'
        return q

    def set_d(self, q, d):
        for f in self.nl.flops:
            if f[1] == q:
                f[0] = d
                return
        raise KeyError(q)

    class _Scope:
        def __init__(s, b, label):
            s.b, s.label, s.prev = b, label, None

        def __enter__(s):
            s.prev = s.b._scope
            s.b._scope = s.label

        def __exit__(s, *a):
            s.b._scope = s.prev

    def scope(self, label):
        return Builder._Scope(self, label)

    def _gate(self, t, a, b=None, s=None, name=None):
        if t in ('$_AND_', '$_OR_', '$_XOR_') and str(b) < str(a):
            a, b = b, a
        key = (t, a, b, s) if self.share == 'all' else (self._scope, t, a, b, s)
        if self.share != 'none' and key in self._hash:
            return self._hash[key]
        self._uid += 1
        pre = (self._scope + '.') if self._scope else ''
        y = self._new(name or f'{pre}{t.strip("$_").lower()}{self._uid}')
        self.nl.gates[y] = (t, a, b, s)
        self.nl.cellnames[y] = f'{pre}$g${self._uid}'
        self.scope_of[y] = self._scope
        if self.share != 'none':
            self._hash[key] = y
        return y

    def NOT(self, a):
        if a == '0': return '1'
        if a == '1': return '0'
        g = self.nl.gates.get(a)
        if g and g[0] == '$_NOT_' and self.share != 'none':
            return g[1]
        return self._gate('$_NOT_', a)

    def AND(self, a, b):
        if a == '0' or b == '0': return '0'
        if a == '1': return b
        if b == '1': return a
        if a == b: return a
        return self._gate('$_AND_', a, b)

    def OR(self, a, b):
        if a == '1' or b == '1': return '1'
        if a == '0': return b
        if b == '0': return a
        if a == b: return a
        return self._gate('$_OR_', a, b)

    def XOR(self, a, b):
        if a == '0': return b
        if b == '0': return a
        if a == '1': return self.NOT(b)
        if b == '1': return self.NOT(a)
        if a == b: return '0'
        return self._gate('$_XOR_', a, b)

    def MUX(self, s, a0, b1):
        """s ? b1 : a0"""
        if s == '0': return a0
        if s == '1': return b1
        if a0 == b1: return a0
        if a0 == '0' and b1 == '1': return s
        if a0 == '1' and b1 == '0': return self.NOT(s)
        if a0 == '0': return self.AND(s, b1)
        if b1 == '0': return self.AND(self.NOT(s), a0)
        if a0 == '1': return self.OR(self.NOT(s), b1)
        if b1 == '1': return self.OR(s, a0)
        return self._gate('$_MUX_', a0, b1, s)

    def tree(self, op, xs):
        xs = list(xs)
        if not xs:
            return '1' if op == 'and' else '0'
        f = self.AND if op == 'and' else self.OR
        while len(xs) > 1:
            xs = [f(xs[i], xs[i + 1]) if i + 1 < len(xs) else xs[i] for i in range(0, len(xs), 2)]
        return xs[0]

    def eq_const(self, bits, value):
        return self.tree('and', [b if (value >> i) & 1 else self.NOT(b) for i, b in enumerate(bits)])

    def rename(self, bit, name):
        if isinstance(bit, int):
            self.nl.names[bit] = name

    def finish(self):
        nl = self.nl
        nl.flops = [tuple(f) for f in nl.flops]
        for d, q, _ in nl.flops:
            if d is None:
                raise NetlistError(f'flop {nl.name(q)} has no D')
        # drop gates that reach neither a flop D nor an output (constant folding can leave some)
        live, stack = set(), [d for d, _, _ in nl.flops] + [b for _, (dr, bits) in nl.ports.items() if dr == 'output' for b in bits]
        while stack:
            x = stack.pop()
            if x in nl.gates and x not in live:
                live.add(x)
                stack.extend(nl.fanins(x))
        for y in [y for y in nl.gates if y not in live]:
            del nl.gates[y]
            nl.names.pop(y, None); nl.cellnames.pop(y, None)
        return nl
