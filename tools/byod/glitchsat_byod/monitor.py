"""Generated Verilog: the monitor (computes `bad` and `ok` from top-level signals) and the wrapper (design + monitor +
reset sequence + tied inputs), written for the user to read and used as the RTL reference in validation.

Conditions are Verilog expressions over the top module's ports and probes. Extras:
  $initial          1 in cycle 0 only
  $past(x)          value of signal x one cycle earlier (0 in cycle 0); $past(x, n): n cycles earlier
  $past(expr)       for an expression that is not a plain name: its truth value (1 bit) one cycle earlier
  a.b.c             an internal signal (becomes a probe; marked keep before synthesis)
"""
import re

from .errors import GSError

_ID = re.compile(r"(?<![\w$'.])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?![\w$])")
# Every name the generated monitor and wrapper declare carries this prefix, so it can never collide with a port or
# signal of the user's design (a design output called `ok` or `bad`, an input called `clk` or `dut`, ...).
PFX = 'gsat__'
CLK, BAD, OK = PFX + 'clk', PFX + 'bad', PFX + 'ok'          # monitor and wrapper ports
DUT, MON, OUT = PFX + 'dut', PFX + 'mon', PFX + 'o_'         # wrapper instances and the prefix of the design's outputs
_KEYWORDS = {'and', 'or', 'not', 'begin', 'end', 'if', 'else', 'assign', 'wire', 'reg', 'module', 'input', 'output'}


def _strip_numbers(expr):
    """Blank out Verilog number literals (8'hC3, 'b1010, 4'd5, 0x..) so their letters are not read as names."""
    return re.sub(r"(\d+)?\s*'\s*[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ_?]+", lambda m: ' ' * len(m.group(0)), expr)


def find_names(expr):
    s = _strip_numbers(expr)
    s = re.sub(r'\$[A-Za-z_]+', lambda m: ' ' * len(m.group(0)), s)
    return [m.group(1) for m in _ID.finditer(s) if m.group(1) not in _KEYWORDS]


