"""Liberty (.lib) reader: cell functions for GlitchSAT.

What is read, per cell:
  pin(...) { direction; function; three_state }      combinational outputs
  ff(IQ, IQN) { next_state; clocked_on; clear; preset; clear_preset_var1/2 }   edge-triggered flip-flops
  latch, statetable, ff_bank, clock_gating_integrated_cell, test_cell, retention_cell, bus/bundle pins
                                                      recognised and reported (not modelled; see `kind`/`risks`)
Everything else (timing, power, noise tables) is skipped without being interpreted.

The reader never copies the Liberty file anywhere. It keeps only the parsed cell functions in memory.

Function syntax (Liberty reference): operators ' (postfix NOT), ! (prefix NOT), ^ (XOR), & * or a space (AND),
| + (OR), parentheses, constants 0 and 1. Precedence used here, highest first: ' and !, ^, AND, OR.
Every cell used by a netlist is checked by exhaustive truth table: the gate network built from the function
(`map_cell`) against a direct evaluation of the parsed Liberty attributes (`eval_*`), see `verify_cell`.
"""
import gzip
import itertools
import os
import re

# ------------------------------------------------------------------ low-level parser

_SKIP_GROUPS = {'timing', 'internal_power', 'leakage_power', 'receiver_capacitance', 'output_current_rise',
                'output_current_fall', 'ccsn_first_stage', 'ccsn_last_stage', 'lu_table_template', 'power_lut_template',
                'output_current_template', 'normalized_driver_waveform', 'operating_conditions', 'wire_load',
                'wire_load_selection', 'dynamic_current', 'intrinsic_parasitic', 'leakage_current', 'gate_leakage',
                'pin_capacitance', 'max_cap', 'min_pulse_width', 'minimum_period', 'tlatch', 'noise_lut_template',
                'propagation_lut_template', 'iv_lut_template', 'base_curves', 'compact_lut_template', 'pg_pin',
                'em_lut_template', 'electromigration', 'fall_capacitance_range', 'rise_capacitance_range',
                'input_voltage', 'output_voltage', 'power_supply', 'voltage_map', 'type'}


class LibertyError(Exception):
    pass


class Group:
    __slots__ = ('name', 'args', 'attrs', 'groups', 'line')

    def __init__(self, name, args, line):
        self.name, self.args, self.attrs, self.groups, self.line = name, args, {}, [], line

    def sub(self, name):
        return [g for g in self.groups if g.name == name]

    def get(self, key, default=None):
        return self.attrs.get(key, default)


_TOK = re.compile(r'\s+|/\*.*?\*/|//[^\n]*|\\\n|"(?:[^"\\]|\\.)*"|[(){}:;,]|[^\s(){}:;,"]+', re.S)


def _strip(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1]
    return v.replace('\\\n', ' ')


def parse_text(text, path='<liberty>'):
    """Parse Liberty text into a Group tree (top group = library)."""
    pos = 0
    n = len(text)
    line = [1]

    def toks():
        nonlocal pos
        while pos < n:
            m = _TOK.match(text, pos)
            if not m:
                raise LibertyError('%s:%d: cannot read character %r' % (path, line[0], text[pos]))
            s = m.group(0)
            line[0] += s.count('\n')
            pos = m.end()
            c = s[0]
            if c.isspace() or s.startswith('/*') or s.startswith('//') or s == '\\\n':
                continue
            yield s

    it = toks()
    root = Group('<root>', [], 1)
    stack = [root]
    pending = []          # tokens of the current statement

    def skip_group():
        """Skip a group body (after its '{') with a fast brace scan (strings and comments respected)."""
        nonlocal pos
        depth = 1
        rx = re.compile(r'"(?:[^"\\]|\\.)*"|/\*.*?\*/|[{}]', re.S)
        while depth:
            m = rx.search(text, pos)
            if not m:
                raise LibertyError('%s: unbalanced braces' % path)
            s = m.group(0)
            line[0] += text.count('\n', pos, m.end())
            pos = m.end()
            if s == '{':
                depth += 1
            elif s == '}':
                depth -= 1

    for t in it:
        if t == '{':
            # pending: name ( args )
            if not pending:
                raise LibertyError('%s:%d: "{" without a group name' % (path, line[0]))
            name = pending[0]
            args = []
            if '(' in pending:
                i = pending.index('(')
                j = len(pending) - 1 - pending[::-1].index(')') if ')' in pending else len(pending)
                args = _split_args(pending[i + 1:j])
            pending = []
            if name in _SKIP_GROUPS and len(stack) > 1:
                skip_group()
                continue
            g = Group(name, args, line[0])
            stack[-1].groups.append(g)
            stack.append(g)
        elif t == '}':
            if pending:
                _attr(stack[-1], pending, path, line[0])
                pending = []
            if len(stack) == 1:
                raise LibertyError('%s:%d: unexpected "}"' % (path, line[0]))
            stack.pop()
        elif t == ';':
            if pending:
                _attr(stack[-1], pending, path, line[0])
            pending = []
        else:
            pending.append(t)
    if len(stack) != 1:
        raise LibertyError('%s: file ends inside group %r (missing "}")' % (path, stack[-1].name))
    libs = root.sub('library')
    if not libs:
        raise LibertyError('%s: no library(...) group found; is this a Liberty file?' % path)
    return libs[0]


