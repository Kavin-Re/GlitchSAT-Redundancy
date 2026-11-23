"""From the user's design to the question the engine answers.

  resolve()   roles of the top-level inputs (clock, reset, attacker, secret, fixed), power-up rule, probes
  make_monitor()  the generated monitor Verilog for one check
  compose()   design netlist + monitor netlist + reset handling + tied inputs -> gscale Problem

The monitor is synthesised on its own and joined to the design at the level of nets, so synthesis never optimises
the property together with the chip, and no monitor gate is ever a fault site.
"""
import fnmatch
import re

from . import monitor as MON
from . import sim as SIM
from .errors import GSError, GSWarning
from .project import parse_value
from .netlist import pretty_cell


# ------------------------------------------------------------------ roles

def resolve(spec, det, warnings):
    """det: detect.detect() of the elaborated design. Returns dict(roles, fixed, clock, reset, powerup, changes, evidence)."""
    ports = det['ports']
    ins = [p for p, (d, w) in ports.items() if d == 'input']
    names = ', '.join('`%s`' % p for p in ins)

    def need_input(p, what):
        if p not in ports:
            import difflib
            close = difflib.get_close_matches(p, ins, 1)
            raise GSError('GS011', '%s `%s` is not a port of the top module%s' % (what, p, ' (did you mean `%s`?)' % close[0] if close else ''),
                          note='inputs: %s' % names,
                          help='use one of the input names above')
        if ports[p][0] != 'input':
            raise GSError('GS020', '%s `%s` is an %s, not an input' % (what, p, ports[p][0]))
    roles, fixed = {}, {}
    clock = spec['clock']
    if clock is None:
        clock = det['clock']
        if clock is None and det['flops']:
            raise GSError('GS012', 'no clock found: the design has %d flip-flops but no input drives their clock' % det['flops'],
                          help='add `clock: <port>` to glitchsat.yaml', note='inputs: %s' % names)
    elif clock == 'none':
        clock = None
        if det['flops']:
            raise GSError('GS012', '`clock: none` but the design has %d flip-flops' % det['flops'], help='name the clock port')
    if clock:
        need_input(clock, 'clock')
        roles[clock] = 'clock'
    reset = spec['reset']
    if reset is None:
        reset = det['reset']
        if reset:
            warnings.append(GSWarning('GS070', 'reset `%s` (active %s) was auto-detected; confirm it in glitchsat.yaml' % (reset['port'], reset['active'])))
    elif reset == 'none':
        reset = None
    if reset:
        need_input(reset['port'], 'reset')
        if reset.get('active') is None:
            reset['active'] = (det['reset'] or {}).get('active') if (det['reset'] or {}).get('port') == reset['port'] else \
                ('low' if re.search(r'(_n|_ni|_b|n)$', reset['port']) else 'high')
        if reset['port'] in roles:
            raise GSError('GS015', '`%s` is both clock and reset' % reset['port'])
        roles[reset['port']] = 'reset'
    for p, v in spec['fixed'].items():
        need_input(p, 'fixed input')
        if p in roles:
            raise GSError('GS015', '`%s` is listed as fixed and as %s' % (p, roles[p]), help='remove it from one of the two')
        val = parse_value(v)
        w = ports[p][1]
        if val >> w:
            raise GSError('GS016', 'fixed value %s does not fit the %d-bit input `%s`' % (v, w, p))
        roles[p] = 'fixed'; fixed[p] = val
    for ch in spec['checks']:
        for p, v in (ch.get('fixed') or {}).items():
            need_input(p, 'template input')
            if p not in fixed:
                roles[p] = 'fixed'; fixed[p] = parse_value(v)
    for p in spec['secret']:
        need_input(p, 'secret input')
        if p in roles:
            raise GSError('GS015', '`%s` is listed as secret and as %s' % (p, roles[p]))
        roles[p] = 'secret'
    att = spec['attacker']
    evidence = list(det['evidence'])
    if att == 'all':
        for p in ins:
            if p not in roles:
                if p in det['test_inputs']:
                    roles[p] = 'fixed'; fixed[p] = 0
                    warnings.append(GSWarning('GS071', '`%s` looks like a test/scan-mode input and is fixed to 0 (functional mode); '
                                              'list it under inputs.attacker to let the attacker drive it' % p))
                else:
                    roles[p] = 'attacker'
    else:
        for p in att:
            need_input(p, 'attacker input')
            if p in roles:
                raise GSError('GS015', '`%s` is listed as attacker input and as %s' % (p, roles[p]))
            roles[p] = 'attacker'
        rest = [p for p in ins if p not in roles]
        for p in rest:
            roles[p] = 'attacker'
        if rest:
            warnings.append(GSWarning('GS072', 'inputs not listed anywhere are treated as attacker-controlled: %s' % ', '.join(rest),
                                      help='list them under inputs.fixed (tied) or inputs.secret if that is wrong'))
    pu = spec['powerup'] or ('any' if reset else 'init-or-zero')
    return dict(roles=roles, fixed=fixed, clock=clock, reset=reset, powerup=pu, evidence=evidence,
                changes='cycle' if spec['attacker_changes'] == 'every_cycle' else 'const')


