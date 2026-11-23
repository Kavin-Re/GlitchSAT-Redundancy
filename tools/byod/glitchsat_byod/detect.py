"""Auto-detection on the elaborated design: top ports, clock, reset, suggested secrets and test-mode inputs.
Every guess comes with its evidence so the user confirms instead of typing."""
import collections
import re

SECRET_RX = re.compile(r'(key|secret|seed|nonce|priv|otp|mask|passw|token)', re.I)
CLOCK_RX = re.compile(r'(^|_)(clk|clock|ck)(_|$|i$|_i$)|clk', re.I)
RESET_RX = re.compile(r'(rst|reset|rstn|rst_n|resetn|clear)', re.I)
TEST_RX = re.compile(r'^(scan_?en|scan_?enable|scan_?mode|test_?mode|test_?en|se|dft_.*|tm)$', re.I)

_FF_TYPES = {'$dff': ('CLK', None, None), '$dffe': ('CLK', None, None), '$adff': ('CLK', 'ARST', 'ARST_POLARITY'),
             '$adffe': ('CLK', 'ARST', 'ARST_POLARITY'), '$sdff': ('CLK', 'SRST', 'SRST_POLARITY'),
             '$sdffe': ('CLK', 'SRST', 'SRST_POLARITY'), '$sdffce': ('CLK', 'SRST', 'SRST_POLARITY'),
             '$dffsr': ('CLK', 'CLR', 'CLR_POLARITY'), '$dffsre': ('CLK', 'CLR', 'CLR_POLARITY'),
             '$aldff': ('CLK', None, None), '$aldffe': ('CLK', None, None)}


def ports_of(mod):
    return {p: (v['direction'], len(v['bits'])) for p, v in mod['ports'].items()}


def _bit_port(mod):
    m = {}
    for p, v in mod['ports'].items():
        if v['direction'] == 'input':
            for i, b in enumerate(v['bits']):
                if isinstance(b, int):
                    m[b] = (p, i)
    return m


def _pol(v):
    if isinstance(v, str):
        return int(v, 2) if set(v) <= {'0', '1'} else 1
    return int(v)


def detect(mod):
    """mod: the elaborated, flattened module (after opt_dff). Returns dict with guesses and evidence."""
    ports = ports_of(mod)
    bp = _bit_port(mod)
    nflops = 0
    clk = collections.Counter()
    rst = collections.defaultdict(lambda: dict(n=0, kind=set(), pol=collections.Counter()))
    edges = collections.Counter()
    for cn, c in (mod.get('cells') or {}).items():
        t = c['type']
        if t not in _FF_TYPES:
            continue
        w = int(c['parameters'].get('WIDTH', '1'), 2) if isinstance(c['parameters'].get('WIDTH'), str) else int(c['parameters'].get('WIDTH', 1))
        nflops += w
        ck, rp, pp = _FF_TYPES[t]
        cb = c['connections'].get(ck, [None])[0]
        if cb in bp:
            clk[bp[cb][0]] += w
        edges[_pol(c['parameters'].get('CLK_POLARITY', 1))] += w
        if rp:
            rb = c['connections'].get(rp, [None])[0]
            if rb in bp:
                r = rst[bp[rb][0]]
                r['n'] += w
                r['kind'].add('asynchronous' if t.startswith('$a') or t.startswith('$dffsr') else 'synchronous')
                r['pol'][_pol(c['parameters'].get(pp, 1))] += w
    ins = [p for p, (d, w) in ports.items() if d == 'input']
    outs = [p for p, (d, w) in ports.items() if d == 'output']
    ev = []
    clock = None
    if clk:
        clock, n = clk.most_common(1)[0]
        ev.append('`%s` drives the clock of %d/%d flip-flops' % (clock, n, nflops))
        if len(clk) > 1:
            ev.append('other clocks: %s (only one clock is modelled)' % ', '.join('`%s` (%d)' % kv for kv in clk.most_common()[1:]))
    elif nflops == 0:
        ev.append('no flip-flops: combinational design')
    else:
        named = [p for p in ins if CLOCK_RX.search(p)]
        if named:
            clock = named[0]
            ev.append('`%s` looks like a clock by its name (no flip-flop clock traced to a port)' % clock)
    reset = None
    if rst:
        rp_, r = max(rst.items(), key=lambda kv: kv[1]['n'])
        pol = r['pol'].most_common(1)[0][0]
        reset = dict(port=rp_, active='high' if pol else 'low', cycles=1, glitch_during_reset=False)
        ev.append('`%s` resets %d/%d flip-flops (%s, active %s)' % (rp_, r['n'], nflops, '/'.join(sorted(r['kind'])), reset['active']))
    else:
        named = [p for p in ins if RESET_RX.search(p) and p != clock]
        if named:
            p = named[0]
            reset = dict(port=p, active='low' if re.search(r'(_n|_ni|_b|n)$', p) else 'high', cycles=1, glitch_during_reset=False)
            ev.append('`%s` looks like a reset by its name (no flip-flop reset traced to it); active %s guessed from the name'
                      % (p, reset['active']))
    secrets = [p for p in ins if SECRET_RX.search(p) and p not in (clock, (reset or {}).get('port'))]
    regs = sorted({n for n in (mod.get('netnames') or {}) if SECRET_RX.search(n.split('.')[-1]) and '$' not in n and n not in ports})
    test = [p for p in ins if TEST_RX.match(p)]
    for p in secrets:
        ev.append('`%s` may carry a secret (name); confirm under inputs.secret' % p)
    for p in test:
        ev.append('`%s` looks like a test/scan-mode input: suggested fixed to 0 (functional mode)' % p)
    return dict(ports=ports, inputs=ins, outputs=outs, flops=nflops, clock=clock, reset=reset, secrets=secrets,
                secret_regs=regs[:20], test_inputs=test, evidence=ev, negedge=edges.get(0, 0))