def _split_args(toks):
    out, cur = [], []
    for x in toks:
        if x == ',':
            out.append(' '.join(cur)); cur = []
        else:
            cur.append(x)
    if cur:
        out.append(' '.join(cur))
    return [_strip(a) for a in out if a.strip()]


def _attr(g, toks, path, line):
    if len(toks) >= 2 and toks[1] == ':':
        g.attrs[toks[0]] = _strip(' '.join(toks[2:]))
    elif len(toks) >= 2 and toks[1] == '(':
        j = len(toks) - 1 - toks[::-1].index(')') if ')' in toks else len(toks)
        g.attrs.setdefault(toks[0], _split_args(toks[2:j]))
    # anything else is ignored (e.g. stray tokens in skipped tables)


def read_file(path):
    op = gzip.open if path.endswith('.gz') else open
    try:
        with op(path, 'rt', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError as e:
        raise LibertyError('cannot read Liberty file %s: %s' % (path, e))
    return parse_text(text, path)


# ------------------------------------------------------------------ function expressions

class ExprError(LibertyError):
    pass


_ETOK = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_\[\]\.]*|[01]\b|[!'&*|+^()])")


def parse_expr(s):
    """Liberty boolean function -> AST: ('var', n) ('const', b) ('not', a) ('and', a, b) ('or', a, b) ('xor', a, b)."""
    toks = []
    pos = 0
    s = s.strip()
    while pos < len(s):
        m = _ETOK.match(s, pos)
        if not m:
            if s[pos:].strip() == '':
                break
            raise ExprError('cannot read function %r at %r' % (s, s[pos:]))
        toks.append(m.group(1))
        pos = m.end()
    i = [0]

    def peek():
        return toks[i[0]] if i[0] < len(toks) else None

    def take():
        t = toks[i[0]]; i[0] += 1; return t

    def starts_primary(t):
        return t is not None and (t == '(' or t == '!' or t in ('0', '1') or re.match(r'[A-Za-z_]', t))

    def p_or():
        a = p_and()
        while peek() in ('|', '+'):
            take(); a = ('or', a, p_and())
        return a

    def p_and():
        a = p_xor()
        while True:
            t = peek()
            if t in ('&', '*'):
                take(); a = ('and', a, p_xor())
            elif starts_primary(t):
                a = ('and', a, p_xor())       # juxtaposition = AND
            else:
                return a

    def p_xor():
        a = p_un()
        while peek() == '^':
            take(); a = ('xor', a, p_un())
        return a

    def p_un():
        t = peek()
        if t == '!':
            take(); a = ('not', p_un())
        else:
            a = p_prim()
        while peek() == "'":
            take(); a = ('not', a)
        return a

    def p_prim():
        t = peek()
        if t is None:
            raise ExprError('function %r ends early' % s)
        take()
        if t == '(':
            a = p_or()
            if peek() != ')':
                raise ExprError('missing ")" in function %r' % s)
            take(); return a
        if t in ('0', '1'):
            return ('const', int(t))
        if re.match(r'[A-Za-z_]', t):
            return ('var', t)
        raise ExprError('unexpected %r in function %r' % (t, s))
    if not toks:
        raise ExprError('empty function')
    a = p_or()
    if i[0] != len(toks):
        raise ExprError('extra text %r in function %r' % (' '.join(toks[i[0]:]), s))
    return a


def expr_vars(a, out=None):
    out = set() if out is None else out
    if a[0] == 'var':
        out.add(a[1])
    elif a[0] != 'const':
        for x in a[1:]:
            expr_vars(x, out)
    return out


def eval_expr(a, env):
    op = a[0]
    if op == 'var':
        return bool(env[a[1]])
    if op == 'const':
        return bool(a[1])
    if op == 'not':
        return not eval_expr(a[1], env)
    x, y = eval_expr(a[1], env), eval_expr(a[2], env)
    return (x and y) if op == 'and' else (x or y) if op == 'or' else (x != y)


def expr_str(a):
    op = a[0]
    if op == 'var': return a[1]
    if op == 'const': return str(a[1])
    if op == 'not': return '!' + expr_str(a[1])
    sym = {'and': '&', 'or': '|', 'xor': '^'}[op]
    return '(%s %s %s)' % (expr_str(a[1]), sym, expr_str(a[2]))


# ------------------------------------------------------------------ cells

class Cell:
    """kind: 'comb' | 'ff' | 'none' (no function output: filler, tap, decap, diode) | 'unsupported'."""

    def __init__(self, name):
        self.name = name
        self.inputs, self.outputs = [], {}       # outputs: pin -> AST (over inputs, and IQ/IQN for ff cells)
        self.kind = 'comb'
        self.ff = None                           # dict(iq, iqn, next_state, clocked_on, clear, preset, cpv1, cpv2)
        self.why = ''                            # reason when unsupported
        self.risks = []                          # scan, clock gating, retention, ... (plain words)
        self.scan_pins = []                      # scan enable pins (functional mode: tie to 0)
        self.attrs = {}

    def to_json(self):
        d = dict(name=self.name, kind=self.kind, inputs=self.inputs, outputs={p: expr_str(a) for p, a in self.outputs.items()},
                 risks=self.risks, why=self.why)
        if self.ff:
            d['ff'] = {k: (expr_str(v) if isinstance(v, tuple) else v) for k, v in self.ff.items()}
        return d


class Library:
    def __init__(self, name, path, cells):
        self.name, self.path, self.cells = name, path, cells

    def __contains__(self, c):
        return c in self.cells

    def summary(self):
        kinds = {}
        for c in self.cells.values():
            kinds[c.kind] = kinds.get(c.kind, 0) + 1
        return dict(library=self.name, cells=len(self.cells), kinds=kinds,
                    risks=sorted({r for c in self.cells.values() for r in c.risks}))


_SCAN_EN = re.compile(r'^(SE|SCE|TE|SCAN_EN|SCANEN|SEN|TEST_EN)$', re.I)


def _cell_from_group(g):
    c = Cell(g.args[0] if g.args else '?')
    c.attrs = {k: v for k, v in g.attrs.items() if k in ('area', 'dont_use', 'is_filler_cell', 'is_tap_cell', 'is_decap_cell',
                                                         'is_level_shifter', 'is_isolation_cell', 'clock_gating_integrated_cell',
                                                         'retention_cell', 'cell_footprint')}
    if g.get('clock_gating_integrated_cell'):
        c.risks.append('clock-gating cell (%s)' % g.get('clock_gating_integrated_cell'))
    if g.get('retention_cell') or g.sub('retention_condition'):
        c.risks.append('retention cell (power-gating behaviour is not modelled)')
    pins = []
    for p in g.sub('pin'):
        for nm in p.args:
            pins.append((nm, p))
    if g.sub('bus') or g.sub('bundle'):
        c.kind, c.why = 'unsupported', 'bus or bundle pins (multibit cell)'
        c.risks.append('multibit cell')
    if g.sub('ff_bank'):
        c.kind, c.why = 'unsupported', 'ff_bank (multibit flip-flop)'
        c.risks.append('multibit flip-flop')
    if g.sub('latch') or g.sub('latch_bank'):
        c.kind, c.why = 'unsupported', 'latch (level-sensitive storage is not modelled; only edge-triggered flip-flops are)'
    if g.sub('statetable'):
        c.kind, c.why = 'unsupported', 'statetable (state described as a table; typical for clock-gating cells)'
    if g.sub('test_cell'):
        c.risks.append('scan flip-flop (scan enable is a fixed functional-mode input by default)')
    outs = {}
    for nm, p in pins:
        d = (p.get('direction') or '').lower()
        if d == 'input':
            c.inputs.append(nm)
            if _SCAN_EN.match(nm) or p.get('signal_type') in ('test_scan_enable', 'test_scan_enable_inverted'):
                c.scan_pins.append(nm)
        elif d in ('output', 'inout'):
            if p.get('three_state'):
                if c.kind != 'unsupported':
                    c.kind, c.why = 'unsupported', 'three-state output %s (tri-state buses are not modelled)' % nm
            f = p.get('function')
            if f is not None:
                outs[nm] = f
            elif d == 'output' and p.get('state_function'):
                outs[nm] = p.get('state_function')
            if d == 'inout' and c.kind != 'unsupported':
                c.kind, c.why = 'unsupported', 'inout pin %s' % nm
    if c.scan_pins and not any('scan' in r for r in c.risks):
        c.risks.append('scan flip-flop (scan enable is a fixed functional-mode input by default)')
    ffs = g.sub('ff')
    if c.kind != 'unsupported' and ffs:
        if len(ffs) > 1:
            c.kind, c.why = 'unsupported', 'more than one ff group'
        else:
            f = ffs[0]
            iq = f.args[0] if f.args else 'IQ'
            iqn = f.args[1] if len(f.args) > 1 else 'IQN'
            try:
                ff = dict(iq=iq, iqn=iqn, next_state=parse_expr(f.get('next_state', '')),
                          clocked_on=parse_expr(f.get('clocked_on', '')),
                          clear=parse_expr(f.get('clear')) if f.get('clear') else None,
                          preset=parse_expr(f.get('preset')) if f.get('preset') else None,
                          cpv1=f.get('clear_preset_var1'), cpv2=f.get('clear_preset_var2'))
            except ExprError as e:
                c.kind, c.why = 'unsupported', 'ff group: %s' % e
                ff = None
            if ff:
                if f.get('clocked_on_also') or f.get('next_state') is None:
                    c.kind, c.why = 'unsupported', 'ff group without next_state or with clocked_on_also (master-slave)'
                else:
                    ck = ff['clocked_on']
                    if ck[0] == 'var':
                        ff['edge'] = 'pos'; ff['clock_pin'] = ck[1]
                    elif ck[0] == 'not' and ck[1][0] == 'var':
                        ff['edge'] = 'neg'; ff['clock_pin'] = ck[1][1]
                    else:
                        c.kind, c.why = 'unsupported', 'clocked_on %r is not a single pin (gated clock)' % expr_str(ck)
                    for v in ('cpv1', 'cpv2'):
                        if ff[v] not in (None, 'L', 'H') and ff['clear'] is not None and ff['preset'] is not None:
                            c.kind, c.why = 'unsupported', 'clear_preset_var %s (only L and H are modelled)' % ff[v]
                    if c.kind != 'unsupported':
                        c.kind = 'ff'
                        c.ff = ff
    try:
        for nm, f in outs.items():
            c.outputs[nm] = parse_expr(f)
    except ExprError as e:
        c.kind, c.why = 'unsupported', 'function of %s: %s' % (nm, e)
    if c.kind == 'comb' and not c.outputs:
        c.kind = 'none'
        c.why = 'no output with a function (filler, tap, decap, antenna diode or similar)'
    if c.kind in ('comb', 'ff'):
        allowed = set(c.inputs) | ({c.ff['iq'], c.ff['iqn']} if c.ff else set())
        for nm, a in c.outputs.items():
            bad = expr_vars(a) - allowed
            if bad:
                c.kind, c.why = 'unsupported', 'function of %s uses %s, which is not an input pin' % (nm, ', '.join(sorted(bad)))
                break
        if c.ff:
            for k in ('next_state', 'clocked_on', 'clear', 'preset'):
                if c.ff.get(k) is not None and expr_vars(c.ff[k]) - set(c.inputs) - {c.ff['iq'], c.ff['iqn']}:
                    c.kind, c.why = 'unsupported', 'ff %s uses an unknown pin' % k
    return c


def load(path):
    """Library object with every cell of a Liberty file (.lib or .lib.gz)."""
    lib = read_file(path)
    cells = {}
    for g in lib.sub('cell'):
        c = _cell_from_group(g)
        cells[c.name] = c
    return Library(lib.args[0] if lib.args else os.path.basename(path), path, cells)


def load_many(paths):
    cells, names = {}, []
    for p in paths:
        L = load(p)
        names.append(L.name)
        for k, v in L.cells.items():
            cells.setdefault(k, v)
    return Library('+'.join(names), ';'.join(paths), cells)


# ------------------------------------------------------------------ mapping to the engine's primitives
#
# A builder `b` must provide: b.gate(op, fanins) -> net, op in AND OR XOR NOT MUX (MUX fanins = (s, then, else));
# b.flop(d, init) -> q net is created by the netlist layer (flops need power-up handling), not here.

def build_expr(b, a, env, memo=None):
    """Gates for AST a; env maps pin names to nets (or '0'/'1'). Returns a net or a constant '0'/'1'."""
    memo = {} if memo is None else memo
    key = a
    if key in memo:
        return memo[key]
    op = a[0]
    if op == 'var':
        r = env[a[1]]
    elif op == 'const':
        r = '1' if a[1] else '0'
    elif op == 'not':
        x = build_expr(b, a[1], env, memo)
        r = '1' if x == '0' else '0' if x == '1' else b.gate('NOT', (x,))
    else:
        x, y = build_expr(b, a[1], env, memo), build_expr(b, a[2], env, memo)
        r = b.gate({'and': 'AND', 'or': 'OR', 'xor': 'XOR'}[op], (x, y))
    memo[key] = r
    return r


def as_site(b, net):
    """A net that is a gate output, so it can carry a fault: a buffer (AND(x, x)) when net is an input pin or a constant."""
    return b.gate('AND', (net, net))


def map_comb(b, cell, pin_nets):
    """Combinational cell -> {output pin: net}. Each output net is a gate output (one fault site per output pin)."""
    env = dict(pin_nets)
    out = {}
    for p, a in cell.outputs.items():
        n = build_expr(b, a, env, {})
        if n in ('0', '1') or not b.is_gate(n) or n in env.values():
            n = as_site(b, n)
        out[p] = n
    return out


def ff_parts(b, cell, pin_nets, q_reg):
    """Flip-flop cell around a stored-value net q_reg (a flop the caller owns).
    Returns (d_net, {output pin: net}). Semantics per cycle (inputs change only at clock edges):
      forced = clear & preset ? cpv : clear ? 0 : preset ? 1 : none
      IQ     = forced if forced else stored value          (asynchronous clear/preset act within the cycle)
      stored' = forced if forced else next_state          (value captured at the clock edge)
    """
    f = cell.ff
    env = dict(pin_nets)
    clr = build_expr(b, f['clear'], env) if f['clear'] is not None else '0'
    pre = build_expr(b, f['preset'], env) if f['preset'] is not None else '0'
    nxt = build_expr(b, f['next_state'], dict(env, **{f['iq']: q_reg}))   # next_state may read IQ (enable flops)

    def forced(normal, var_val):
        # var_val: value when clear and preset are both active
        v = normal
        v = _mux(b, pre, '1', v)
        v = _mux(b, clr, '0', v)
        if clr != '0' and pre != '0' and var_val is not None:
            both = b.gate('AND', (clr, pre))
            v = _mux(b, both, var_val, v)
        return v
    v1 = {'L': '0', 'H': '1'}.get(f['cpv1'], '0' if f['clear'] is not None else None)
    v2 = {'L': '0', 'H': '1'}.get(f['cpv2'], '1' if f['clear'] is not None else None)
    iq = forced(q_reg, v1)
    d = forced(nxt, v1)
    iqn_plain = b.gate('NOT', (q_reg,))
    iqn = _mux(b, pre, '0', iqn_plain)
    iqn = _mux(b, clr, '1', iqn)
    if clr != '0' and pre != '0' and v2 is not None:
        iqn = _mux(b, b.gate('AND', (clr, pre)), v2, iqn)
    env2 = dict(env, **{f['iq']: iq, f['iqn']: iqn})
    outs = {}
    for p, a in cell.outputs.items():
        n = build_expr(b, a, env2, {})
        if n in ('0', '1') or n == q_reg or not b.is_gate(n) or n in pin_nets.values():
            n = as_site(b, n)
        outs[p] = n
    return d, outs


def _mux(b, s, t, e):
    """s ? t : e with constant folding."""
    if s == '0': return e
    if s == '1': return t
    if t == e: return t
    if t == '1' and e == '0': return s
    if t == '0' and e == '1': return b.gate('NOT', (s,))
    if t == '1': return b.gate('OR', (s, e))
    if t == '0': return b.gate('AND', (b.gate('NOT', (s,)), e))
    if e == '0': return b.gate('AND', (s, t))
    if e == '1': return b.gate('OR', (b.gate('NOT', (s,)), t))
    return b.gate('MUX', (s, t, e))


# ------------------------------------------------------------------ verification (exhaustive)

class _TB:
    """Tiny builder used for verification: gates stored and evaluated directly."""

    def __init__(self):
        self.g = {}; self.n = 0

    def gate(self, op, fi):
        self.n += 1
        k = 'g%d' % self.n
        self.g[k] = (op, tuple(fi))
        return k

    def is_gate(self, n):
        return n in self.g

    def ev(self, n, env, memo):
        if n == '0': return False
        if n == '1': return True
        if n in memo: return memo[n]
        if n not in self.g:
            return bool(env[n])
        op, fi = self.g[n]
        x = [self.ev(f, env, memo) for f in fi]
        r = (x[0] and x[1]) if op == 'AND' else (x[0] or x[1]) if op == 'OR' else (x[0] != x[1]) if op == 'XOR' \
            else (not x[0]) if op == 'NOT' else (x[1] if x[0] else x[2])
        memo[n] = r
        return r


def eval_ff(cell, env, q):
    """Direct semantics of the ff group: returns (IQ, IQN, stored_next) for pin values env and stored value q."""
    f = cell.ff
    e = dict(env); e[f['iq']] = q; e[f['iqn']] = not q
    clr = eval_expr(f['clear'], e) if f['clear'] is not None else False
    pre = eval_expr(f['preset'], e) if f['preset'] is not None else False
    nxt = eval_expr(f['next_state'], e)
    lv = {'L': False, 'H': True}
    if clr and pre:
        iq = lv.get(f['cpv1'], False); iqn = lv.get(f['cpv2'], True); st = iq
    elif clr:
        iq, iqn, st = False, True, False
    elif pre:
        iq, iqn, st = True, False, True
    else:
        iq, iqn, st = q, not q, nxt
    return iq, iqn, st


def verify_cell(cell, max_inputs=16):
    """Exhaustive check of the primitive mapping against the Liberty function. Returns dict(ok, rows, detail)."""
    if cell.kind not in ('comb', 'ff'):
        return dict(ok=None, rows=0, detail='not modelled: ' + cell.why)
    ins = [p for p in cell.inputs if not (cell.ff and p == cell.ff.get('clock_pin'))]
    if len(ins) > max_inputs:
        return dict(ok=None, rows=0, detail='too many inputs for an exhaustive check (%d)' % len(ins))
    b = _TB()
    pins = {p: 'in_' + p for p in ins}
    if cell.ff:
        pins[cell.ff['clock_pin']] = '0'
    rows = 0
    if cell.kind == 'comb':
        outs = map_comb(b, cell, pins)
        for bits in itertools.product((False, True), repeat=len(ins)):
            env = {'in_' + p: v for p, v in zip(ins, bits)}
            penv = dict(zip(ins, bits))
            for p, a in cell.outputs.items():
                want = eval_expr(a, penv)
                got = b.ev(outs[p], env, {})
                if want != got:
                    return dict(ok=False, rows=rows, detail='pin %s differs for inputs %s' % (p, penv))
            rows += 1
        return dict(ok=True, rows=rows, detail='%d input combinations x %d output(s)' % (rows, len(cell.outputs)))
    q = 'q_reg'
    d, outs = ff_parts(b, cell, pins, q)
    for bits in itertools.product((False, True), repeat=len(ins) + 1):
        qv = bits[-1]
        env = {'in_' + p: v for p, v in zip(ins, bits)}; env[q] = qv
        penv = dict(zip(ins, bits))
        iq, iqn, st = eval_ff(cell, penv, qv)
        e2 = dict(penv); e2[cell.ff['iq']] = iq; e2[cell.ff['iqn']] = iqn
        for p, a in cell.outputs.items():
            if eval_expr(a, e2) != b.ev(outs[p], env, {}):
                return dict(ok=False, rows=rows, detail='pin %s differs (inputs %s, stored %d)' % (p, penv, qv))
        if st != b.ev(d, env, {}):
            return dict(ok=False, rows=rows, detail='next stored value differs (inputs %s, stored %d)' % (penv, qv))
        rows += 1
    return dict(ok=True, rows=rows, detail='%d (input, stored value) combinations; outputs and next state' % rows)


def verify_library(lib, only=None):
    res = {}
    for name in sorted(only or lib.cells):
        c = lib.cells[name]
        res[name] = verify_cell(c)
    return res