# ------------------------------------------------------------------ monitor

def netname_bits(mod):
    """Cleaned hierarchical name -> bits, for the flattened Yosys module."""
    out = {}
    for n, x in (mod.get('netnames') or {}).items():
        nm = n.replace('$flatten\\', '').replace('\\', '')
        out.setdefault(nm, x['bits'])
    return out


def make_monitor(spec, check, res, det, elab_mod):
    widths = {p: w for p, (d, w) in det['ports'].items()}
    nb = netname_bits(elab_mod)
    probes = {}
    for a, h in spec['probes'].items():
        if h not in nb:
            close = [n for n in nb if n.endswith('.' + h.split('.')[-1]) or n.split('.')[-1] == h.split('.')[-1]][:5]
            raise GSError('GS017', 'probe `%s` = `%s` is not a signal of the elaborated design' % (a, h),
                          note=('similar names: ' + ', '.join(close)) if close else None,
                          help='write the instance path and the signal name as in the RTL, e.g. u_ctrl.state_q')
    M = MON.Monitor(widths, {}, res['clock'], internal=[n for n in nb if '.' not in n and not n.startswith('$')])
    aliases = dict(spec['probes'])
    bad = check['bad']
    if bad and check.get('width_of'):
        w = M.width(check['width_of']) or (len(nb.get(check['width_of'], [])) or 1)
        bad = bad.replace('{W}', "%d'h%X" % (w, (1 << w) - 1))
    bads = [M.rewrite(bad, aliases)] if bad else []
    oks = [M.rewrite(e, aliases) for e in check['must_hold']]
    for a, h in M.probe_names.items():
        if h not in nb:
            close = sorted(n for n in nb if n.split('.')[-1] == h.split('.')[-1])[:5]
            raise GSError('GS017', 'internal signal `%s` used in check `%s` is not in the elaborated design' % (h, check['id']),
                          note=('signals with that name: ' + ', '.join(close)) if close else 'no signal with that name exists',
                          help='check the instance path (dots between instance names)')
        M.probe_widths[a] = len(nb[h])
    # widths of $past sources that are probes were unknown when rewritten: fix them now
    fixed_past = []
    for reg, src, w, d in M.past:
        if src in M.probe_widths:
            w = M.probe_widths[src]
        fixed_past.append((reg, src, w, d))
    M.past = fixed_past
    text = M.verilog(bads, oks, latency=check['detect_latency'])
    return M, text


# ------------------------------------------------------------------ composition

class Composed:
    def __init__(self):
        self.P = None
        self.circ = None
        self.bad = None
        self.ok = None
        self.sites = set()
        self.site_meta = {}         # site net -> dict(net, type flip|set|reset, cell, scope, kind, label)
        self.free_init = {}         # x input net -> flop
        self.in_mode = {}
        self.out_bits = {}          # design output port -> bits
        self.notes = []
        self.reset_state = None