def _balanced(s, i):
    """s[i] == '(' -> index of the matching ')'."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '(':
            depth += 1
        elif s[j] == ')':
            depth -= 1
            if depth == 0:
                return j
    raise GSError('GS019', 'unbalanced parentheses in condition: %s' % s)


def _split_top_comma(s):
    depth = 0
    for i, ch in enumerate(s):
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ',' and depth == 0:
            return s[:i], s[i + 1:]
    return s, None


def _alias(name):
    return PFX + 'p_' + name.replace('.', '__')


class Monitor:
    """Collects signals and $past registers while conditions are rewritten into monitor-local Verilog."""

    def __init__(self, widths, probe_widths, clock, internal=()):
        self.widths = dict(widths)            # top-level port -> width
        self.probe_widths = dict(probe_widths)  # alias -> width (resolved probes)
        self.probe_names = {}                 # alias -> hierarchical name
        self.used = []                        # ports used, in order
        self.past = []                        # (reg name, source expr, width, depth)
        self.extra = []                       # other declarations
        self.clock = clock
        self.n_expr = 0
        self.internal = set(internal)         # names of internal signals of the top module (no instance path)

    def _use(self, name, aliases):
        if name in aliases:
            name = aliases[name]
        if '.' in name or (name not in self.widths and name in self.internal):
            a = _alias(name)
            self.probe_names[a] = name
            if a not in self.used:
                self.used.append(a)
            return a
        if name not in self.widths and name not in self.probe_widths:
            import difflib
            close = difflib.get_close_matches(name, list(self.widths) + sorted(self.internal), 1)
            raise GSError('GS011', 'condition uses `%s`, which is not a port of the top module or a probe%s'
                          % (name, ' (did you mean `%s`?)' % close[0] if close else ''),
                          note='ports: %s' % ', '.join(sorted(self.widths)),
                          help='use a port name, give `probes: {%s: u_inst.signal}`, or write the internal signal with its '
                               'instance path (u_inst.signal)' % name)
        if name not in self.used:
            self.used.append(name)
        return name

    def width(self, n):
        if n in self.widths:
            return self.widths[n]
        if n in self.probe_widths:
            return self.probe_widths[n]
        return None

    def rewrite(self, expr, aliases):
        s = expr
        out = []
        i = 0
        while i < len(s):
            if s.startswith('$past', i):
                j = s.index('(', i)
                k = _balanced(s, j)
                inner, depth = _split_top_comma(s[j + 1:k])
                d = int(depth.strip()) if depth else 1
                if d < 1:
                    raise GSError('GS019', '$past depth must be >= 1 in: %s' % expr)
                inner = inner.strip()
                if re.fullmatch(r'[A-Za-z_][\w.]*', inner):
                    nm = self._use(inner, aliases)
                    w = self.width(nm) or 1
                    src = nm
                else:
                    src = '((%s) != 0)' % self.rewrite(inner, aliases)
                    w = 1
                reg = PFX + 'past%d_%d' % (len(self.past), d)
                self.past.append((reg, src, w, d))
                out.append(reg)
                i = k + 1
                continue
            if s.startswith('$initial', i):
                out.append(PFX + 'initial')
                i += len('$initial')
                continue
            m = re.compile(r"(\d+)?\s*'\s*[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ_?]+").match(s, i)
            if m and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == '_')):
                out.append(m.group(0)); i = m.end(); continue
            m = re.compile(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*').match(s, i)
            if m and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] in '_$')):
                nm = m.group(0)
                out.append(nm if nm in _KEYWORDS else self._use(nm, aliases))
                i = m.end(); continue
            if s[i] == '$':
                m = re.compile(r'\$[A-Za-z_]+').match(s, i)
                raise GSError('GS019', 'system function %s is not supported in conditions' % (m.group(0) if m else '$'),
                              help='supported: $past(x), $past(x, n), $initial')
            out.append(s[i]); i += 1
        return ''.join(out)

    def verilog(self, bad_exprs, ok_exprs, latency=0, module='glitchsat_monitor'):
        ports = ['  input wire ' + CLK]
        for n in self.used:
            w = self.width(n)
            if w is None:
                raise GSError('GS017', 'probe `%s` has no known width (not found in the elaborated design)' % self.probe_names.get(n, n))
            ports.append('  input wire %s%s' % ('[%d:0] ' % (w - 1) if w > 1 else '', n))
        ports += ['  output wire ' + BAD, '  output wire ' + OK]
        L = ['// Generated by GlitchSAT. Do not edit: change glitchsat.yaml and run again.',
             '// %s = the attack succeeded in this cycle; %s = every must-hold condition is true in this cycle.' % (BAD, OK),
             '// Every name declared here starts with %s, so it cannot clash with a name in your design.' % PFX,
             'module %s (' % module, ',\n'.join(ports), ');']
        L.append('  reg gsat__initial = 1\'b1;')
        L.append('  always @(posedge %s) gsat__initial <= 1\'b0;' % CLK)
        for reg, src, w, d in self.past:
            wd = '[%d:0] ' % (w - 1) if w > 1 else ''
            for k in range(1, d + 1):
                L.append('  reg %s%s_s%d = 0;' % (wd, reg, k))
            L.append('  always @(posedge %s) begin' % CLK)
            L.append('    %s_s1 <= %s;' % (reg, src))
            for k in range(2, d + 1):
                L.append('    %s_s%d <= %s_s%d;' % (reg, k, reg, k - 1))
            L.append('  end')
            L.append('  wire %s%s = %s_s%d;' % (wd, reg, reg, d))
        L += self.extra
        b = ' || '.join('(%s)' % e for e in bad_exprs) or "1'b0"
        o = ' && '.join('(%s)' % e for e in ok_exprs) or "1'b1"
        L.append('  wire gsat__bad_now = (%s) ? 1\'b1 : 1\'b0;' % b)
        L.append('  wire gsat__ok_now = (%s) ? 1\'b1 : 1\'b0;' % o)
        if latency:
            L.append('  reg [%d:0] gsat__bad_sr = 0;' % (latency - 1))
            L.append('  always @(posedge %s) gsat__bad_sr <= %s;' % (CLK, '{gsat__bad_sr[%d:0], gsat__bad_now}' % (latency - 2) if latency > 1 else 'gsat__bad_now'))
            L.append('  assign %s = gsat__bad_sr[%d];   // success %d cycle(s) ago, still unreported' % (BAD, latency - 1, latency))
        else:
            L.append('  assign %s = gsat__bad_now;' % BAD)
        L.append('  assign %s = gsat__ok_now;' % OK)
        L.append('endmodule')
        return '\n'.join(L) + '\n'


def wrapper_verilog(top, ports, roles, fixed, reset, params, monitor_ports, probe_wires, module='glitchsat_wrap'):
    """ports: {name: (direction, width)}. roles: {input name: attacker|secret|fixed|clock|reset}.
    The wrapper has the clock, every free input, every output of the design (gsat__o_<name>), gsat__bad and gsat__ok."""
    clk = next((p for p, r in roles.items() if r == 'clock'), None)
    L = ['// Generated by GlitchSAT from glitchsat.yaml. Do not edit.',
         '// The design as analysed: reset sequence and tied inputs are inside; free inputs and all outputs are ports.']
    io = ['  input wire ' + CLK]
    for p, (d, w) in ports.items():
        if d == 'input' and roles.get(p) in ('attacker', 'secret'):
            io.append('  input wire %s%s' % ('[%d:0] ' % (w - 1) if w > 1 else '', p))
    for p, (d, w) in ports.items():
        if d == 'output':
            io.append('  output wire %s%s%s' % ('[%d:0] ' % (w - 1) if w > 1 else '', OUT, p))
    io += ['  output wire ' + BAD, '  output wire ' + OK]
    L += ['module %s (' % module, ',\n'.join(io), ');']
    if reset:
        R = reset['cycles']
        L.append('  reg [%d:0] gsat__rst_sr = {%d{1\'b1}};' % (R - 1, R))
        L.append('  always @(posedge ' + CLK + ') gsat__rst_sr <= %s;' % ("{gsat__rst_sr[%d:0], 1'b0}" % (R - 2) if R > 1 else "1'b0"))
        L.append('  wire gsat__rst_on = gsat__rst_sr[%d];' % (R - 1))
    for a, (hier, w) in probe_wires.items():
        L.append('  wire %s%s;   // probe %s: connected after flattening (connect -set)' % ('[%d:0] ' % (w - 1) if w > 1 else '', a, hier))
    conns = []
    for p, (d, w) in ports.items():
        r = roles.get(p)
        if d == 'output':
            conns.append('.%s(%s%s)' % (p, OUT, p))
        elif r == 'clock':
            conns.append('.%s(%s)' % (p, CLK))
        elif r == 'reset':
            act = "1'b1" if reset['active'] == 'high' else "1'b0"
            inact = "1'b0" if reset['active'] == 'high' else "1'b1"
            conns.append('.%s(gsat__rst_on ? %s : %s)' % (p, act, inact))
        elif r == 'fixed':
            conns.append(".%s(%d'd%d)" % (p, w, fixed[p]))
        else:
            conns.append('.%s(%s)' % (p, p))
    L.append('  %s %s (%s);' % (top, DUT, ', '.join(conns)))
    mc = ['.%s(%s)' % (CLK, CLK)]
    for n in monitor_ports:
        if n in probe_wires:
            mc.append('.%s(%s)' % (n, n))
        elif n in ports and ports[n][0] == 'output':
            mc.append('.%s(%s%s)' % (n, OUT, n))
        elif roles.get(n) == 'fixed':
            mc.append(".%s(%d'd%d)" % (n, ports[n][1], fixed[n]))
        elif roles.get(n) == 'reset':
            mc.append('.%s(gsat__rst_on ? %s : %s)' % (n, "1'b1" if reset['active'] == 'high' else "1'b0", "1'b0" if reset['active'] == 'high' else "1'b1"))
        elif roles.get(n) == 'clock':
            mc.append('.%s(%s)' % (n, CLK))
        else:
            mc.append('.%s(%s)' % (n, n))
    mc += ['.%s(%s)' % (BAD, BAD), '.%s(%s)' % (OK, OK)]
    L.append('  glitchsat_monitor %s (%s);' % (MON, ', '.join(mc)))
    L.append('endmodule')
    return '\n'.join(L) + '\n'