def _site_label(R, net):
    si = R.site_info[net]
    nm = R.circ.names.get(si.get('label_net') or net)
    cell = pretty_cell(si['cell'])
    flop = si['kind'] == 'flop'
    kind = 'flip-flop' if flop else 'gate'
    what = 'stored value' if flop else 'output'
    t = si['type'].lstrip('$').strip('_')
    if nm and not nm.startswith('$') and '$' not in nm.split('.')[-1]:
        return '%s (%s %s %s)' % (nm, t, kind, what)
    sc, _, leaf = cell.rpartition('.')
    return '%s%s %s %s%s' % (sc + ': ' if sc else '', t, kind, leaf, ' (stored value)' if flop else '')


def src_line(attrs):
    """The RTL line a cell came from (Yosys `src` attribute): 'hello_lock.v:18', or '' when synthesis dropped it."""
    import os
    src = str((attrs or {}).get('src') or '')
    for part in src.split('|'):
        m = re.match(r'^(.*?):(\d+)', part)
        if m and m.group(1).endswith(('.v', '.sv', '.vh', '.svh')):
            return '%s:%s' % (os.path.basename(m.group(1)), m.group(2))
    return ''


def match_sites(R, patterns, what):
    """Patterns: glob on hierarchy/net/cell names, re:REGEX, @attr or @attr=value. Returns set of nets; error when one
    pattern matches nothing."""
    out = set()
    for pat in patterns:
        hit = set()
        if pat.startswith('@'):
            k, _, v = pat[1:].partition('=')
            for n, si in R.site_info.items():
                a = si.get('attrs') or {}
                if k in a and (not v or str(a[k]).strip('"') == v or _attr_val(a[k]) == v):
                    hit.add(n)
        else:
            rx = re.compile(pat[3:]) if pat.startswith('re:') else None
            for n, si in R.site_info.items():
                cands = [si['scope'], pretty_cell(si['cell']), R.circ.names.get(si.get('label_net') or n, '')]
                cands += [c + '.' for c in cands if c]
                ok = any(rx.search(c) for c in cands if c) if rx else any(fnmatch.fnmatchcase(c, pat) for c in cands if c)
                if ok:
                    hit.add(n)
        if not hit:
            scopes = sorted({si['scope'] for si in R.site_info.values() if si['scope']})[:12]
            raise GSError('GS018', 'fault-site pattern `%s` in faults.%s matches no gate or flip-flop' % (pat, what),
                          note='scopes in this netlist: %s' % (', '.join(scopes) or '(flat netlist: no hierarchy names)'),
                          help='patterns are matched against instance paths (u_core.*), net names and cell names; '
                               'use re:REGEX for a regular expression or @attribute[=value]')
        out |= hit
    return out


def _attr_val(v):
    if isinstance(v, str) and set(v) <= {'0', '1'} and v:
        return str(int(v, 2))
    return str(v)


def select_sites(spec, R):
    base = set()
    for n, si in R.site_info.items():
        if spec['where'] == 'gates' and si['kind'] != 'gate':
            continue
        if spec['where'] == 'flops' and si['kind'] != 'flop':
            continue
        base.add(n)
    inc = match_sites(R, spec['include'], 'include') if spec['include'] else None
    exc = match_sites(R, spec['exclude'], 'exclude') if spec['exclude'] else set()
    s = (base & inc if inc is not None else base) - exc
    return s, dict(candidates=len(R.site_info), where=spec['where'], selected=len(s), excluded=len(base - s))


def compose(spec, res, R, mod, Mi, check, probe_map, mode='after_reset', warnings=None):
    """R: design Imported; mod: its Yosys JSON module (for names); Mi: monitor Imported (ports by name).
    mode: 'after_reset' (cycle 0 = first cycle after reset; the analysed question) or 'from_powerup' (cycle 0 = power-up,
    reset sequence included; used for validation and with glitch_during_reset)."""
    from .engine import gscale
    G = gscale()
    warnings = warnings if warnings is not None else []
    rc = R.circ
    c = G.circuit.Circuit()
    c.gates = dict(rc.gates); c.flops = dict(rc.flops); c.names = dict(rc.names); c.ports = dict(rc.ports)
    c.inputs = dict(rc.inputs)
    off = R.next_free + 10
    nxt = [off + Mi.next_free + 10]

    def new():
        n = nxt[0]; nxt[0] += 1; return n
    X = Composed()
    roles, fixed, reset = res['roles'], res['fixed'], res['reset']
    # --- monitor
    nb = netname_bits(mod)
    sub = {}
    for p, (d, bits) in Mi.circ.ports.items():
        if d != 'input' or p == MON.CLK or (Mi.asserts and p == 'clk'):   # monitor clock; a checker module's own clock
            continue
        if p in R.port_bits:
            tgt = R.port_bits[p]
        else:
            h = probe_map.get(p)
            if h is None and Mi.asserts:
                raise GSError('GS017', 'port `%s` of the assertion module is not a port or signal of the top module' % p,
                              note='top-level ports: %s' % ', '.join(sorted(R.port_bits)),
                              help='the checker module\'s port names must be the names of top-level ports (or probes)')
            if h is None or h not in nb:
                raise GSError('GS017', 'probe `%s` is not in the netlist of this flow (it was optimised away or renamed)' % (h or p),
                              help='internal signals are marked keep, but a flow that re-encodes or merges them can still change '
                                   'them; use a top-level output in the condition, or a flow such as plain or synth-nofsm')
            tgt = nb[h]
        if len(tgt) != len(bits):
            raise GSError('GS017', 'width of `%s` differs between monitor (%d) and netlist (%d)' % (p, len(bits), len(tgt)))
        for b, t in zip(bits, tgt):
            if isinstance(b, int):
                sub[b] = t if not isinstance(t, str) else t
    mc = Mi.circ

    def m(n):
        if not isinstance(n, int):
            return n
        if n in sub:
            return sub[n]
        return n + off
    for y, (op, fi) in mc.gates.items():
        c.gates[m(y)] = (op, tuple(m(f) for f in fi))
    for q, (d, i) in mc.flops.items():
        iv = Mi.flop_init.get(q)
        c.flops[m(q)] = (m(d), bool(iv))
    for n, nm in mc.names.items():
        if isinstance(n, int) and n not in sub:
            c.names[m(n)] = 'monitor.' + nm
    bad = m(mc.ports[MON.BAD][1][0])
    ok = m(mc.ports[MON.OK][1][0])
    if Mi.asserts:
        terms_b, terms_o = [], []
        for a in Mi.asserts:
            A, EN = m(a['a']), m(a['en'])
            if a['kind'] == 'assert':
                nA = new(); c.gates[nA] = ('NOT', (A,))
                t = new(); c.gates[t] = ('AND', (EN, nA)); terms_b.append(t)
            else:
                nE = new(); c.gates[nE] = ('NOT', (EN,))
                t = new(); c.gates[t] = ('OR', (nE, A)); terms_o.append(t)
        for t in terms_b:
            g = new(); c.gates[g] = ('OR', (bad, t)); bad = g
        for t in terms_o:
            g = new(); c.gates[g] = ('AND', (ok, t)); ok = g
    X.bad, X.ok = bad, ok
    # --- inputs
    in_mode = {}
    for b, (p, i) in list(c.inputs.items()):
        r = roles.get(p)
        if r == 'fixed':
            in_mode[b] = (fixed[p] >> i) & 1
        elif r == 'secret':
            in_mode[b] = 'const'
        elif r == 'attacker':
            in_mode[b] = res['changes']
        elif r == 'reset':
            in_mode[b] = 'reset'
        else:                               # black-box outputs and anything else: free every cycle
            in_mode[b] = 'cycle'
    # --- power-up
    unknown = [q for q in rc.flops if R.flop_init.get(q) is None]
    pu = res['powerup']
    if pu == 'init' and unknown:
        raise GSError('GS028', '`powerup: init` but %d flip-flop(s) have no initial value in the netlist (e.g. %s)'
                      % (len(unknown), rc.names.get(unknown[0], unknown[0])),
                      help='use `powerup: any` (unknown values, safest) or `powerup: zero`')
    init3 = {}
    for q in rc.flops:
        iv = R.flop_init.get(q)
        if iv is None:
            iv = None if pu == 'any' else False
        init3[q] = iv
    # --- reset
    rbits = [b for b, md in in_mode.items() if md == 'reset']
    if reset and mode == 'from_powerup':
        prev = '0'
        chain = []
        for k in range(reset['cycles']):
            q = new(); c.flops[q] = (prev, True); c.names[q] = 'glitchsat.reset_seq[%d]' % k
            chain.append(q); prev = q
        on = chain[-1]
        for b in rbits:
            del c.inputs[b]
            in_mode.pop(b)
            c.gates[b] = ('AND', (on, on)) if reset['active'] == 'high' else ('NOT', (on,))
    elif reset:
        for b in rbits:
            in_mode[b] = 0 if reset['active'] == 'high' else 1
        # state after reset: three-valued fault-free simulation of the design alone (inputs other than fixed are X)
        st = {q: init3[q] for q in rc.flops}
        ordr = SIM.order(rc)
        act = 1 if reset['active'] == 'high' else 0
        for t in range(reset['cycles']):
            inv = {}
            for b, (p, i) in rc.inputs.items():
                r = roles.get(p)
                inv[b] = act if r == 'reset' else ((fixed[p] >> i) & 1) if r == 'fixed' else None
            _, st = SIM.step3(rc, ordr, st, inv)
        X.reset_state = dict(known=sum(1 for v in st.values() if v is not None), unknown=sum(1 for v in st.values() if v is None))
        init3 = dict(st)
    for q in rc.flops:
        v = init3[q]
        c.flops[q] = (c.flops[q][0], bool(v))
    free = [q for q in rc.flops if init3[q] is None]
    if free:
        first = new(); c.flops[first] = ('0', True); c.names[first] = 'glitchsat.first_cycle'
        repl = {}
        for q in free:
            x = new(); c.inputs[x] = ('powerup:' + str(rc.names.get(q, q)), 0); in_mode[x] = 'const'
            qv = new(); repl[q] = qv
            X.free_init[x] = q
            c.names[x] = 'power-up value of ' + str(rc.names.get(q, q))
        for y, (op, fi) in list(c.gates.items()):
            if any(f in repl for f in fi):
                c.gates[y] = (op, tuple(repl.get(f, f) for f in fi))
        for q2, (d, i) in list(c.flops.items()):
            if d in repl:
                c.flops[q2] = (repl[d], i)
        for q, qv in repl.items():
            x = next(k for k, v in X.free_init.items() if v == q)
            c.gates[qv] = ('MUX', (first, x, q))
        if bad in repl: X.bad = bad = repl[bad]
        if ok in repl: X.ok = ok = repl[ok]
    # --- fault sites
    sites, sinfo = select_sites(spec, R)
    X.site_stats = sinfo
    types = spec['fault_types']
    final = set()
    for s in sites:
        lab = _site_label(R, s)
        base = dict(net=s, cell=R.site_info[s]['cell'], scope=R.site_info[s]['scope'], kind=R.site_info[s]['kind'], label=lab,
                    src=src_line(R.site_info[s].get('attrs')))
        if types == ['flip']:
            final.add(s); X.site_meta[s] = dict(base, type='flip')
            continue
        # move the driver of s to s0, then rebuild s from s0 and one auxiliary site per fault type
        s0 = new()
        c.gates[s0] = c.gates.pop(s)
        cur = s0
        for t in types:
            z = new(); c.gates[z] = ('AND', ('0', '0'))      # constant 0; its flip variable is the fault
            final.add(z); X.site_meta[z] = dict(base, type=t)
            if t == 'flip':
                g = new(); c.gates[g] = ('XOR', (cur, z))
            elif t == 'set':
                g = new(); c.gates[g] = ('OR', (cur, z))
            else:
                nz = new(); c.gates[nz] = ('NOT', (z,))
                g = new(); c.gates[g] = ('AND', (cur, nz))
            cur = g
        c.gates[s] = c.gates.pop(cur)
    X.sites = final
    X.in_mode = in_mode
    X.circ = c
    X.out_bits = {p: v['bits'] for p, v in mod['ports'].items() if v['direction'] == 'output'}
    goal = [(bad, 1)]
    quiet = [(ok, 1)] if ok != '1' else []
    N = check['horizon']
    X.P = G.circuit.Problem(c, N, goal, quiet, None, in_mode, final, label=check['id'])
    return X

