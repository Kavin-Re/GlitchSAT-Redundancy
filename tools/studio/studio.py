#!/usr/bin/env python3
"""GlitchSAT Studio - local desktop front-end for the GlitchSAT engine.

Run:  python3 studio.py [--port 8765] [--no-browser] [--no-autostop] [--no-plugins]
Serves a single-page app on 127.0.0.1 only (Python standard library, fully offline).
This one command also loads the lesson (learn_view.py, next to this file) and, when it is found on disk, the
"Open my design" plug-in (tools/studio/studio_byod.py in the repository). See the PLUGIN hook near the end.
Live mode    : every analysis calls scripts/glitchsat.py:run_check in a worker process that can be stopped
               (needs z3; Yosys for the "rebuilt" designs). Studies on the Findings tab run as background jobs.
Recorded mode: if z3 (or Yosys) is missing, results stored in the repository are shown and labelled as recorded.
The project root is $GLITCHSAT_ROOT, else the repository that contains this file, else the current directory.

Extension points (see the end of the Python part and `Studio.registerView` in the page):
  STUDIES / register_study()  - a background study: plan(params) -> units; served by /api/job
  Studio.registerView({...})  - a tab or a Findings card in the page
  PLUGINS / load_plugins()    - optional add-ons found on disk: install(page) and handle(h, method, path, q)
"""
import collections, csv, hashlib, json, os, queue, re, shutil, signal, subprocess, sys, tempfile, threading, time, urllib.parse, urllib.request, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

STUDIO_VERSION = '3.2'                  # the interface; the product version shown to the user is the engine's (ENGINE_VERSION)
IS_WORKER = '--worker' in sys.argv
INFO_ONLY = any(a in ('-h', '--help', '--version', '-V') for a in sys.argv[1:]) and not IS_WORKER   # print and exit: no server

def _find_root():
    env = os.environ.get('GLITCHSAT_ROOT')
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    for up in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):   # repo/, repo/tools/, repo/tools/studio/
        if os.path.isfile(os.path.join(up, 'scripts', 'glitchsat.py')):
            return up
    pk = _package_root()
    if pk:
        return pk
    return os.path.abspath(os.getcwd())     # last resort: the Studio says "not a GlitchSAT project folder"

def _package_root():
    """An installed package that carries the project data (engine, recorded results, tools/<module>), found with
    importlib.resources, so a wheel install does not depend on the current folder."""
    try:
        import importlib.resources as ir
        import importlib.util as iu
    except ImportError:                    # pragma: no cover
        return None
    for pkg in ('glitchsat_data', 'glitchsat', 'faultbound_wt'):
        try:
            if iu.find_spec(pkg) is None:
                continue
            base = ir.files(pkg)
        except Exception:                  # noqa: BLE001 - not installed, or not a package with files
            continue
        for d in (base, base / 'data'):
            try:
                if (d / 'scripts' / 'glitchsat.py').is_file() or (d / '.glitchsat-project').is_file():
                    return os.path.abspath(str(d))
            except Exception:              # noqa: BLE001
                continue
    return None

ROOT = _find_root()
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
GS = None
try:                                   # optional: the app must start without z3
    import glitchsat as GS
    import z3
    LIVE, WHY, Z3V = True, '', z3.get_version_string()
except Exception as e:                 # noqa: BLE001
    LIVE, WHY, Z3V = False, str(e), None

def P(*parts):
    return os.path.join(ROOT, *parts)

def _engine_version():
    """GlitchSAT version, read from the repository (engine file first, then the package metadata)."""
    for rel, pat in (('scripts/glitchsat.py', r"__version__\s*=\s*['\"]([^'\"]+)['\"]"), ('product/pyproject.toml', r"(?m)^version\s*=\s*\"([^\"]+)\"")):
        try:
            m = re.search(pat, open(P(rel), encoding='utf-8').read())
            if m: return m.group(1)
        except OSError:
            pass
    return None

ENGINE_VERSION = _engine_version()
YOSYS = shutil.which('yosys')
YOSYS_V = None
if YOSYS and not IS_WORKER:
    try:
        YOSYS_V = subprocess.run([YOSYS, '-V'], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:                  # noqa: BLE001
        YOSYS_V = None
def _yshort(v):
    m = re.search(r'Yosys\s+(\S+)', v or '')
    return m.group(1) if m else None
YOSYS_SHORT = _yshort(YOSYS_V)
WORK = None if IS_WORKER or INFO_ONLY else tempfile.mkdtemp(prefix='glitchsat-studio-')
KEY = 0xC3
NWORKERS = max(1, (os.cpu_count() or 2) - 1)
CACHE_DIR = os.path.join(os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache'), 'glitchsat-studio')
IDLE_LIMIT_S = 30 * 60                 # generous: a minimised window throttles its timers
BYE_GRACE_S = 8                        # a reload says "bye" and then comes straight back with a new client id
CLIENTS = {}                           # client id -> last time it was heard from
EVER_CLIENT = [False]
LAST_PAGE_GET = [0.0]                  # explainer pages opened from Findings count as "someone is still here"
STARTED = time.time()
BOOT_ID = '%x' % int(STARTED * 1000)    # changes with every start of the server
BROWSER_USED = ['']
PORT = [0]

def explainer_dir():
    """Folder holding the stand-alone explainer pages and their data (name may change in the repo)."""
    for d in ('docs/explainers', 'docs/wow'):
        if os.path.isdir(P(d)):
            return d
    return None

def explainer_file(name):
    d = explainer_dir()
    return os.path.join(d, name) if d and os.path.isfile(P(d, name)) else None

def _recorded_tools():
    """Tool versions of the stored results/reproduce files, as stated by ci/expected_reproduce.json."""
    try:
        note = json.load(open(P('ci', 'expected_reproduce.json'))).get('note', '')
        y = re.search(r'yosys\s+([\d.+]+\d)', note); z = re.search(r'z3\s+([\d.]+\d)', note)
        return dict(yosys=y.group(1) if y else None, z3=z.group(1) if z else None, source='ci/expected_reproduce.json')
    except Exception:                  # noqa: BLE001
        return dict(yosys=None, z3=None, source=None)

DESIGNS = {
    'v0':      dict(file='reference/spike_netlists/v0.json', top='v0',  rec='v0_spike_given-netlist', build='stored', fam='v0'),
    'v1':      dict(file='reference/spike_netlists/v1.json', top='v1',  rec='v1_spike_given-netlist', build='stored', fam='v1'),
    'v2':      dict(file='reference/spike_netlists/v2.json', top='v2',  rec='v2_spike_given-netlist', build='stored', fam='v2'),
    'v0_rtl':  dict(file='rtl/v0.v',  top='v0',  rec='v0_rtl', build='yosys', fam='v0'),
    'v1_rtl':  dict(file='rtl/v1.v',  top='v1',  rec='v1_rtl', build='yosys', fam='v1'),
    'v2_rtl':  dict(file='rtl/v2.v',  top='v2',  rec='v2_rtl', build='yosys', fam='v2'),
    'v2e_rtl': dict(file='rtl/v2e.v', top='v2e', rec=None,     build='yosys', fam='v2e'),
}
# State codes as written in the design sources (rtl/v0.v, rtl/v1.v line 8, rtl/v2.v, rtl/v2e.v); names as in the report (Table 4.1).
_W = {0xF0: 'Idle', 0xCC: 'Armed', 0x96: 'Accept', 0x69: 'Reject'}
FAMILY = {
    'v0':  dict(code='V0',  name='V0 · one check', what='one check of the key', copies=[], src='rtl/v0.v',
                states=dict(st={0: 'Idle', 1: 'Armed', 2: 'Accept', 3: 'Reject'}, boot_word={0x96: 'Accept', 0x69: 'Reject'})),
    'v1':  dict(code='V1',  name='V1 · two copies', what='two copies of the check, joined by one shared wire', copies=[1, 2], src='rtl/v1.v', states=dict(boot_word=_W)),
    'v2':  dict(code='V2',  name='V2 · three copies', what='three copies, each sets its own result bits', copies=[0, 1, 2], src='rtl/v2.v', states=dict(boot_word=_W)),
    'v2e': dict(code='V2e', name='V2e · re-encoded armed word', what='V2 with the Armed code changed from 0xCC to 0xA5', copies=[0, 1, 2], src='rtl/v2e.v',
                states=dict(boot_word={0xF0: 'Idle', 0xA5: 'Armed', 0x96: 'Accept', 0x69: 'Reject'})),
}
# Stored netlists that can stand in for a recorded "rebuilt" run whose own netlist file was not kept.
# A candidate is used only if gate/flop counts match the record and the recorded attack reproduces on it by replay.
REPLAY_CANDIDATES = {
    ('v2', 'plain'):  ['research/c6/p01/netlists/nl_apt_v2.json', 'research/c2/e2_variance/baseline_netlists/apt0.33_v2.json'],
    ('v1', 'plain'):  ['research/c2/e2_variance/baseline_netlists/apt0.33_v1.json'],
    ('v0', 'plain'):  ['research/c2/e2_variance/baseline_netlists/apt0.33_v0.json'],
    ('v2e', 'plain'): ['research/c6/p01/netlists/nl_apt_v2e.json'],
}

# ------------------------------------------------------------------ netlist model (no z3)
PINS = {'$_AND_': ('A', 'B'), '$_OR_': ('A', 'B'), '$_XOR_': ('A', 'B'), '$_NOT_': ('A',), '$_MUX_': ('A', 'B', 'S')}

class NL:
    """Yosys JSON netlist reader. Mirrors the parts of scripts/glitchsat.py:Netlist that the views need."""
    def __init__(self, path, top):
        with open(path) as fh:
            doc = json.load(fh)
        m = doc['modules'][top]
        self.path, self.top, self.creator = path, top, str(doc.get('creator', ''))
        self.ports = m['ports']
        self.gates, self.dffs = {}, []
        for cn, c in m['cells'].items():
            t, con = c.get('type'), c.get('connections', {})
            if t == '$scopeinfo':
                continue
            if t == '$_DFF_P_':
                self.dffs.append((con['D'][0], con['Q'][0]))
            elif t in PINS:
                self.gates[con['Y'][0]] = (t, {p: con[p][0] for p in PINS[t]})
            else:
                raise ValueError(f'unsupported cell type {t}')
        self.names, self.byname = {}, {}
        for n, x in sorted(m['netnames'].items(), key=lambda kv: (kv[0].startswith('$'), kv[0])):
            for i, b in enumerate(x['bits']):
                if isinstance(b, int):
                    nm = f'{n}[{i}]' if len(x['bits']) > 1 else n
                    self.names.setdefault(b, nm)
                    self.byname.setdefault(nm, b)
        self.vec = {n: x['bits'] for n, x in m['netnames'].items()}
        self.init = {}
        for n, x in m['netnames'].items():
            iv = x.get('attributes', {}).get('init')
            if iv:
                for i, b in enumerate(reversed(iv)):
                    if i >= len(x['bits']): break
                    if b in '01':
                        self.init[x['bits'][i]] = int(b)
                    elif any(x['bits'][i] == q for _, q in self.dffs):   # the engine refuses an unknown power-up value; so do the views
                        raise ValueError(f'flop net {n}: init value {iv!r} is not 0/1')
        self.dq = {q: d for d, q in self.dffs}
        self.inbits = {}
        for pn, p in self.ports.items():
            if p.get('direction') == 'input' and pn != 'clk':
                for i, b in enumerate(p['bits']):
                    self.inbits[b] = (pn, i)
        self.fan = collections.defaultdict(list)
        for y, (_, pins) in self.gates.items():
            for s in pins.values():
                if isinstance(s, int):
                    self.fan[s].append(y)
        self.dsink = collections.defaultdict(list)
        for d, q in self.dffs:
            if isinstance(d, int):
                self.dsink[d].append(q)

    def sha(self):
        with open(self.path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def sim(self, inputs, faults, N):
        """Cycle-accurate replay with the engine's fault semantics (glitchsat.py build(), l.205-255):
        a fault (t, net) XORs that net during tick t only; outputs are sampled before the clock edge."""
        inb = {b: (inputs.get(pn, 0) >> i) & 1 for b, (pn, i) in self.inbits.items()}
        st = {q: self.init.get(q, 0) for _, q in self.dffs}
        out = []
        for t in range(N):
            f = {b for tt, b in faults if tt == t}
            val = {}
            def g(b):
                if b == '1': return 1
                if b == '0': return 0
                if not isinstance(b, int): raise ValueError(f'constant {b!r} in the netlist: the engine does not model unknown values')
                if b in val: return val[b]
                if b in inb: v = inb[b]
                elif b in st: v = st[b] ^ (b in f)
                elif b in self.gates:
                    ty, p = self.gates[b]
                    if ty == '$_AND_': v = g(p['A']) & g(p['B'])
                    elif ty == '$_OR_': v = g(p['A']) | g(p['B'])
                    elif ty == '$_XOR_': v = g(p['A']) ^ g(p['B'])
                    elif ty == '$_NOT_': v = 1 - g(p['A'])
                    else: v = g(p['B']) if g(p['S']) else g(p['A'])
                    v ^= (b in f)
                else: v = 0
                val[b] = v
                return v
            for b in list(self.gates) + list(st) + list(inb):
                g(b)
            out.append(val)
            st = {q: g(d) for d, q in self.dffs}
        return out

    @staticmethod
    def word(val, bits):
        return sum((1 if b == '1' else val.get(b, 0) if isinstance(b, int) else 0) << i for i, b in enumerate(bits))

    def reach_positions(self, b, goal_bits, maxcyc):
        """How many bit POSITIONS of the goal port net b can influence within maxcyc clock edges (a port may repeat a net)."""
        hit = self.reach(b, [x for x in goal_bits if isinstance(x, int)], maxcyc)
        return sum(1 for x in goal_bits if x in hit)

    def back_cone(self, start):
        seen, st = set(), list(start)
        while st:
            b = st.pop()
            if b in seen or not isinstance(b, int): continue
            seen.add(b)
            if b in self.gates:
                st.extend(self.gates[b][1].values())
        return seen

    def fwd_comb(self, start):
        seen, st = set(), list(start)
        while st:
            b = st.pop()
            if b in seen: continue
            seen.add(b)
            st.extend(self.fan.get(b, []))
        return seen

    def reach(self, b, goal_bits, maxcyc):
        """Goal bits reachable from b (<= maxcyc flop crossings). Same rule as glitchsat.py forward_reach()."""
        goals, seen, st, hit = set(goal_bits), {(b, 0)}, [(b, 0)], set()
        while st:
            x, c = st.pop()
            if x in goals: hit.add(x)
            nxt = [(y, c) for y in self.fan.get(x, [])] + [(q, c + 1) for q in self.dsink.get(x, [])]
            for y in nxt:
                if y[1] <= maxcyc and y not in seen:
                    seen.add(y); st.append(y)
        return hit

    def in_support(self, b):
        return len({x for x in self.back_cone([b]) if x in self.inbits})

_TL = threading.local()                # Plain view numbers copies from 1 when a design has a copy 0 (V2: c0..c2 -> copy 1..3; V1 keeps c1, c2)
def _cn(c):
    return int(c) + 1 if getattr(_TL, 'one', True) else int(c)

def pretty(name):
    """Everyday description of a wire name. Returns (text, group); group is c0/c1/c2 (a copy), shared, state, flag or merged."""
    m = re.search(r'(?:^|\\)c(\d)\.', name)
    g = re.search(r'new_n(\d+)_?', name)
    i = re.search(r'\[(\d+)\]$', name)
    if name == 'ok': return 'the shared "ok" wire both copies report into', 'shared'
    if name == 'boot_ok': return 'the 1-bit accept flag', 'flag'
    if re.fullmatch(r'(c\d\.m|m\d)', name): return f'the result wire of copy {_cn(name[1])}', 'c' + name[1]
    if name in ('m', 'c.m'): return 'the result wire of the check', 'shared'
    if m and g: return f'a gate inside copy {_cn(m.group(1))}', 'c' + m.group(1)
    if re.search(r'(?:^|\\)c\.', name) and g: return 'a gate inside the check', 'shared'
    if name.startswith('word[') and i: return f'result bit {i.group(1)}, just before it is stored', 'shared'
    if re.match(r'(boot_word|st)\[', name) and i: return f'memory bit {i.group(1)} of the lock state', 'state'
    if name.startswith('$procmux') and i: return f'the logic that picks the next state (bit {i.group(1)})', 'merged'
    if g or 'MuxGate' in name: return 'a gate outside the copies (logic the build tool rearranged)', 'merged'
    return name, 'merged'

GATE_PLAIN = {'AND': 'AND gate: output is 1 only when both inputs are 1', 'OR': 'OR gate: output is 1 when at least one input is 1',
              'XOR': 'XOR gate: output is 1 when the inputs differ', 'NOT': 'NOT gate: output is the opposite of the input',
              'MUX': 'selector: passes one of two inputs, chosen by a third', 'DFF': 'memory bit: keeps its value until the next tick'}

# ------------------------------------------------------------------ witness replay
def state_name(fam, row, v):
    return FAMILY[fam]['states'].get(row, {}).get(v)

def replay(nl, fam, sig, faults, N, goal):
    """faults = [(tick, net_id)]. Returns the waveform data for attacked / same key without flips / right key."""
    goal_port, goal_val = ('boot_ok', 1) if goal == 'flag' else ('boot_word', 0x96)
    t0 = time.time()
    runs = dict(attack=nl.sim({'sig': sig}, faults, N), clean=nl.sim({'sig': sig}, [], N), honest=nl.sim({'sig': KEY}, [], N))
    rows = [dict(id='sig', tech='sig', plain='Key tried', width=8, kind='bus')]
    if 'st' in nl.vec and nl.vec['st'] != nl.ports['boot_word']['bits']:
        rows.append(dict(id='st', tech='st', plain='Lock state', width=len(nl.vec['st']), kind='bus', bits=nl.vec['st']))
        rows.append(dict(id='boot_word', tech='boot_word', plain="The lock's answer", width=8, kind='bus'))
    else:
        rows.append(dict(id='boot_word', tech='boot_word (= st)', plain='Lock state', width=8, kind='bus'))
    rows.append(dict(id='boot_ok', tech='boot_ok', plain='"Open" signal', width=1, kind='bit'))
    seenb = set()
    for nm in sorted(nl.byname):
        if re.fullmatch(r'c\d?\.m', nm) and nl.byname[nm] not in seenb:
            seenb.add(nl.byname[nm])
            c = nm[1] if nm[1].isdigit() else ''
            rows.append(dict(id='n%d' % nl.byname[nm], tech=nm, plain=f'Copy {_cn(c)} says "key matches"' if c else 'The check says "key matches"',
                             width=1, kind='bit', bits=[nl.byname[nm]], group='c' + c if c else 'shared'))
    for t, b in sorted(set(faults)):
        if not any(r['id'] == 'n%d' % b for r in rows) and b not in nl.ports['boot_ok']['bits'] and b not in nl.ports['boot_word']['bits']:
            nm = nl.names.get(b, str(b)); txt, grp = pretty(nm)
            rows.append(dict(id='n%d' % b, tech=nm, plain='Flipped: ' + txt, short='Flipped wire (tick %d)' % t, width=1, kind='bit', bits=[b], group=grp))
    for r in rows:
        bits = r.pop('bits', None) or nl.ports[r['id']]['bits']
        nets = {b for b in bits if isinstance(b, int)}
        r['flips'] = sorted({t for t, b in faults if b in nets})
        for k, run in runs.items():
            r[k] = [NL.word(v, bits) for v in run]
        if r['kind'] == 'bus':
            key = r['id']
            r['names'] = {str(v): state_name(fam, key, v) for k in ('attack', 'clean', 'honest') for v in r[k] if state_name(fam, key, v)}
    gb = nl.ports[goal_port]['bits']
    hit = lambda run: next((t for t, v in enumerate(run) if NL.word(v, gb) == goal_val), None)
    return dict(rows=rows, ticks=N, sig=sig, goal_port=goal_port, goal_val=goal_val,
                opens_at=hit(runs['attack']), clean_opens_at=hit(runs['clean']), honest_opens_at=hit(runs['honest']),
                fault_ticks=sorted({t for t, _ in faults}), ms=round((time.time() - t0) * 1000, 1))

def find_key(nl, faults, N, goal, prefer=None):
    """For records that store the flips but not the wrong key: try every wrong key in the replay."""
    gp, gv = ('boot_ok', 1) if goal == 'flag' else ('boot_word', 0x96)
    gb = nl.ports[gp]['bits']
    order = ([prefer] if prefer is not None else []) + [0x03] + list(range(256))
    for s in order:
        if s == KEY: continue
        if any(NL.word(v, gb) == gv for v in nl.sim({'sig': s}, faults, N)):
            if not any(NL.word(v, gb) == gv for v in nl.sim({'sig': s}, [], N)):
                return s
    return None

# ------------------------------------------------------------------ circuit map (layered layout, pure Python)
def schematic(nl, faults, focus=True):
    fnets = {b for _, b in faults}
    ftick = collections.defaultdict(list)
    for t, b in faults: ftick[b].append(t)
    hot = nl.fwd_comb(fnets) if fnets else set()
    cone = nl.back_cone(fnets) if fnets else set()
    if focus and fnets:
        keep = {b for b in (cone | hot) if b in nl.gates}
    else:
        keep = set(nl.gates)
    out_bits = {}
    for pn, p in nl.ports.items():
        if p.get('direction') == 'output':
            for i, b in enumerate(p['bits']):
                if isinstance(b, int): out_bits.setdefault(b, []).append(f'{pn}[{i}]' if len(p['bits']) > 1 else pn)
    nodes, edges = {}, []          # edges: (src_id, dst_id, pin, net)
    def src_tag(b):
        if b in fnets: return None            # a flipped source keeps its own box so the flip can be shown on it
        if b in nl.inbits:
            pn, i = nl.inbits[b]; return dict(tag='k%d' % i, tagplain=f'key bit {i}', tagtech=f'{pn}[{i}]')
        if b in nl.dq:
            nm = nl.names.get(b, str(b)); ix = re.search(r'\[(\d+)\]$', nm)
            return dict(tag='s' + (ix.group(1) if ix else ''), tagplain=f'lock-state bit {ix.group(1)} (current value)' if ix else 'lock-state bit', tagtech=nm)
        return None
    def src_node(b):
        if b in nl.gates:
            return ('g%d' % b) if b in keep else None
        nid = 's%d' % b
        if nid not in nodes:
            if b in nl.inbits:
                pn, i = nl.inbits[b]
                nodes[nid] = dict(kind='in', net=b, tech=f'{pn}[{i}]', plain=f'key bit {i}', type='IN')
            elif b in nl.dq:
                nm = nl.names.get(b, str(b)); ix = re.search(r'\[(\d+)\]$', nm)
                nodes[nid] = dict(kind='q', net=b, tech=nm, plain=f'state bit {ix.group(1)}' if ix else 'state bit', type='DFF')
            else:
                return None
        return nid
    for y in sorted(keep):
        ty, pins = nl.gates[y]
        nm = nl.names.get(y, str(y)); txt, grp = pretty(nm)
        nodes['g%d' % y] = dict(kind='gate', net=y, type=ty.strip('$_'), tech=nm, plain=txt, group=grp, pins=[])
    for y in sorted(keep):
        ty, pins = nl.gates[y]
        for pin in PINS[ty]:
            s = pins[pin]
            if not isinstance(s, int):
                nodes['g%d' % y]['pins'].append(dict(pin=pin, const=str(s))); continue
            tg = src_tag(s)
            if tg:
                nodes['g%d' % y]['pins'].append(dict(pin=pin, **tg)); continue
            sid = src_node(s)
            if sid is None:
                nodes['g%d' % y]['pins'].append(dict(pin=pin, stub=True)); continue
            nodes['g%d' % y]['pins'].append(dict(pin=pin))
            edges.append((sid, 'g%d' % y, pin, s))
    for d, q in nl.dffs:
        if not isinstance(d, int): continue
        sid = ('g%d' % d) if d in keep else (src_node(d) if d in fnets else None)
        if sid is None: continue
        nm = nl.names.get(q, str(q)); ix = re.search(r'\[(\d+)\]$', nm)
        nodes['d%d' % q] = dict(kind='d', net=q, tech=nm + ' (next)', plain=(f'next state bit {ix.group(1)}' if ix else 'next state bit'),
                                type='DFF', pins=[dict(pin='D')])
        edges.append((sid, 'd%d' % q, 'D', d))
    for nid, n in nodes.items():
        b = n['net']
        if n['kind'] != 'd':
            if b in fnets: n['fault'] = sorted(ftick[b])
            n['hot'] = b in hot
            n['cone'] = b in cone
            if n['kind'] == 'gate' and b in out_bits: n['out'] = out_bits[b]
        else:
            n['hot'] = nl.dq[b] in hot
    # layers
    preds = collections.defaultdict(list); succs = collections.defaultdict(list)
    for s, d, _, _ in edges:
        preds[d].append(s); succs[s].append(d)
    layer = {}
    def lay(n):
        if n in layer: return layer[n]
        k = nodes[n]['kind']
        layer[n] = 0 if k in ('in', 'q') else 1 + max([lay(p) for p in preds[n]] or [0])
        return layer[n]
    for n in nodes: lay(n)
    for n in nodes:                    # pull sources next to their first consumer; keeps long wires short
        if nodes[n]['kind'] in ('in', 'q') and succs[n]:
            layer[n] = min(layer[s] for s in succs[n]) - 1
    gate_max = max([layer[n] for n in nodes if nodes[n]['kind'] != 'd'] or [0])
    for n in nodes:
        if nodes[n]['kind'] == 'd': layer[n] = gate_max + 1
    L = max(layer.values() or [0])
    # dummy nodes: one trunk per net per crossed layer
    segs = []                          # (u, v, pin_or_None, net)
    for s, d, pin, net in edges:
        prev = s
        for l in range(layer[s] + 1, layer[d]):
            did = 'x%d_%d' % (net, l)
            if did not in nodes:
                nodes[did] = dict(kind='dummy', net=net, hot=nodes[s].get('hot', False)); layer[did] = l
            if (prev, did, None, net) not in segs: segs.append((prev, did, None, net))
            prev = did
        segs.append((prev, d, pin, net))
    up = collections.defaultdict(list); dn = collections.defaultdict(list)
    for u, v, _, _ in segs:
        up[v].append(u); dn[u].append(v)
    cols = [[] for _ in range(L + 1)]
    for n in sorted(nodes, key=lambda n: (nodes[n]['kind'] != 'in', nodes[n].get('group', ''), nodes[n]['net'] if isinstance(nodes[n]['net'], int) else 0)):
        cols[layer[n]].append(n)
    pos = {}
    def index():
        for c in cols:
            for i, n in enumerate(c): pos[n] = i
    index()
    for sweep in range(8):
        rng = range(1, L + 1) if sweep % 2 == 0 else range(L - 1, -1, -1)
        nb = up if sweep % 2 == 0 else dn
        for l in rng:
            bc = {n: (sum(pos[x] for x in nb[n]) / len(nb[n]) if nb[n] else pos[n]) for n in cols[l]}
            cols[l].sort(key=lambda n: (bc[n], pos[n]))
            for i, n in enumerate(cols[l]): pos[n] = i
    H = dict(gate=30, dummy=9, d=22, q=22)
    H['in'] = 22
    W = dict(gate=34, dummy=0, d=92, q=72)
    W['in'] = 62
    HH = lambda n: 58 if nodes[n].get('fault') else H[nodes[n]['kind']]
    y = {}
    for c in cols:
        cy = 0
        for n in c:
            h = HH(n); y[n] = cy + h / 2; cy += h
    def settle(l, want):
        c = cols[l]
        if not c: return
        ys = [want[n] for n in c]
        for i in range(1, len(c)):
            sep = (HH(c[i]) + HH(c[i - 1])) / 2
            ys[i] = max(ys[i], ys[i - 1] + sep)
        shift = sum(ys[i] - want[n] for i, n in enumerate(c)) / len(c)
        for i, n in enumerate(c): y[n] = ys[i] - shift
    for it in range(6):
        for l in (range(1, L + 1) if it % 2 == 0 else range(L - 1, -1, -1)):
            nb = up if it % 2 == 0 else dn
            settle(l, {n: (sum(y[x] for x in nb[n]) / len(nb[n]) if nb[n] else y[n]) for n in cols[l]})
    ymin = min(y.values() or [0])
    for n in y: y[n] = round(y[n] - ymin + 22, 1)
    # pin positions
    pin_y = {}
    for n, nd in nodes.items():
        if nd['kind'] == 'gate':
            ty = nd['type']
            inc = {p: u for u, v, p, _ in segs if v == n and p}
            order = list(PINS['$_%s_' % ty])
            offs = {'AND': [-7, 7], 'OR': [-7, 7], 'XOR': [-7, 7], 'NOT': [0], 'MUX': [-9, 0, 9]}[ty]
            if ty in ('AND', 'OR', 'XOR') and len(inc) == 2 and y[inc['A']] > y[inc['B']]:
                order = ['B', 'A']
            for p, o in zip(order, offs): pin_y[(n, p)] = y[n] + o
            for pd in nd['pins']: pd['y'] = round(pin_y[(n, pd['pin'])] - y[n], 1)
        elif nd['kind'] == 'd':
            pin_y[(n, 'D')] = y[n]
    # columns and wire tracks
    pad = [20 if any(pd.get('tag') or pd.get('const') is not None or pd.get('stub') for n in c for pd in nodes[n].get('pins', [])) else 0 for c in cols]
    colw = [pad[l] + max([W[nodes[n]['kind']] for n in c] or [0]) for l, c in enumerate(cols)]
    gap_nets = []
    for l in range(L):
        nets = {}
        for u, v, p, net in segs:
            if layer[u] == l:
                ty_ = pin_y.get((v, p), y[v])
                if abs(ty_ - y[u]) > 0.5: nets.setdefault(net, y[u])
        gap_nets.append([k for k, _ in sorted(nets.items(), key=lambda kv: kv[1])])
    x0, cx = [], 14
    gapx = []
    for l in range(L + 1):
        x0.append(cx); cx += colw[l]
        if l < L:
            gapx.append(cx); cx += 16 + 6 * len(gap_nets[l])
    width = cx + 14
    for n, nd in nodes.items():
        l = layer[n]; w = W[nd['kind']]
        nd['x'] = round(x0[l] + (colw[l] - w if nd['kind'] in ('in', 'q') else pad[l]), 1); nd['y'] = y[n]; nd['w'] = w
    wires, dots = [], []
    by_net_gap = collections.defaultdict(list)
    for u, v, p, net in segs:
        l = layer[u]; un, vn = nodes[u], nodes[v]
        sx = x0[l] if un['kind'] == 'dummy' else un['x'] + un['w']
        ex = x0[l + 1] + colw[l + 1] if vn['kind'] == 'dummy' else vn['x']
        sy, ey = y[u], pin_y.get((v, p), y[v])
        if abs(sy - ey) <= 0.5:
            pts = [[sx, sy], [ex, sy]]
        else:
            tx = gapx[l] + 8 + 6 * gap_nets[l].index(net)
            pts = [[sx, sy], [tx, sy], [tx, ey], [ex, ey]]
            by_net_gap[(net, l)].append((tx, sy, ey))
        ishot = bool(net in hot)
        wires.append(dict(net=net, pts=[[round(a, 1), round(b, 1)] for a, b in pts], hot=ishot, cone=net in cone, to=v))
    for (net, l), lst in by_net_gap.items():
        if len(lst) > 1:
            ys = sorted({ey for _, _, ey in lst} | {lst[0][1]})
            for yy in ys[1:-1]: dots.append([round(lst[0][0], 1), round(yy, 1), net in hot])
    height = max([nd['y'] for nd in nodes.values()] or [0]) + 30
    outn = [dict(id=n, **{k: v for k, v in nd.items()}) for n, nd in nodes.items() if nd['kind'] != 'dummy']
    return dict(w=round(width), h=round(height), nodes=outn, wires=wires, dots=dots, focus=bool(focus and fnets),
                shown=len([1 for n in nodes.values() if n['kind'] == 'gate']), total=len(nl.gates), flops=len(nl.dffs))

def ownership(nl, fam, rp):
    """Which copy sets which result bit, from the netlist's own `sel` / `cN.m` names (kept by the designs' keep attributes)."""
    sel = nl.vec.get('sel')
    cm = {nl.byname[n]: int(n[1]) for n in nl.byname if re.fullmatch(r'c\d\.m', n)}
    if not sel or len(sel) != 8 or not cm or any(b not in cm for b in sel):
        return None
    codes = {v: k for k, v in FAMILY[fam]['states']['boot_word'].items()}
    armed, opened = codes.get('Armed'), codes.get('Accept')
    need = armed ^ opened
    bits = [dict(bit=i, copy=cm[sel[i]], armed=(armed >> i) & 1, open=(opened >> i) & 1, change=bool((need >> i) & 1)) for i in range(8)]
    return dict(bits=bits, armed=armed, open=opened, xor=need, copies_needed=sorted({b['copy'] for b in bits if b['change']}),
                source=f'net names `sel`, `cN.m` in the netlist; state codes from {FAMILY[fam]["src"]}')

# ------------------------------------------------------------------ recorded results
def _load(rel):
    with open(P(rel)) as fh:
        return json.load(fh)

def _names_to_ids(nl, items):
    out = []
    for nm, t in items:
        if nm not in nl.byname: return None
        out.append((int(t), nl.byname[nm]))
    return out

def _bound(k, N, goal):
    gp, gv = ('boot_ok', 1) if goal == 'flag' else ('boot_word', 0x96)
    return dict(max_faults=k, cycles=N, fault_model='single-cycle bit flip of any gate output or flop Q',
                attacker_input='`sig` free, held constant, != key 0xC3', goal=f'{gp} == 0x{gv:X} at some cycle < {N}')

def _synth_record(d, flow, goal, k, min_f, fault_names, sig, gates, flops, src, engine, k_rec, extra=''):
    """Shape a record from another repo file like a run_check result."""
    atk = min_f is not None and k >= min_f
    r = dict(label='MEASURED', tool=engine, design=d['file'], top=d['top'], synth_flow=flow,
             verdict='ATTACK_FOUND' if atk else 'NO_ATTACK_UP_TO_BOUND', bound=_bound(k, 6, goal),
             netlist=dict(gates=gates, flops=flops), runtime_s={}, model={})
    if atk:
        r['min_faults'] = min_f
        r['faults'] = [dict(net=n, cycle=int(t), kind='') for n, t in fault_names]
        if sig is not None:
            r['attacker_input'] = {'sig': f'0x{sig:02X}'}; r['attacker_input_raw'] = {'sig': sig}
    r['_rec'] = dict(file=src, engine=engine, k_rec=k_rec, derived=(k != k_rec), extra=extra,
                     wit=[(n, int(t)) for n, t in fault_names], wit_sig=sig, min_rec=min_f)
    return r

def recorded(d, k, flow, goal, cycles):
    """Returns (result, netlist_candidates) or (None, reason)."""
    fam = d['fam']
    if cycles != 6:
        return None, 'Saved results exist only for 6 ticks.'
    if goal == 'word' and d['rec']:
        fn = lambda kk: 'results/reproduce/' + (f"{d['rec']}_k{kk}.json" if d['build'] == 'stored' else f"{d['rec']}_{flow}_k{kk}.json")
        rel, k_rec = fn(k), k
        if not os.path.exists(P(rel)) and k > 3 and os.path.exists(P(fn(3))):
            rel, k_rec = fn(3), 3              # a minimum found at k<=3 is also the minimum at a larger limit
        if not os.path.exists(P(rel)):
            return None, 'Saved results cover limits of 0 to 3 flips.'
        r = _load(rel)
        if k_rec != k:
            if r['verdict'] != 'ATTACK_FOUND':
                return None, 'The saved runs stop at 3 flips and found no attack there, so nothing can be said about 4.'
            r['bound'] = _bound(k, 6, goal)
        rt = _recorded_tools()
        r['_rec'] = dict(file=rel, engine='scripts/glitchsat.py', k_rec=k_rec, derived=(k_rec != k), extra='', min_rec=r.get('min_faults'),
                         yosys_rec=rt['yosys'], z3_rec=rt['z3'], tools_source=rt['source'])
        return r, ([d['file']] if d['build'] == 'stored' else REPLAY_CANDIDATES.get((fam, flow), []))
    if goal == 'word' and fam == 'v2e':
        rel = 'research/c6/p01/sweeps/sweep_apt_v2e.json'
        if not os.path.exists(P(rel)): return None, 'The saved V2e result file is missing.'
        s = _load(rel)
        v = next((x for x in s['variants'] if x['name'] == ('plain' if flow == 'plain' else 'opt_flow')), None)
        if not v or v.get('status') != 'ok': return None, 'No saved result for this build style.'
        fl = [x.rsplit('@', 1) for x in v.get('faults', [])]
        r = _synth_record(d, flow, goal, k, v.get('min_faults'), fl, None, v['gates'], v['flops'], rel,
                          f"packaged CLI faultbound-wt {s.get('tool_version', '')} (the package is now glitchsat {ENGINE_VERSION or ''}; record not re-run)", s['bounds']['max_flips'],
                          extra=f"variant `{v['name']}`; netlist built with {s.get('yosys', 'Yosys')}; register id P01.v2e.apt.sweep in docs/NUMBERS.md")
        r['runtime_s'] = dict(solve_and_minimize=v.get('runtime_s'))
        r['_rec']['yosys'] = s.get('yosys')
        return r, REPLAY_CANDIDATES.get((fam, flow), [])
    if goal == 'flag' and d['build'] == 'stored':
        wf = explainer_file('witness.json')
        if fam == 'v2' and wf:
            fr = next((f for f in _load(wf)['frames'] if f['id'] == 'v2_flag_k1'), None)
            if fr:
                s = fr['solver']
                r = _synth_record(d, 'given-netlist', goal, k, s['min_faults'], [(f['net'], f['cycle']) for f in s['faults']],
                                  s['attacker_input_raw']['sig'], s['gates'], s['flops'], wf + ' (frame v2_flag_k1)',
                                  'scripts/glitchsat.py', s['max_faults'], extra='register id B2.v2.ok / P21.witness in docs/NUMBERS.md')
                r['model'] = dict(sites_total=s['sites_total'], sites_modelled=s['sites_modelled'], reduce=s['reduce'])
                return r, [d['file']]
        rel = 'research/c2/b2_scope/matrix.jsonl'
        if os.path.exists(P(rel)):
            for line in open(P(rel)):
                x = json.loads(line)
                if (x['design'], x['netlist'], x['goal'], x['input_sites'], x['init'], x['free_input']) == (fam, 'spike', 'boot_ok', False, 'known', False):
                    nl = NL(P(d['file']), d['top'])
                    r = _synth_record(d, 'given-netlist', goal, k, x['min_cost'], x['faults'], None, len(nl.gates), len(nl.dffs), rel,
                                      'research/c2/b2_scope/gs.py (scope-study copy of the engine)', 3, extra='scope-grid cell: flag goal, known start, key wires not glitchable')
                    return r, [d['file']]
    return None, ('No saved result for the 1-bit flag on a rebuilt circuit.' if goal == 'flag' else 'No saved result for these settings.')

# ------------------------------------------------------------------ worker process (one task, then exit; can be killed at any time)
def worker_main(task_file, out_file):
    """Runs ONE engine call in its own process so the server can stop it. Task kinds: check (scripts/glitchsat.py:run_check),
    cell (the packaged CLI in product/src, for the scope options run_check does not have)."""
    with open(task_file) as fh:
        t = json.load(fh)
    try:
        if t['kind'] == 'check':
            if GS is None or not LIVE:
                raise RuntimeError('z3-solver is not installed: ' + WHY)
            src, d, k, cycles, flow = t['src'], dict(top=t['top']), t['k'], t['cycles'], t['flow']
            goal_out, goal_val, WORK = t['goal_out'], t['goal_val'], t['workdir']
            r = GS.run_check(src, d['top'], k, cycles, None, 'full', goal_out, goal_val, 'sig', 0xC3, 0,
                             workdir=WORK, flow=flow)
            out = dict(ok=True, result=r)
        elif t['kind'] == 'cell':
            import contextlib, io
            sys.path.insert(0, P('product', 'src'))
            from faultbound_wt import cli
            rep = out_file + '.report.json'
            err, so = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(so):
                try:
                    code = cli.main(list(t['args']) + ['--report', rep])
                except SystemExit as e:
                    code = e.code if isinstance(e.code, int) else 3
            report = None
            if os.path.exists(rep):
                with open(rep) as fh:
                    report = json.load(fh)
            out = dict(ok=True, result=dict(exit=code, report=report, stderr=err.getvalue()[-1500:]))
        else:
            out = dict(ok=False, error='unknown task kind')
    except BaseException as e:                 # noqa: BLE001  (reported to the server, never swallowed)
        out = dict(ok=False, error=f'{type(e).__name__}: {e}')
    with open(out_file + '.tmp', 'w') as fh:
        json.dump(out, fh)
    os.replace(out_file + '.tmp', out_file)

# ------------------------------------------------------------------ process control: every engine or Yosys call is a killable child
def _kill(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)       # the child leads its own process group, so Yosys/abc children die with it
    except (ProcessLookupError, PermissionError, OSError):
        try: p.kill()
        except OSError: pass

def run_proc(argv, limit_s, token, cwd=None):
    """Returns (status, returncode, stdout, stderr, seconds); status is ok | timeout | stopped. Never blocks past limit_s."""
    t0 = time.time()
    td = tempfile.mkdtemp(dir=WORK)
    with open(os.path.join(td, 'o'), 'w+') as fo, open(os.path.join(td, 'e'), 'w+') as fe:
        env = dict(os.environ, GLITCHSAT_ROOT=ROOT)
        p = subprocess.Popen(argv, cwd=cwd, env=env, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, start_new_session=True)
        token['proc'] = p
        status = 'ok'
        while p.poll() is None:
            if token.get('cancel'): status = 'stopped'; _kill(p); break
            if time.time() - t0 > limit_s: status = 'timeout'; _kill(p); break
            time.sleep(0.03)
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: pass
        fo.seek(0); fe.seek(0)
        out, err = fo.read(), fe.read()
    shutil.rmtree(td, ignore_errors=True)
    token.pop('proc', None)
    return status, p.returncode, out, err, round(time.time() - t0, 3)

def run_worker(task, limit_s, token):
    """Returns (status, payload, seconds); status is ok | timeout | stopped | error."""
    td = tempfile.mkdtemp(dir=WORK)
    tf, of = os.path.join(td, 'task.json'), os.path.join(td, 'out.json')
    with open(tf, 'w') as fh:
        json.dump(task, fh)
    st, rc, out, err, secs = run_proc([sys.executable, os.path.abspath(__file__), '--worker', tf, of], limit_s, token)
    payload = None
    if st == 'ok':
        if os.path.exists(of):
            with open(of) as fh:
                o = json.load(fh)
            st, payload = ('ok', o['result']) if o.get('ok') else ('error', o.get('error', 'engine error'))
        else:
            st, payload = 'error', (err.strip().splitlines() or ['the engine process ended without a result'])[-1]
    shutil.rmtree(td, ignore_errors=True)
    return st, payload, secs

# ------------------------------------------------------------------ analysis entry point
RUNS = {}                              # run id -> token of the running engine process (for the Stop button)

def _cli(d, k, cycles, flow, goal):
    c = f"python3 scripts/glitchsat.py check {d['file']} --top {d['top']} --k {k} --cycles {cycles}"
    if d['build'] == 'yosys': c += f' --flow {flow}'
    if goal == 'flag': c += ' --goal-out boot_ok --goal-value 1'
    return c

def _plain_error(raw, d, k, flow, goal, cycles):
    low = raw.lower()
    if 'synthesis failed' in low or 'yosys' in low and 'error' in low:
        msg = f'The build tool ({YOSYS_V.split(" (")[0] if YOSYS_V else "Yosys"}) could not turn the design into gates.'
    elif 'unsupported' in low or 'has type' in low:
        msg = 'This Yosys build produced a kind of gate that the engine does not model.'
    elif 'z3' in low or 'importerror' in low or 'modulenotfound' in low or 'attributeerror' in low:
        msg = 'The solver (z3) is not installed correctly on this computer.'
    else:
        msg = 'The engine stopped with an error.'
    try: fb = recorded(d, k, flow, goal, cycles)[0] is not None
    except Exception: fb = False                # noqa: BLE001
    return dict(error=msg, error_kind='engine', error_detail=raw[-1800:], can_fallback=fb)

def analyze(q):
    d = DESIGNS[q['design']]
    fam = d['fam']
    _TL.one = 0 in FAMILY[fam]['copies']
    try:
        k = max(0, min(int(q.get('k', 3)), 4))
        cycles = max(1, min(int(q.get('cycles', 6)), 12))
        limit = max(2.0, min(float(q.get('time_limit_s', 60)), 3600.0))
    except (TypeError, ValueError):
        return dict(error='The settings are not valid numbers.', error_kind='bad_settings')
    flow = q.get('flow', 'plain') if q.get('flow') in ('plain', 'opt') else 'plain'
    goal = 'flag' if q.get('goal') == 'flag' else 'word'
    goal_out, goal_val = ('boot_ok', 1) if goal == 'flag' else ('boot_word', 0x96)
    src = os.path.join(ROOT, d['file'])
    log = []
    def L(tag, tech, plain): log.append(dict(tag=tag, tech=tech, plain=plain))
    cands, nlpath, nl_note, nl_standin = [], None, '', False
    stop = None
    can_live = LIVE and (d['build'] == 'stored' or YOSYS)
    if can_live and not q.get('force_recorded'):
        rid, token = str(q.get('run_id') or ''), {}
        RUNS[rid] = token
        wd = tempfile.mkdtemp(dir=WORK)        # private folder per run: a second run can never overwrite this run's netlist
        try:
            st, payload, secs = run_worker(dict(kind='check', src=src, top=d['top'], k=k, cycles=cycles, goal_out=goal_out,
                                                goal_val=goal_val, flow=flow, workdir=wd), limit, token)
        finally:
            RUNS.pop(rid, None)
        nlpath = src if d['build'] == 'stored' else os.path.join(wd, f"{d['top']}.json" if flow == 'plain' else f"{d['top']}_{flow}.json")
        if st == 'error':
            L('error', payload, 'the engine reported an error')
            e = _plain_error(str(payload), d, k, flow, goal, cycles); e['_log'] = log
            return e
        if st in ('timeout', 'stopped'):
            stop = dict(why=st, limit=limit, elapsed=secs)
            r = dict(tool='glitchsat.py', design=d['file'], top=d['top'], synth_flow=flow, verdict='UNKNOWN_TIMEOUT',
                     bound=_bound(k, cycles, goal), netlist={}, model={}, runtime_s={})
        else:
            r = payload
            if r['verdict'] not in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND'):
                stop = dict(why='solver', limit=limit, elapsed=secs)
        r['_wall'] = secs
        r['_src'] = 'live'
        rt, mo = r.get('runtime_s') or {}, r.get('model') or {}
        if r.get('netlist'):
            if d['build'] == 'yosys':
                L('synth', f"yosys {flow} {d['file']} -> {r['netlist']['gates']} gates, {r['netlist']['flops']} flops ({rt.get('synth', 0):.2f} s)",
                  f"Yosys turned the design into {r['netlist']['gates']} logic gates")
            else:
                L('load', f"{d['file']} ({r['netlist']['gates']} gates, {r['netlist']['flops']} flops)", 'opened the saved circuit file')
        if mo.get('sites_total') is not None:
            L('model', f"N={cycles}  sites {mo.get('sites_total')}  modelled {mo.get('sites_modelled')} (reduce={mo.get('reduce')})",
              f"{mo.get('sites_total')} places-and-moments where a flip could hit; {mo.get('sites_modelled')} of them can matter")
        if stop is None:
            L('solve', f"z3 {Z3V}  k<={k}  solve {mo.get('solve_s', 0)} s" + (f"  minimise {mo.get('minimize_s')} s" if 'minimize_s' in mo else '') + f"  (wall {secs} s, limit {limit:g} s)",
              'the solver finished: it covered every combination inside the limits exactly (not by sampling)')
        else:
            txt = {'timeout': f'stopped at the time limit of {limit:g} s', 'stopped': f'stopped by the user after {secs} s',
                   'solver': 'the solver returned "unknown"'}[stop['why']]
            L('solve', f"z3 {Z3V}  k<={k}  INCOMPLETE: {txt}", f'the search did not finish ({txt}); nothing can be concluded')
    else:
        r, cands = recorded(d, k, flow, goal, cycles)
        if r is None:
            reason = cands
            tail = ('With the engine (z3' + ('' if d['build'] == 'stored' else ' and Yosys') + ') installed, this setting is computed live.') if not can_live else ''
            return dict(error=f'{reason} {tail}'.strip(), error_kind='no_record')
        r['_src'] = 'recorded'
        r['_wall'] = (r.get('runtime_s') or {}).get('solve_and_minimize')
        L('load', r['_rec']['file'], 'opened a saved result from the project files')
        L('record', f"engine {r['_rec']['engine']}; bound when recorded: <= {r['_rec']['k_rec']} flips, 6 ticks" +
          (f"; solver time stored in the record {r['_wall']} s" if r['_wall'] is not None else ''),
          'this result was computed earlier and stored; nothing was run just now')
        if r['_rec']['derived']:
            L('note', f"your limit k={k} differs from the saved run (k<={r['_rec']['k_rec']}); the saved run minimised the flip count, so the answer for k={k} follows from its minimum",
              'the saved run used a different flip limit; its smallest attack tells us the answer for your limit')
    atk = r['verdict'] == 'ATTACK_FOUND'
    none = r['verdict'] == 'NO_ATTACK_UP_TO_BOUND'
    # ---- netlist for the views
    nl = None
    if nlpath and os.path.isfile(nlpath):
        try: nl = NL(nlpath, d['top'])
        except Exception as e: nl_note = f'The circuit file could not be read for drawing ({type(e).__name__}: {e}).'
    for c in cands:
        if not os.path.isfile(P(c)): continue
        try: cnl = NL(P(c), d['top'])
        except Exception: continue
        if (len(cnl.gates), len(cnl.dffs)) != (r['netlist']['gates'], r['netlist']['flops']): continue
        if d['build'] != 'stored':
            wit = [(f['net'], f['cycle']) for f in r['faults']] if atk else (r.get('_rec') or {}).get('wit')
            if not wit: continue                      # nothing to verify the stand-in against
            ids = _names_to_ids(cnl, wit)
            if ids is None: continue
            sg = (r.get('attacker_input_raw') or {}).get('sig') if atk else (r.get('_rec') or {}).get('wit_sig')
            if find_key(cnl, ids, cycles, goal, prefer=sg) is None: continue
            nl_note = (f'The recorded run did not keep its own circuit file. The pictures use the stored build {c} as a stand-in '
                       f'(same gate count and wire names); the recorded attack was re-checked on it by replay.')
            nl_standin = True
        nl, nlpath = cnl, P(c)
        break
    if nl is None and not nl_note:
        if r['_src'] == 'live':
            nl_note = 'The search was stopped before the circuit was built, so there is nothing to draw.'
        elif not atk and d['build'] != 'stored':
            nl_note = ('The circuit file of this recorded run was not kept, and a record without an attack gives nothing to check a stand-in circuit against, '
                       'so the time view and the circuit map are not drawn.')
        else:
            nl_note = ('The circuit file of this recorded run was not kept in the project, so the time view and the circuit map cannot be drawn. '
                       'The live engine draws them on a computer with z3 and Yosys.')
    if nl is not None and not r.get('netlist'):
        r['netlist'] = dict(gates=len(nl.gates), flops=len(nl.dffs))
    # ---- faults, replay, map
    rp = sch = own = None
    faults = []
    if nl is not None:
        if atk:
            if all('net_id' in f for f in r['faults']) and (r['_src'] == 'live' or d['build'] == 'stored'):
                faults = [(f['cycle'], f['net_id']) for f in r['faults']]
            else:
                faults = _names_to_ids(nl, [(f['net'], f['cycle']) for f in r['faults']]) or []
            sig = (r.get('attacker_input_raw') or {}).get('sig')
            keyfound = False
            if faults and (sig is None or d['build'] != 'stored' and r['_src'] == 'recorded'):
                s2 = find_key(nl, faults, cycles, goal, prefer=sig)
                keyfound = s2 is not None and sig is None
                sig = s2 if s2 is not None else sig
            if faults and sig is not None:
                rp = replay(nl, fam, sig, faults, cycles, goal)
                rp['key_from_replay'] = keyfound
                ok = rp['opens_at'] is not None and rp['clean_opens_at'] is None
                rp['verified'] = ok
                if keyfound:
                    r['attacker_input'] = {'sig': f'0x{sig:02X}'}
                L('replay', f"pure-Python re-simulation: {rp['goal_port']} == 0x{rp['goal_val']:X} at tick {rp['opens_at']} with the flips, never without ({rp['ms']} ms)" if ok
                  else 'REPLAY MISMATCH: the re-simulation did not reproduce the attack',
                  f"replayed the attack step by step: Accept is reached at tick {rp['opens_at']}; without the flips it never is" if ok
                  else 'the step-by-step replay did not reproduce the attack')
        elif none:
            rp = replay(nl, fam, 0x03, [], cycles, goal)
            rp['verified'] = True; rp['no_attack'] = True
        try:
            sch = dict(focus=schematic(nl, faults, True) if faults else None, full=schematic(nl, faults, False))
        except Exception as e:   # drawing must never break a result
            nl_note = nl_note or f'The circuit map could not be laid out ({type(e).__name__}: {e}).'
        own = ownership(nl, fam, rp) if goal == 'word' else None
        gb = nl.ports[goal_out]['bits']
        for f, (t, b) in zip(r.get('faults', []), faults):
            f['net_id'] = b
            f['kind'] = f.get('kind') or ('flop_Q' if b in nl.dq else 'gate_output')
            f['gate'] = nl.gates[b][0].strip('$_') if b in nl.gates else 'DFF'
            # result-bit positions this wire can still reach before Accept is observed (not the whole time window)
            left = (rp['opens_at'] - t) if (rp and rp.get('opens_at') is not None) else (cycles - 1 - t)
            f['reach'] = nl.reach_positions(b, gb, max(0, left)); f['reach_total'] = len(gb)
            f['key_bits'] = nl.in_support(b)
    for f in r.get('faults', []):
        f['plain'], f['group'] = pretty(f['net'])
    stale = r.pop('explanation', None)     # engine prose is never shown: the Studio writes its own text from the fault data
    honest = r.get('honest_key_boots_fault_free')
    if honest is not None:
        L('check', f"honest key 0xC3 boots fault-free: {'yes' if honest else 'NO'}", f"the right key still reaches Accept when nothing is flipped: {'yes' if honest else 'NO'}")
    if atk:
        L('DONE', f"ATTACK_FOUND min k={r['min_faults']}  N={cycles}  source={r['_src']}", f"finished: cheapest attack found uses {r['min_faults']} flip(s)")
    elif none:
        L('DONE', f"NO_ATTACK_UP_TO_BOUND k<={k}  N={cycles}  source={r['_src']}", f"finished: no attack found with up to {k} flip(s) in {cycles} ticks")
    else:
        L('DONE', f"UNKNOWN k<={k}  N={cycles}  source={r['_src']}  (no conclusion)", 'UNKNOWN: the search stopped before finishing; no conclusion, and this is not "no attack"')
    rec = r.get('_rec') or {}
    live = r['_src'] == 'live'
    if live and d['build'] == 'yosys': ysrc, yv = 'this run', YOSYS_V
    elif rec.get('yosys'): ysrc, yv = 'stated in the record', rec['yosys']
    elif nl_standin: ysrc, yv = 'header of the stand-in circuit file; the record itself stores none', nl.creator
    elif nl: ysrc, yv = 'header of the circuit file', nl.creator
    else: ysrc, yv = ('stated for these records by ' + str(rec.get('tools_source')), 'Yosys ' + rec['yosys_rec']) if rec.get('yosys_rec') else ('not stored', None)
    cmp_rec = None
    if live and stop is None:
        try:
            rr, _ = recorded(d, k, flow, goal, cycles) if cycles == 6 else (None, None)
            if rr is not None:
                cmp_rec = dict(verdict=rr['verdict'], min=rr.get('min_faults'), file=rr['_rec']['file'], derived=rr['_rec'].get('derived', False),
                               yosys=rr['_rec'].get('yosys') or (('Yosys ' + rr['_rec']['yosys_rec']) if rr['_rec'].get('yosys_rec') else None),
                               same=(rr['verdict'] == r['verdict'] and rr.get('min_faults') == r.get('min_faults')))
        except Exception:                      # noqa: BLE001
            cmp_rec = None
    prov = dict(source=r['_src'], engine=(f'glitchsat {ENGINE_VERSION} (scripts/glitchsat.py)' if live else rec.get('engine', 'scripts/glitchsat.py')),
                engine_version=ENGINE_VERSION, z3=(Z3V if live else (rec.get('z3_rec') + ' (when recorded)' if rec.get('z3_rec') else 'not stored in the record')),
                yosys=yv, yosys_from=ysrc, design=d['file'], design_sha=r.get('design_sha256_16'),
                netlist=os.path.relpath(nlpath, ROOT) if (nlpath and nl and nlpath.startswith(ROOT + os.sep)) else ('temporary build of this run' if (nlpath and nl) else None),
                netlist_sha=nl.sha() if nl else None, record=rec.get('file'), record_extra=rec.get('extra'), derived=rec.get('derived', False),
                k_rec=rec.get('k_rec'), cli=_cli(d, k, cycles, flow, goal), fault_model=r['bound']['fault_model'],
                attacker_input=r['bound']['attacker_input'], goal=r['bound']['goal'], nl_note=nl_note, nl_standin=nl_standin,
                min_rec=rec.get('min_rec'), studio=STUDIO_VERSION, time_limit_s=limit if live else None)
    r.update(_design=q['design'], _fam=fam, _code=FAMILY[fam]['code'], _name=FAMILY[fam]['name'], _what=FAMILY[fam]['what'], _build=d['build'],
             _flow=flow if d['build'] == 'yosys' else 'stored netlist', _goal=goal, _k=k, _cycles=cycles,
             _replay=rp, _map=sch, _own=own, _log=log, _prov=prov, _stop=stop, _cmp=cmp_rec)
    r.pop('_rec', None)
    return r

# ------------------------------------------------------------------ findings: recorded study datasets, read at request time
def _csv(rel):
    with open(P(rel), newline='') as f:
        return list(csv.DictReader(f))

def _f_synth():
    rel = 'research/c2/e2_variance/raw/matrix.csv'
    rows = _csv(rel)
    out = dict(source=rel, register='E2.v2.min, E2.v1.min, E2.v0.min (docs/NUMBERS.md)', designs={}, tiles=[])
    for des in ('v0', 'v1', 'v2'):
        rs = [r for r in rows if r['design'] == des]
        solved = [r for r in rs if r['status'] == 'SOLVED']
        cnt = collections.Counter(int(r['min_flips']) for r in solved)
        out['designs'][des] = dict(rows=len(rs), solved=len(solved), unsupported=len(rs) - len(solved), min={str(k): cnt.get(k, 0) for k in (1, 2, 3)})
    v2 = [r for r in rows if r['design'] == 'v2']
    out['tiles'] = [[r['build'], r['flow'], r['order'], r['abc'], r['merge'], r['keep'], r['status'] == 'SOLVED',
                     int(r['gates']) if r['gates'] else None, int(r['min_flips']) if r['status'] == 'SOLVED' else None] for r in v2]
    dist = {}
    for r in v2:
        if r['status'] == 'SOLVED': dist[r['sha256_canon']] = int(r['min_flips'])
    dc = collections.Counter(dist.values())
    out['distinct'] = dict(n=len(dist), min={str(k): dc.get(k, 0) for k in (1, 2, 3)})
    out['gates_max'] = max(int(r['gates']) for r in rows if r['gates'])
    out['builds'] = {'apt0.33': 'Yosys 0.33 (apt package)', 'conda-eda0.38': 'Yosys 0.38+92 (conda build a)', 'conda-formal0.38': 'Yosys 0.38+92 (conda build b)'}
    m = collections.Counter(int(r['min_flips']) for r in v2 if r['status'] == 'SOLVED' and r['merge'] == 'opt_merge')
    out['merge_on'] = {str(k): m.get(k, 0) for k in (1, 2, 3)}
    out['axes'] = {a: sorted({r[a] for r in v2}) for a in ('build', 'flow', 'order', 'abc', 'merge', 'keep')}
    return out

def _f_scope():
    rel = 'research/c2/b2_scope/matrix.jsonl'
    cells = []
    others = collections.defaultdict(set)
    for line in open(P(rel)):
        x = json.loads(line)
        if x['netlist'] != 'spike' or x['free_input']: continue
        if x['design'] == 'v2':
            cells.append(dict(goal=x['goal'], inputs=x['input_sites'], init=x['init'], min=x['min_cost'], verdict=x['verdict'],
                              faults=[[pretty(n)[0], n, t] for n, t in x['faults']]))
        else:
            others[x['design']].add(x['min_cost'])
    return dict(source=rel, register='B2.v2.spike.word, B2.v2.ok, B2.v2.in, B2.v2.nongoal (docs/NUMBERS.md)', cells=cells,
                others={k: sorted(v) for k, v in others.items()}, bound='stored V2 circuit, 6 ticks, limit 3 flips')

def _f_count():
    rel = 'research/c3/rep/rep_results.csv'
    rows = _csv(rel)
    out = dict(source=rel, register='REP.unit, REP.fanout (docs/NUMBERS.md)', designs={})
    for des in ('v1', 'v2'):
        rs = [r for r in rows if r['netlist'].startswith(des + '_')]
        out['designs'][des] = dict(n=len(rs), items=[[r['netlist'], int(r['gates']), int(r['rep_unit_cli']), int(r['rep_fanout_pins'])] for r in rs],
                                   stem=dict(collections.Counter(r['rep_unit_cli'] for r in rs)), fanout=dict(collections.Counter(r['rep_fanout_pins'] for r in rs)))
    return out

def _f_width():
    rel = 'research/c3/m1/m1_all_masks.csv'
    rows = _csv(rel)
    by = {r['mask_hex'].lower(): r for r in rows}
    stair = [int(by[m]['v2_spike_min_flips']) for m in ('0x01', '0x03', '0x07', '0x0f', '0x1f', '0x3f', '0x7f', '0xff')]
    nc = [r for r in rows if r['collides_with_legit_state'] == '0']
    four = [r for r in nc if r['popcount'] == '4']
    cnt = lambda rs: {str(k): sum(1 for r in rs if r['v2_spike_min_flips'] == str(k)) for k in (1, 2, 3)}
    masks = [[int(r['mask_hex'], 16), int(r['v2_spike_min_flips']), int(r['collides_with_legit_state']), int(r['copies_touched'])] for r in rows]
    return dict(source=rel, register='M1.width, M1.split, M1.four (docs/NUMBERS.md)', stair=stair, total=len(rows), noncolliding=len(nc),
                colliding=len(rows) - len(nc), split=cnt(nc), four=dict(n=len(four), split=cnt(four)), masks=masks)

def _f_enc():
    rel = 'research/c6/p01/sweep_rows.csv'
    rows = _csv(rel)
    out = dict(source=rel, register='P01.v2.apt.sweep, P01.v2e.apt.sweep, P01.cause (docs/NUMBERS.md); docs/report/WHY_TWO_FLIPS.md', sets=[])
    for ys in sorted({r['yosys'] for r in rows}):
        for des in ('v2', 'v2e'):
            rs = [r for r in rows if r['yosys'] == ys and r['design'] == des]
            if rs:
                out['sets'].append(dict(yosys=ys, design=des, armed=rs[0]['armed_const'], xor=rs[0]['xor_with_96'], copies=int(rs[0]['groups_touched']),
                                        flows=[[r['variant'], int(r['gates']), int(r['min_flips'])] for r in rs]))
    return out

def _f_valid():
    rel = 'validation/VALIDATION.md'
    with open(P(rel)) as fh:
        txt = fh.read()
    facts = [('v0', '19 successful single faults', 'V0: 19 of 120 single flips reach Accept with a wrong key', '120'),
             ('v1', 'exactly 1: net `ok` @ cycle 1, all 255 sigs', 'V1: exactly 1 of 396 single flips does: the shared "ok" wire at tick 1, for all 255 wrong keys', '396'),
             ('v2k1', '| V2 (A) | 1 | exhaustive, 456 | 0 |', 'V2: 0 of 456 single flips do', '456'),
             ('v2k2', 'T=6 (103,740 sets) | 0 |', 'V2: 0 of 103,740 pairs of flips do (6 ticks)', '103,740'),
             ('v2k2t4', 'T=4 (46,056 sets)', 'V2: 0 of 46,056 pairs of flips do (4 ticks)', '46,056'),
             ('v2k3', '(70,300 sets): 182 attacks', 'V2: 182 of 70,300 triples (all three flips at tick 1) do', '70,300'),
             ('replay', '13/13 CONFIRMED', '13 of 13 stored solver attacks confirmed by the independent simulator', '13'),
             ('tot', '~2.1M simulated fault sets x 255 inputs, 0 disagreements', 'About 2.1 million flip sets, each against all 255 wrong keys: 0 disagreements with the solver', '2.1M')]
    return dict(source=rel, register='F.valid, F.sets (docs/NUMBERS.md)',
                facts=[dict(id=i, text=plain, n=n, quote=q, confirmed=(q in txt)) for i, q, plain, n in facts],
                limits='Same fault model as the solver: this checks the solver encoding, not the physics. Triples at 6 ticks were not searched exhaustively.')

def _f_dial():
    rel = explainer_file('dial.json')
    if not rel: raise FileNotFoundError('dial.json not found in docs/explainers or docs/wow')
    d = _load(rel)
    cells = {}
    for k, v in d['cells'].items():
        if v.get('status') == 'measured':
            s = v.get('source') or {}
            cells[k] = dict(v=v['value'], w=[[pretty(x.split(' @ ')[0])[0], x] for x in (v.get('witness') or [])],
                            src=' · '.join(str(s.get(a)) for a in ('file', 'key', 'row') if s.get(a)), b=v.get('bound') or {}, yosys=v.get('yosys'), sha=v.get('netlist_sha256'))
    return dict(source=rel, register='P40.dial (docs/NUMBERS.md)', controls=d['controls'], order=d['meta']['key_order'], cells=cells,
                total=len(d['cells']), measured=len(cells))

FINDINGS = dict(dial=_f_dial, synth=_f_synth, scope=_f_scope, count=_f_count, width=_f_width, enc=_f_enc, valid=_f_valid)

# ------------------------------------------------------------------ local cache of live results
class Cache:
    """Results of study cells, keyed by netlist sha256 + engine version + z3 version + settings. Kept in ~/.cache/glitchsat-studio."""
    def __init__(self):
        self.lock = threading.Lock(); self.data = None; self.dirty = False
    def _load(self):
        if self.data is None:
            try:
                with open(os.path.join(CACHE_DIR, 'results.json')) as fh:
                    self.data = json.load(fh)
            except Exception:                  # noqa: BLE001
                self.data = {}
    def get(self, key):
        with self.lock:
            self._load(); return self.data.get(key)
    def put(self, key, val):
        with self.lock:
            self._load(); self.data[key] = val; self.dirty = True
    def save(self):
        with self.lock:
            if not self.dirty or self.data is None: return
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                tmp = os.path.join(CACHE_DIR, 'results.json.tmp')
                with open(tmp, 'w') as fh:
                    json.dump(self.data, fh)
                os.replace(tmp, os.path.join(CACHE_DIR, 'results.json')); self.dirty = False
            except OSError:
                pass
    def clear(self):
        with self.lock:
            self.data = {}; self.dirty = False
        shutil.rmtree(CACHE_DIR, ignore_errors=True)

CACHE = Cache()

def _sha_file(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()

def _key(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()

def _solve_key(netlist_sha, spec):
    return _key('solve', netlist_sha, ENGINE_VERSION, Z3V, spec)

def _synth_key(s):
    return _key('synth', YOSYS_V, s['mode'], s['text'], s['src_sha'], s.get('strip'))

def _synth_cached(s):
    p = os.path.join(CACHE_DIR, 'netlists', _synth_key(s) + '.json')
    return p if os.path.isfile(p) else None

# ------------------------------------------------------------------ one study cell = (optional Yosys build) + one engine call
class UnitStop(Exception):
    def __init__(self, state, note=''):
        self.state, self.note = state, note

def _unit_netlist(u, token, limit):
    if u.get('netlist'):
        p = P(u['netlist'])
        if not os.path.isfile(p): raise UnitStop('error', 'circuit file missing: ' + u['netlist'])
        return p
    s = u['synth']
    hit = _synth_cached(s)
    if hit: return hit
    td = tempfile.mkdtemp(dir=WORK)
    try:
        with open(P(s['src'])) as fh:
            text = fh.read()
        if s.get('strip') == 'regex': text = re.sub(r'\(\*\s*keep\s*\*\)\s*', '', text)      # as product synth_sweep (_KEEP_RE)
        elif s.get('strip') == 'literal': text = text.replace('(* keep *) ', '')               # as research/c2/e2_variance/scripts/matrix.py
        with open(os.path.join(td, 'design.v'), 'w') as fh:
            fh.write(text)
        if s['mode'] == 'script':
            with open(os.path.join(td, 'flow.ys'), 'w') as fh:
                fh.write(s['text'])
            argv = [YOSYS, '-q', '-s', 'flow.ys']
        else:
            argv = [YOSYS, '-q', '-p', s['text']]
        st, rc, out, err, secs = run_proc(argv, min(limit, 300), token, cwd=td)
        if st != 'ok': raise UnitStop('unknown', 'Yosys ' + ('hit the time limit' if st == 'timeout' else 'was stopped'))
        outp = os.path.join(td, 'netlist.json')
        if rc != 0 or not os.path.isfile(outp):
            raise UnitStop('error', 'Yosys could not build this configuration: ' + ((err or out).strip().splitlines() or ['no output'])[-1][:200])
        os.makedirs(os.path.join(CACHE_DIR, 'netlists'), exist_ok=True)
        dst = os.path.join(CACHE_DIR, 'netlists', _synth_key(s) + '.json')
        shutil.copyfile(outp, dst + '.tmp'); os.replace(dst + '.tmp', dst)
        return dst
    finally:
        shutil.rmtree(td, ignore_errors=True)

def _product_args(path, sp):
    a = ['analyze', path, '--top', sp['top'], '--config', P('product', 'src', 'faultbound_wt', 'examples', 'threat.toml'),
         '--max-flips', str(sp['max_flips']), '--cycles', str(sp['cycles'])]
    if sp.get('goal') == 'flag': a += ['--goal-out', 'boot_ok', '--accept-value', '1']
    if sp.get('mask') is not None: a += ['--consumer-bits', '0x%02X' % sp['mask']]
    a += ['--input-sites', sp.get('input_sites', 'none'), '--init', sp.get('init', 'known'), '--count-rule', sp.get('count_rule', 'stem')]
    return a

def _unit_solve(u, path, token, limit):
    sp = u['solve']
    eng = sp['engine']
    if eng in SOLVERS:                         # engines added with register_engine() (module tools)
        return SOLVERS[eng](u, path, token, limit)
    if eng == 'valid':                         # the project's z3-free exhaustive simulator (validation/*.py)
        st, rc, out, err, secs = run_proc([sys.executable] + [P(sp['script'])] + [P(a) if a.endswith('.json') else a for a in sp['args']], limit, token, cwd=P('validation'))
        if st != 'ok': raise UnitStop('unknown', 'stopped at the time limit' if st == 'timeout' else 'stopped')
        m = None
        for line in out.splitlines():
            m = re.search(sp['regex'], line) or m
        if rc != 0 or not m: raise UnitStop('error', ((err or out).strip().splitlines() or ['no output'])[-1][:200])
        a, b = int(m.group('succ')), int(m.group('total'))
        return dict(state='ok', v=[a, b], secs=secs)
    if eng == 'check':
        wd = tempfile.mkdtemp(dir=WORK)
        try:
            st, payload, secs = run_worker(dict(kind='check', src=path, top=sp['top'], k=sp['k'], cycles=sp['cycles'], goal_out=sp['goal_out'],
                                                goal_val=sp['goal_val'], flow=sp.get('flow', 'plain'), workdir=wd), limit, token)
        finally:
            shutil.rmtree(wd, ignore_errors=True)
        if st in ('timeout', 'stopped'): raise UnitStop('unknown', f'stopped at the time limit of {limit:g} s' if st == 'timeout' else 'stopped')
        if st == 'error': raise UnitStop('error', str(payload)[-200:])
        if payload['verdict'] == 'ATTACK_FOUND': return dict(state='ok', v=payload['min_faults'], secs=secs)
        if payload['verdict'] == 'NO_ATTACK_UP_TO_BOUND': return dict(state='ok', v=None, K=sp['k'], secs=secs)
        raise UnitStop('unknown', 'the solver returned "unknown"')
    # eng == 'product': the packaged CLI (product/src/faultbound_wt), which has the scope options
    st, payload, secs = run_worker(dict(kind='cell', args=_product_args(path, sp)), limit, token)
    if st in ('timeout', 'stopped'): raise UnitStop('unknown', f'stopped at the time limit of {limit:g} s' if st == 'timeout' else 'stopped')
    if st == 'error': raise UnitStop('error', str(payload)[-200:])
    code, rep, err = payload.get('exit'), payload.get('report') or {}, payload.get('stderr') or ''
    v = rep.get('verdict')
    if code == 2 or v == 'UNKNOWN_TIMEOUT': raise UnitStop('unknown', 'the solver returned "unknown"')
    if code in (3, 4) or v not in ('ATTACK_FOUND', 'NO_ATTACK_UP_TO_BOUND'):
        low = (err + ' ' + str(rep.get('note', ''))).lower()
        if 'unsupported' in low or 'has type' in low: raise UnitStop('unsupported', 'this build has gate types the engine does not model')
        raise UnitStop('error', (err.strip().splitlines() or [str(v or 'engine error')])[-1][:200])
    if rep.get('minimize_incomplete'): raise UnitStop('unknown', 'minimisation did not finish')
    if v == 'ATTACK_FOUND':
        n = rep.get('min_cost', rep.get('min_faults', 0)) if rep.get('faults') else 0
        return dict(state='ok', v=n, secs=secs, w=['%s @ tick %s' % (f.get('net'), f.get('cycle')) for f in (rep.get('faults') or [])][:6])
    return dict(state='ok', v=None, K=sp['max_flips'], secs=secs)

def _cmp(res, u):
    """match / mismatch / na against the recorded value of the same cell."""
    if res.get('state') != 'ok': return 'na'
    if u.get('expect') == 'none':              # ladder: fewer flips must give "no attack"
        return 'match' if res.get('v') is None else 'mismatch'
    rec = u.get('rec')
    if rec is None or u.get('rec_other'): return 'na'
    return 'match' if res.get('v') == rec else 'mismatch'

def run_unit(u, token, limit):
    t0 = time.time()
    res = None
    try:
        if u.get('skip'): raise UnitStop('skipped', u['skip'])
        path = _unit_netlist(u, token, limit) if (u.get('netlist') or u.get('synth')) else None
        sha = _sha_file(path) if path else None
        key = _solve_key(sha, u['solve']) if (sha or u['solve']['engine'] == 'valid') and not u.get('nocache') else None
        hit = CACHE.get(key) if key else None
        if hit:
            res = dict(hit, src='cached')
        else:
            res = _unit_solve(u, path or (P(u['solve']['src']) if u['solve'].get('src') else None), token, limit)
            res['src'] = 'live'; res['when'] = time.strftime('%Y-%m-%d %H:%M')
            if key: CACHE.put(key, {k: v for k, v in res.items() if k != 'src'})
        if sha: res['sha'] = sha[:12]
    except UnitStop as e:
        res = dict(state=e.state, note=e.note, src='live')
    except Exception as e:                     # noqa: BLE001
        res = dict(state='error', note=f'{type(e).__name__}: {e}'[:200], src='live')
    res['rec'] = u.get('rec'); res['cmp'] = _cmp(res, u)
    if u.get('rec_other'): res['rec_other'] = u['rec_other']
    res.setdefault('secs', round(time.time() - t0, 3))
    return res

def peek_unit(u):
    """Cached value of a cell without running anything (None if the build or the result is not in the cache)."""
    try:
        if u.get('skip') or u.get('nocache'): return None
        path = P(u['netlist']) if u.get('netlist') else (_synth_cached(u['synth']) if u.get('synth') else None)
        if (u.get('netlist') or u.get('synth')) and not (path and os.path.isfile(path)): return None
        sha = _sha_file(path) if path else None
        hit = CACHE.get(_solve_key(sha, u['solve']))
        if not hit: return None
        res = dict(hit, src='cached', rec=u.get('rec'))
        if sha: res['sha'] = sha[:12]
        res['cmp'] = _cmp(res, u)
        if u.get('rec_other'): res['rec_other'] = u['rec_other']
        return res
    except Exception:                          # noqa: BLE001
        return None

# ------------------------------------------------------------------ background jobs (/api/job)
JOBS, JOBQ, _JOB_THREADS, _JOB_LOCK, _JOB_SEQ = collections.OrderedDict(), queue.Queue(), [], threading.Lock(), [0]

class Job:
    def __init__(self, study, params, units, info):
        with _JOB_LOCK:
            _JOB_SEQ[0] += 1; self.id = 'j%d' % _JOB_SEQ[0]
        self.study, self.params, self.units, self.info = study, params, units, info
        self.results, self.done, self.total = {}, 0, len(units)
        self.status, self.started, self.ended = 'running', time.time(), None
        self.cancelled, self.tokens = False, []
        self.limit = max(2.0, min(float(params.get('time_limit_s', 120)), 3600.0))
        self.est = round(sum(u.get('est', 1.5) for u in units if not u.get('skip')) / NWORKERS, 1)
    def json(self, full=True):
        c = collections.Counter()
        for r in list(self.results.values()):
            c[r.get('cmp', 'na')] += 1; c['state_' + r.get('state', '?')] += 1; c['src_' + r.get('src', '?')] += 1
        o = dict(id=self.id, study=self.study, title=STUDIES[self.study]['title'], status=self.status, done=self.done, total=self.total,
                 elapsed=round((self.ended or time.time()) - self.started, 1), est_s=self.est, workers=NWORKERS, info=self.info, counts=dict(c), limit_s=self.limit)
        if full: o['results'] = dict(self.results)
        return o

def _job_loop():
    while True:
        job, u = JOBQ.get()
        try:
            if job.cancelled:
                res = dict(state='cancelled', src='live', rec=u.get('rec'), cmp='na')
            else:
                token = {}
                job.tokens.append(token)
                if job.cancelled: token['cancel'] = True
                res = run_unit(u, token, job.limit)
                if job.cancelled and res.get('state') == 'unknown': res['state'] = 'cancelled'
                try: job.tokens.remove(token)
                except ValueError: pass
            job.results[u['cell']] = res
        except Exception as e:                 # noqa: BLE001
            job.results[u['cell']] = dict(state='error', note=str(e)[:200], src='live', cmp='na')
        job.done += 1
        if job.done >= job.total:
            job.status = 'cancelled' if job.cancelled else 'done'; job.ended = time.time(); CACHE.save()
        elif job.done % 8 == 0:
            CACHE.save()

def start_job(study, params):
    if study not in STUDIES: return dict(error='unknown study')
    ok, why = study_available(study)
    if not ok: return dict(error=why)
    try:
        units, info = STUDIES[study]['plan'](params or {})
    except Exception as e:                     # noqa: BLE001
        return dict(error=f'This study could not be set up from the project files ({type(e).__name__}: {e}).')
    if not units: return dict(error='Nothing to run for this study on this computer.')
    for j in JOBS.values():                    # one run of a study at a time
        if j.study == study and j.status == 'running' and study != 'ladder':
            return dict(id=j.id, already=True)
    job = Job(study, params or {}, units, info)
    JOBS[job.id] = job
    while len(JOBS) > 40: JOBS.popitem(last=False)
    with _JOB_LOCK:
        while len(_JOB_THREADS) < NWORKERS:
            t = threading.Thread(target=_job_loop, daemon=True); t.start(); _JOB_THREADS.append(t)
    for u in units: JOBQ.put((job, u))
    return dict(id=job.id)

def cancel_job(jid):
    job = JOBS.get(jid)
    if not job: return dict(error='no such job')
    job.cancelled = True
    for t in list(job.tokens): t['cancel'] = True
    return dict(ok=True)

def cancel_everything():
    for j in list(JOBS.values()):
        if j.status == 'running': cancel_job(j.id)
    for t in list(RUNS.values()): t['cancel'] = True

# ------------------------------------------------------------------ studies: registry + plans (EXTENSION POINT)
# A study is {title, needs, plan}. plan(params) returns (units, info). A unit is a dict:
#   cell     id the page uses to place the value            rec   recorded value of the same cell (None if there is none)
#   netlist  repo-relative Yosys JSON, OR synth = {src, mode: script|p, text, strip, src_sha}   (design.v -> netlist.json in a private folder)
#   solve    {engine: product|check|valid, ...}             est   expected seconds (from recorded runtimes)
#   skip     reason this cell cannot be computed here (it then stays recorded)
# To add an analysis: write a plan function and call register_study(); the page reaches it through POST /api/job {study, params}.
STUDIES = collections.OrderedDict()

def register_study(sid, title, plan, needs=('z3',), heavy=False):
    STUDIES[sid] = dict(title=title, plan=plan, needs=tuple(needs), heavy=heavy)

def _have(need):
    if need == 'z3': return LIVE, 'the solver (z3) is not installed on this computer'
    if need == 'yosys': return bool(YOSYS), 'Yosys is not installed on this computer'
    if need == 'product': return os.path.isfile(P('product', 'src', 'faultbound_wt', 'cli.py')), 'this study runs only from a full copy of the project (a git clone); the installed app shows the saved results'
    if need == 'validation': return os.path.isfile(P('validation', 'netsim.py')), 'the validation scripts are not in the project folder'
    return True, ''

def study_available(sid):
    for n in STUDIES[sid]['needs']:
        ok, why = _have(n)
        if not ok: return False, why
    return True, ''

def _pspec(top, K=3, goal='word', mask=None, inputs=False, init='known', rule='stem'):
    return dict(engine='product', top=top, max_flips=K, cycles=6, goal=goal, mask=mask, input_sites='all' if inputs else 'none', init=init, count_rule=rule)

_SS = [None]
def _ss():
    """The eight documented build flows come from the packaged CLI itself (product/src/faultbound_wt/synth_sweep.py), not from a copy."""
    if _SS[0] is None:
        if P('product', 'src') not in sys.path: sys.path.insert(0, P('product', 'src'))
        from faultbound_wt import synth_sweep as SS
        _SS[0] = SS
    return _SS[0]

def _flow_synth(src, top, variant):
    SS = _ss()
    v = next(x for x in SS.builtin_variants() if x['name'] == variant)
    return dict(src=src, mode='script', text=SS.make_script(v, 'design.v', top, 'netlist.json'), strip='regex' if v.get('strip_keep') else None, src_sha=_sha_file(P(src)))

def _rec_yosys_label(kind):
    """Which recorded build, if any, was made with the Yosys version on this computer."""
    s = YOSYS_SHORT or ''
    if kind == 'e2': return 'apt0.33' if s == '0.33' else 'conda-eda0.38' if s.startswith('0.38+92') else None
    if kind == 'rep': return '033' if s == '0.33' else '038' if s.startswith('0.38+92') else None
    return None

def _plan_scope(p):
    units = []
    for line in open(P('research/c2/b2_scope/matrix.jsonl')):
        x = json.loads(line)
        if x['design'] != 'v2' or x['netlist'] != 'spike' or x['free_input']: continue
        init = {'known': 'known', 'free_nongoal': 'free_nongoal', 'free': 'arbitrary'}[x['init']]
        units.append(dict(cell='scope|%s|%d|%s' % (x['goal'], int(x['input_sites']), x['init']), rec=x['min_cost'], est=float(x.get('secs') or 1.5),
                          netlist='reference/spike_netlists/v2.json',
                          solve=_pspec('v2', 3, 'flag' if x['goal'] == 'boot_ok' else 'word', None, x['input_sites'], init)))
    return units, dict(note='stored V2 circuit, 6 ticks, limit 3 flips')

_DIAL_SRC = {'v0': ('reference/spike_netlists/v0.json', 'rtl/v0.v', 'v0'), 'v1': ('reference/spike_netlists/v1.json', 'rtl/v1.v', 'v1'),
             'v2': ('reference/spike_netlists/v2.json', 'rtl/v2.v', 'v2')}
def _plan_dial(p):
    rel = explainer_file('dial.json')
    if not rel: raise FileNotFoundError('dial.json')
    d = _load(rel)
    order = d['meta']['key_order']
    masks = {o['id']: int(o['mask'], 16) for o in d['controls']['reader'] if o.get('mask')}
    units = []
    for key, c in d['cells'].items():
        measured = c.get('status') == 'measured'
        if not measured and not p.get('all'): continue
        o = dict(zip(order, key.split('|')))
        stored, rtl, top = _DIAL_SRC[o['design']]
        u = dict(cell='dial|' + key, rec=c.get('value') if measured else None, est=1.8)
        if o['build'] == 'v2e' and o['design'] != 'v2':
            continue                                   # there is no re-encoded V0 or V1
        goal = 'flag' if o['reader'] == 'flag' else 'word'
        u['solve'] = _pspec('v2e' if o['build'] == 'v2e' else top, 3, goal, masks.get(o['reader']), o['inputs'] == 'yes',
                            {'known': 'known', 'nonopen': 'free_nongoal', 'any': 'arbitrary'}[o['power']])
        if o['build'] == 'stored':
            u['netlist'] = stored
        elif not YOSYS:
            u['skip'] = 'needs Yosys to rebuild the circuit'
        else:
            u['synth'] = _flow_synth('rtl/v2e.v' if o['build'] == 'v2e' else rtl, 'v2e' if o['build'] == 'v2e' else top, 'plain_opt_merge' if o['build'] == 'merge' else 'plain')
            ry = c.get('yosys')
            if measured and ry and YOSYS_SHORT and ('Yosys ' + YOSYS_SHORT + ' ') not in (ry + ' '):
                u['rec_other'] = 'recorded with ' + ry.split(' (')[0]
            elif measured and not ry:
                u['rec_other'] = 'recorded build: Yosys version not stored'
        units.append(u)
    return units, dict(note='limit 3 flips, 6 ticks', yosys=YOSYS_SHORT)

def _plan_width(p):
    rows = _csv('research/c3/m1/m1_all_masks.csv')
    stair = {0x01, 0x03, 0x07, 0x0F, 0x1F, 0x3F, 0x7F, 0xFF}
    units = []
    for r in rows:
        m = int(r['mask_hex'], 16)
        if not p.get('all') and m not in stair: continue
        units.append(dict(cell='width|%d' % m, rec=int(r['v2_spike_min_flips']), est=3.0, netlist='reference/spike_netlists/v2.json', solve=_pspec('v2', 3, 'word', m)))
    return units, dict(note='stored V2 circuit; ' + ('all 255 selections' if p.get('all') else 'the 8 "lowest n bits" selections'))

def _rep_abc():
    txt = open(P('research/c3/rep/scripts/gen_rep.sh')).read()
    m = re.search(r'ABC=\((.*?)\)\s*$', txt, re.M)
    return re.findall(r'"([^"]+)"', m.group(1))

def _plan_count(p):
    abc = _rep_abc()
    ver = _rec_yosys_label('rep')
    rec = {r['netlist']: r for r in _csv('research/c3/rep/rep_results.csv')}
    units = []
    sha = _sha_file(P('rtl/v2.v'))
    for fl in ('opt', 'plain'):
        pre = 'synth -top v2; dffunmap' if fl == 'opt' else 'proc; opt_clean; techmap; opt_clean'
        for i, a in enumerate(abc):
            # same command string as research/c3/rep/scripts/gen_rep.sh
            text = f'read_verilog design.v; hierarchy -top v2; {pre}; {a}; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json netlist.json'
            r = rec.get(f'v2_{fl}_{ver}_s{i}') if ver else None
            for rule, col in (('stem', 'rep_unit_cli'), ('fanout_pins', 'rep_fanout_pins')):
                rv = None
                if r:
                    try: rv = int(r[col])
                    except ValueError: rv = None
                units.append(dict(cell=f'count|{fl}|{i}|{rule}', rec=rv, est=float(r['max_solve_s']) + 0.3 if r else 2.0,
                                  synth=dict(src='rtl/v2.v', mode='p', text=text, strip=None, src_sha=sha), solve=_pspec('v2', 4, 'word', None, False, 'known', rule)))
    return units, dict(yosys=YOSYS_SHORT, rec_ver=ver, note='16 builds of V2 with the Yosys on this computer, two counting rules, limit 4')

def _plan_enc(p):
    SS = _ss()
    rows = _csv('research/c6/p01/sweep_rows.csv')
    mine = [r for r in rows if YOSYS_SHORT and r['yosys'].startswith('Yosys ' + YOSYS_SHORT + ' ')]
    units = []
    for des in ('v2', 'v2e'):
        for v in SS.builtin_variants():
            r = next((x for x in mine if x['design'] == des and x['variant'] == v['name']), None)
            units.append(dict(cell=f"enc|{des}|{v['name']}", rec=int(r['min_flips']) if r else None, est=1.2,
                              synth=_flow_synth(f'rtl/{des}.v', des, v['name']), solve=_pspec(des, 3)))
    return units, dict(yosys=YOSYS_SHORT, rec_yosys=mine[0]['yosys'] if mine else None, note='8 build flows x (V2, V2e), limit 3 flips, 6 ticks')

_E2 = [None]
def _e2():
    """The 96-configuration recipe is the study's own script generator (research/c2/e2_variance/scripts/matrix.py), loaded at run time."""
    if _E2[0] is None:
        import importlib.util
        sp = importlib.util.spec_from_file_location('e2_matrix', P('research/c2/e2_variance/scripts/matrix.py'))
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        _E2[0] = m
    return _E2[0]

def _plan_synth(p):
    M = _e2()
    label = _rec_yosys_label('e2')
    rec = {}
    if label:
        for r in _csv('research/c2/e2_variance/raw/matrix.csv'):
            if r['design'] == 'v2' and r['build'] == label:
                rec[(r['flow'], r['order'], r['abc'], r['merge'], r['keep'])] = int(r['min_flips']) if r['status'] == 'SOLVED' else 'unsupported'
    sha = _sha_file(P('rtl/v2.v'))
    units = []
    for fl in M.FLOWS:
        for o in M.ORDERS:
            for a in M.ABCS:
                for mg in M.MERGES:
                    for kp in M.KEEPS:
                        text = '\n'.join(M.script('v2', 'design.v', 'netlist.json', fl, o, a, mg)) + '\n'
                        rv = rec.get((fl, o, a, mg, kp))
                        units.append(dict(cell=f'synth|{fl}|{o}|{a}|{mg}|{kp}', rec=rv if isinstance(rv, int) else None, est=1.3,
                                          synth=dict(src='rtl/v2.v', mode='script', text=text, strip='literal' if kp == 'keep_off' else None, src_sha=sha),
                                          solve=_pspec('v2', 3)))
    return units, dict(yosys=YOSYS_SHORT, rec_build=label, note='96 build settings of V2 with the Yosys on this computer, limit 3 flips, 6 ticks')

_VALID = [  # cell, script, args, regex, est seconds (validation/VALIDATION.md "Commands"), recorded (successful, total)
    ('v0',     'validation/k1.py', ['reference/spike_netlists/v0.json', 'v0', '6'], r'successful.*?:\s*(?P<succ>\d+) of (?P<total>\d+)', 1, (19, 120)),
    ('v1',     'validation/k1.py', ['reference/spike_netlists/v1.json', 'v1', '6'], r'successful.*?:\s*(?P<succ>\d+) of (?P<total>\d+)', 1, (1, 396)),
    ('v2k1',   'validation/k1.py', ['reference/spike_netlists/v2.json', 'v2', '6'], r'successful.*?:\s*(?P<succ>\d+) of (?P<total>\d+)', 1, (0, 456)),
    ('v2k2t4', 'validation/k2.py', ['reference/spike_netlists/v2.json', 'v2', '4', '2'], r'(?P<total>\d+) fault sets.*successful sets=(?P<succ>\d+)', 6, (0, 46056)),
    ('v2k2',   'validation/k2.py', ['reference/spike_netlists/v2.json', 'v2', '6', '2'], r'(?P<total>\d+) fault sets.*successful sets=(?P<succ>\d+)', 17, (0, 103740)),
    ('v2k3',   'validation/k3c1.py', [], r'(?P<total>\d+) sets, successful=(?P<succ>\d+)', 20, (182, 70300)),
]
def _plan_valid(p):
    txt = open(P('validation/VALIDATION.md')).read().replace(',', '')
    units = []
    for cell, script, args, rx, est, rec in _VALID:
        ok = str(rec[1]) in txt                # the recorded pair is shown only if the file still states it
        units.append(dict(cell='valid|' + cell, rec=list(rec) if ok else None, est=est, nocache=False,
                          solve=dict(engine='valid', script=script, args=args, regex=rx, script_sha=_sha_file(P(script)), sim_sha=_sha_file(P('validation/netsim.py')),
                                     nl_sha=_sha_file(P(args[0])) if args else _sha_file(P('reference/spike_netlists/v2.json')))))
    return units, dict(note='exhaustive gate-level simulation without any solver (validation/k1.py, k2.py, k3c1.py); 255 wrong keys each')

def _plan_ladder(p):
    d = DESIGNS[p['design']]
    goal = 'flag' if p.get('goal') == 'flag' else 'word'
    goal_out, goal_val = ('boot_ok', 1) if goal == 'flag' else ('boot_word', 0x96)
    cycles = max(1, min(int(p.get('cycles', 6)), 12)); upto = max(0, min(int(p.get('upto', 0)), 4))
    flow = p.get('flow') if p.get('flow') in ('plain', 'opt') else 'plain'
    units = []
    for j in range(upto):
        u = dict(cell='ladder|%d' % j, rec=None, expect='none', est=1.5,
                 solve=dict(engine='check', top=d['top'], k=j, cycles=cycles, goal_out=goal_out, goal_val=goal_val, flow=flow, src=d['file']))
        if d['build'] == 'stored': u['netlist'] = d['file']
        else: u['nocache'] = True
        units.append(u)
    return units, dict(note='each smaller flip count searched on its own')

register_study('ladder', 'Check each smaller flip count separately', _plan_ladder, needs=('z3',))
register_study('scope',  'Assumption grid (12 settings)', _plan_scope, needs=('z3', 'product'))
register_study('dial',   'Assumption dial', _plan_dial, needs=('z3', 'product'))
register_study('width',  'Result bits that are read', _plan_width, needs=('z3', 'product'))
register_study('enc',    'Re-encoding experiment (8 build flows)', _plan_enc, needs=('z3', 'product', 'yosys'))
register_study('count',  'Counting rule (16 builds)', _plan_count, needs=('z3', 'product', 'yosys'))
register_study('synth',  'Build settings (96 with this Yosys)', _plan_synth, needs=('z3', 'product', 'yosys'), heavy=True)
register_study('valid',  'Independent check without a solver', _plan_valid, needs=('validation',))

# ------------------------------------------------------------------ finished modules shown as Explore views (3.0)
# Each module lives at tools/<module>/ in the repository. A work tree may also keep the modules in a folder `ext/` next
# to the folder of this file (or in $GLITCHSAT_EXT/<module>). Paths are always found relative to this file or the
# project, never from a fixed machine path. Module data is read at run time, never copied into this file.
_HERE_UP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_FALLBACK = os.environ.get('GLITCHSAT_EXT') or os.path.join(_HERE_UP, 'ext')
MOD_EXTRA = {'real': [os.environ.get('GLITCHSAT_REAL') or os.path.join(_HERE_UP, 'real')],
             'product': [os.path.join(ROOT, 'product')]}   # in the repository the evidence tools are product/ itself
MODULES = ('surface', 'harden', 'unbounded', 'shots', 'vlab', 'firmware', 'secboot_hw', 'product', 'real')

def mod_dirs(name):
    return [P('tools', name), os.path.join(EXT_FALLBACK, name)] + MOD_EXTRA.get(name, [])

def mod_dir(name):
    for d in mod_dirs(name):
        if d and os.path.isdir(d): return d
    return None

def _mrel(d):
    """Path shown to the user: relative to the project when inside it."""
    if not d: return None
    try:
        r = os.path.relpath(d, ROOT)
        return d if r.startswith('..') else r
    except ValueError:
        return d

def _jload(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)

def _mtime(path):
    try: return time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path)))
    except OSError: return None

SURFACE_NAMES = {   # file stem -> (design family, plain name, technical name)
    'surface_v0_T6': ('v0', 'Lock with one check', 'V0 stored, T=6'),
    'surface_v1_T6': ('v1', 'Lock with two checks joined by one wire', 'V1 stored, T=6'),
    'surface_v2_T6': ('v2', 'Lock with three copies', 'V2 stored, T=6'),
    'surface_v2_T4': ('v2', 'Lock with three copies, shorter time window', 'V2 stored, T=4'),
    'surface_v2_T6_k2': ('v2', 'Lock with three copies, at most 2 glitches', 'V2 stored, T=6, k<=2'),
    'surface_v2apt_T6': ('v2', 'Three copies, rebuilt with an older build tool', 'V2 apt Yosys 0.33, T=6'),
    'surface_v2flowB_T6': ('v2', 'Three copies, built so that the copies got merged', 'V2 flow B (flatten first), T=6'),
    'surface_v2inbuf_T6': ('v2', 'Three copies sharing their key-input wires', 'V2 with input buffers, T=6'),
}

def _m_surface(d):
    out = dict(designs=[], lint=None)
    for stem, (fam, plain, techn) in SURFACE_NAMES.items():
        f = os.path.join(d, 'results', stem + '.json')
        if not os.path.isfile(f): continue
        s = _jload(f)
        out['designs'].append(dict(id=stem, fam=fam, plain=plain, tech=techn, netlist=s.get('netlist'), top=s.get('top'), sha=(s.get('netlist_sha256') or '')[:16],
                                   cycles=(s.get('bound') or {}).get('cycles'), max_faults=(s.get('bound') or {}).get('max_faults'),
                                   verdict=s.get('verdict'), min_faults=s.get('min_faults'), count=s.get('count'), complete=s.get('complete'),
                                   stop_reason=s.get('stop_reason'), runtime_s=s.get('runtime_s'), sets=s.get('sets_simulated'), sites=s.get('sites_modelled'),
                                   nets=(s.get('nets') or [])[:18], cyc=s.get('cycles'), copies=s.get('copies'), touched=s.get('copies_touched'),
                                   examples=(s.get('attacks') or [])[:3], note=s.get('note'), file=_mrel(f), when=_mtime(f)))
    f = os.path.join(d, 'results', 'lint_validation.json')
    if os.path.isfile(f):
        lv = _jload(f)
        out['lint'] = dict(rows=[dict(netlist=r.get('netlist'), verdict=r.get('lint_verdict'), min=r.get('measured_min'), gates=r.get('gates'),
                                      recorded=r.get('recorded_min'), mode=r.get('lint_mode'), single=r.get('single_points'), first=r.get('first_points')) for r in lv.get('rows', [])][:60],
                           confusion=lv.get('confusion'), by_family=lv.get('confusion_by_family'), note=lv.get('note'), file=_mrel(f))
    return out

def _m_harden(d):
    f = os.path.join(d, 'studio', 'suggest_fix.json')
    s = _jload(f)
    s.pop('moves', None)
    s['file'] = _mrel(f); s['when'] = _mtime(f)
    return s

UB_MAIN = ['v0_stored', 'v1_stored', 'v2_stored', 'v2e_apt', 'v2_apt', 'v2_conda', 'v2_stored_ok', 'v2_flowB']
UB_PLAIN = {'v0_stored': 'Lock with one check', 'v1_stored': 'Lock with two checks joined by one wire', 'v2_stored': 'Lock with three copies',
            'v2_apt': 'Three copies, rebuilt with an older build tool', 'v2_conda': 'Three copies, rebuilt with a newer build tool',
            'v2e_apt': 'Three copies with one pattern changed, rebuilt', 'v2e_conda': 'Three copies with one pattern changed, newer build tool',
            'v2_stored_ok': 'Three copies, but only the single "open" signal is read', 'v2_flowB': 'Three copies, built so that the copies got merged',
            'v2_inbuf': 'Three copies sharing their key-input wires'}

def _m_unbounded(d):
    sm = _jload(os.path.join(d, 'results', 'summary.json'))
    rows = collections.OrderedDict()
    for r in sm.get('rows', []):
        if r.get('init') != 'known': continue
        rows.setdefault(r['design'], {})[r['k']] = r['verdict']
    designs = []
    for name, byk in rows.items():
        info = {}
        fk = os.path.join(d, 'results', '%s_k%d.json' % (name, max(byk)))
        if os.path.isfile(fk):
            j = _jload(fk)
            info = dict(netlist=j.get('netlist'), top=j.get('top'), origin=j.get('origin'), sha=j.get('netlist_sha256_16'), note=j.get('note'),
                        stats=j.get('netlist_stats'), goal=(j.get('scope') or {}).get('goal'))
            for sc in j.get('scopes', []):
                if sc.get('init') == 'known':
                    o = (sc.get('methods') or {}).get('oracle') or {}
                    if o.get('verdict') == 'attack': info['witness'] = dict(faults=o.get('faults'), cycles=o.get('cycles'), sig=(o.get('attacker_input') or {}).get('sig'), replayed=o.get('replayed'))
                    info['methods'] = {k: dict(verdict=v.get('verdict'), seconds=v.get('seconds'), method=v.get('method')) for k, v in (sc.get('methods') or {}).items()}
        proved = sorted(k for k, v in byk.items() if v == 'PROVED_UNBOUNDED')
        attack = min([k for k, v in byk.items() if v == 'ATTACK_FOUND'] or [None]) if any(v == 'ATTACK_FOUND' for v in byk.values()) else None
        designs.append(dict(id=name, plain=UB_PLAIN.get(name, name), main=name in UB_MAIN, proved=proved, attack=attack, verdicts={str(k): v for k, v in byk.items()},
                            unknown=sorted(k for k, v in byk.items() if v not in ('PROVED_UNBOUNDED', 'ATTACK_FOUND')), **info))
    designs.sort(key=lambda x: (UB_MAIN.index(x['id']) if x['id'] in UB_MAIN else 99, x['id']))
    f = os.path.join(d, 'results', 'summary.json')
    return dict(designs=designs, tool=sm.get('tool'), backend=sm.get('backend'), kmax=sm.get('kmax'), problems=sm.get('problems'),
                consistency=sm.get('consistency'), label=sm.get('label'), file=_mrel(f), when=_mtime(f))

SHOTS_PLAIN = {'v1': 'Lock with two checks', 'v2': 'Lock with three copies (as placed by the tools)', 'v2_v8': 'Three copies, pinned 8 µm apart',
               'v2_s8': 'Three copies, spread along a line', 'v2_v15': 'Three copies, pinned 15 µm apart', 'v2_rr': 'Three copies, round-robin placement'}

def _m_shots(d):
    full = _jload(os.path.join(d, 'results', 'shots_results.json'))
    out = dict(designs=[], labels=full.get('labels'), model=dict(T=(full.get('model') or {}).get('T'), rules=(full.get('model') or {}).get('rules'),
               aims=(full.get('model') or {}).get('aims')), unplaced=full.get('unplaced_designs'), generated=full.get('generated'), tool=full.get('tool'))
    for name, des in (full.get('designs') or {}).items():
        f = os.path.join(d, 'results', name + '_shared.json')
        sh = _jload(f) if os.path.isfile(f) else {}
        ex = sh.get('extra') or {}
        cells = [dict(n=c['name'], r=c['role'], x=c['x'], y=c['y'], w=c['w'], h=c['h'], m=c.get('master')) for c in des.get('cells', [])]
        out['designs'].append(dict(id=name, plain=SHOTS_PLAIN.get(name, name), note=des.get('note'), die=des.get('die_um'), rows=des.get('rows'), cells=cells,
                                   n_logic=des.get('n_logic_cells'), n_flops=des.get('n_flops'), files=des.get('files'),
                                   min_cost=sh.get('min_cost'), one_shot=ex.get('one_shot_radius_um'), steps=ex.get('min_shots_vs_radius'),
                                   attacks=[a for a in ex.get('attacks', []) if a.get('aim') == 'cell'][:40], honesty=sh.get('honesty'),
                                   sources=ex.get('spot_size_sources'), placement_note=ex.get('placement_note'), file=_mrel(f)))
    out['file'] = _mrel(os.path.join(d, 'results', 'shots_results.json'))
    return out

def _m_vlab(d):
    out = dict(designs=[])
    cf = os.path.join(d, 'results', 'comparison.json')
    comp = _jload(cf) if os.path.isfile(cf) else {}
    cmpd = {x['design']: x for x in comp.get('designs', [])}
    for name in ('v1', 'v2'):
        f = os.path.join(d, 'results', name + '_campaign.json')
        if not os.path.isfile(f): continue
        c = _jload(f)
        cells = [[x['offset'], x['period_ps'], x['counts'].get('SUCCESS', 0), x['counts'].get('CRASH', 0), x['counts'].get('NO_EFFECT', 0)] for x in c.get('cells', [])]
        cm = cmpd.get(name, {})
        out['designs'].append(dict(id=name, T=c.get('T'), offsets=c.get('offsets'), periods=c.get('periods_ps'), cells=cells, derate=(c.get('derate_sweep') or {}).get('rows'),
                                   sta=c.get('sta_flop_arrival_ps'), delay_model=c.get('delay_model'), honesty=c.get('honesty'), runtime_s=c.get('runtime_s'),
                                   engine_min=cm.get('engine_abstract_min_flips'), flop_min=cm.get('abstract_flop_only_single_cycle_min'),
                                   glitch=cm.get('glitch_campaign'), file=_mrel(f), when=c.get('generated')))
    out['honesty'] = comp.get('honesty')
    return out

def _m_firmware(d, q):
    f = os.path.join(d, 'results', 'studio_firmware.json')
    s = _jload(f)
    s.pop('sha3_engine', None)
    s['file'] = _mrel(f)
    v = q.get('variant') or 'rom_naive'; o = q.get('opt') or 'O0'; m = q.get('mode') or 'plain'
    if not re.fullmatch(r'rom_[a-z]+', v) or o not in ('O0', 'O1', 'O2', 'Os') or m not in ('plain', 'vol', 'barrier'):
        v, o, m = 'rom_naive', 'O0', 'plain'
    build = '%s-%s-%s-hw' % (v, o, m)
    src = os.path.join(d, 'src', v + '.c')
    lines = open(src, encoding='utf-8', errors='replace').read().splitlines() if os.path.isfile(src) else []
    marks = collections.defaultdict(dict)          # line -> model -> {hits, asm}
    found = 0
    raw = os.path.join(d, 'results', 'raw')
    if os.path.isdir(raw):
        for fn in sorted(os.listdir(raw)):
            if not fn.startswith(build + '__tampered_payload__'): continue
            try: r = _jload(os.path.join(raw, fn))
            except Exception: continue          # noqa: BLE001
            found += 1
            for h in (r.get('k1_hits') or []):
                if h.get('file') == v + '.c' and h.get('line'):
                    e = marks[h['line']].setdefault(r.get('model'), dict(n=0, asm=[], effect=h.get('effect')))
                    e['n'] += 1
                    if len(e['asm']) < 3 and h.get('asm') not in e['asm']: e['asm'].append(h.get('asm'))
            for w in (r.get('witness') or []):
                if r.get('min_faults', 0) and r.get('min_faults') > 1 and w.get('file') == v + '.c' and w.get('line'):
                    e = marks[w['line']].setdefault(r.get('model'), dict(n=0, asm=[], effect=w.get('effect'), multi=True))
                    e['multi'] = True
    s['source'] = dict(variant=v, opt=o, mode=m, build=build, file=_mrel(src), lines=lines, marks={str(k): v2 for k, v2 in marks.items()}, searches=found)
    return s

def _m_secboot(d):
    f = os.path.join(d, 'studio', 'secboot_hw.json')
    s = _jload(f)
    s['file'] = _mrel(f); s['when'] = _mtime(f)
    s['cloud_script'] = _mrel(os.path.join(d, 'cloud', 'cloud_run.sh')) if os.path.isfile(os.path.join(d, 'cloud', 'cloud_run.sh')) else None
    return s

def _evidence_dir(d):
    for c in ([os.path.join(d, 'product', 'examples', 'evidence'), os.path.join(d, 'examples', 'evidence')] if d else []) + [P('product', 'examples', 'evidence')]:
        if os.path.isdir(c): return c
    return None

def _m_product(d):
    e = _evidence_dir(d)
    if not e: raise FileNotFoundError('no examples/evidence folder')
    out = dict(designs=[], folder=_mrel(e))
    for name in ('v0', 'v1', 'v2'):
        mf = os.path.join(e, name + '_margin.json')
        if not os.path.isfile(mf): continue
        m = _jload(mf)
        m = m if isinstance(m, list) else [m]
        out['designs'].append(dict(id=name, rows=[dict(name=r.get('name'), min_faults=r.get('min_faults'), no_attack_up_to=r.get('no_attack_up_to'), status=r.get('status'),
                                                    headline=r.get('headline'), events=r.get('events'), psa_total=r.get('psa_total'), psa_levels=r.get('psa_levels'),
                                                    jil_total=r.get('jil_total'), jil_band=r.get('jil_band'), sensitivity=r.get('sensitivity'), disclaimer=r.get('disclaimer'),
                                                    target=(r.get('assumptions') or {}).get('target_psa_level'), fault_type=(r.get('assumptions') or {}).get('fault_type'),
                                                    minimum_source=r.get('minimum_source')) for r in m],
                                   html=('/mod/product/' + os.path.relpath(os.path.join(e, name + '_evidence.html'), d)) if d and os.path.isfile(os.path.join(e, name + '_evidence.html')) else None,
                                   file=_mrel(mf)))
    return out

def _m_real(d):
    res = os.path.join(d, 'results')
    files = sorted(os.listdir(res)) if os.path.isdir(res) else []
    out = dict(files=files, folder=_mrel(res), ready=None, adapter=None)
    for cand in ('studio_real.json', 'summary.json', 'results.json'):
        if cand in files:
            try: out['ready'] = _jload(os.path.join(res, cand)); out['ready_file'] = cand
            except Exception: pass             # noqa: BLE001
            break
    ex = os.path.join(res, 'experiments.json')
    rj = os.path.join(res, 'results.json')                  # the combined file (glitchsat-real-results/1), preferred when it lists experiments
    try:
        rr = _jload(rj) if os.path.isfile(rj) else {}
    except Exception:                          # noqa: BLE001  (may be half-written while the run is going)
        rr = {}
    if rr.get('experiments'): ex = rj
    if isinstance(rr.get('adapter_validation'), dict): out['adapter_all'] = rr['adapter_validation']
    out['about'] = rr.get('about')
    if os.path.isfile(ex):
        try:
            j = _jload(ex)
            def _g(e, old, new):               # experiments.json (flat) and results.json (under "glitchsat") name the same values differently
                v = e.get(old)
                if v is None: v = (e.get('glitchsat') or {}).get(new)
                return v
            def _mf(v):
                return v.get('min_faults') if isinstance(v, dict) else v
            def _sf(v):
                return {k: v.get(k) for k in ('min_faults', 'attacks', 'complete')} if isinstance(v, dict) else None
            out['experiments'] = [dict(id=e.get('id'), title=e.get('title'), netlist=e.get('netlist'), top=e.get('top'),
                                       flip=_mf(_g(e, 'margin_flip_model', 'min_faults_bit_flip')),
                                       synfi=_mf(_g(e, 'margin_synfi_model', 'min_faults_gate_replacement')), surface=_sf(_g(e, 'surface_flip_model', 'surface_bit_flip')),
                                       published=e.get('published') and {k: e['published'].get(k) for k in ('target', 'setting', 'simultaneous_faults', 'effective_percent', 'citation', 'where')},
                                       k1=(e.get('glitchsat_k1') or (e.get('glitchsat') or {}).get('k1_distinct') or {}).get('effective_percent', ((e.get('glitchsat') or {}).get('k1_distinct') or {}).get('percent')),
                                       k2=(e.get('glitchsat_k2') or (e.get('glitchsat') or {}).get('k2_distinct') or {}).get('effective_percent', ((e.get('glitchsat') or {}).get('k2_distinct') or {}).get('percent')),
                                       rerun=(lambda r: r and dict(effective_percent=r.get('effective_percent'), agrees=r.get('glitchsat_agrees_on') or (e.get('agreement') or {}).get('per_injection')))(((e.get('synfi_rerun') or e.get('synfi_rerun_here') or {}).get('s1')))) for e in j.get('experiments', [])]
            out['experiments_when'] = _mtime(ex); out['schema'] = j.get('schema')
            # comparison with the published tool (SYNFI): per-injection agreement, and whether a published figure is reproduced
            raw = {e.get('id'): e for e in j.get('experiments', [])}
            readme = ''
            try: readme = open(os.path.join(d, 'README.md'), encoding='utf-8', errors='replace').read()
            except OSError: pass
            out['reconciled'] = bool(re.search(r'(?i)\breconcil', readme)) and 'could not determine the cause' not in readme
            try:                               # the module's own reconciliation of the one figure that is not met exactly
                rc = _jload(os.path.join(res, 'e5_reconciliation.json')); fs = rc.get('in_fault_sets') or {}
                ov = next((v for k, v in (rc.get('synfi_own_verdicts') or {}).items() if 'glitchsat_effective' in k), {})
                if out['reconciled'] and fs.get('here') and fs.get('paper'):
                    out['recon'] = dict(id='E5', here=fs['here'], paper=fs['paper'], confirmed=[ov.get('synfi_sat'), ov.get('sets')] if ov else None)
            except Exception:                  # noqa: BLE001  (no such file: the row then says so)
                pass
            tot = [0, 0]
            for x in out['experiments']:
                e = raw.get(x['id']) or {}; g = e.get('glitchsat') or {}; pub = e.get('published') or {}
                m = re.fullmatch(r'(\d+)/(\d+)', str((e.get('agreement') or {}).get('per_injection') or ''))
                if m:
                    x['agree'] = [int(m.group(1)), int(m.group(2))]; tot[0] += x['agree'][0]; tot[1] += x['agree'][1]
                k = pub.get('simultaneous_faults')
                basis = g.get('k%s_synfi_list_basis' % k) if k in (1, 2) else None
                x['pub'] = dict(faults=k, percent=pub.get('effective_percent'), total=str(pub.get('total_injected')), flow=pub.get('flow')) if pub else None
                x['here'] = dict(injected=basis.get('injected_faults'), effective=basis.get('effective_faults'), percent=basis.get('effective_percent')) if basis else None
                x['status'] = _real_status(pub, basis)
                if x['status'] == 'differs':
                    mm = re.search(r'(?:against|prints)\s+(\d[\d,]*)\s+of\s+' + re.escape(str(pub.get('total_injected'))), readme)
                    if mm: x['pub']['eff'] = int(mm.group(1).replace(',', ''))
                    else:
                        try: x['pub']['eff'] = round(float(pub['effective_percent']) / 100 * int(str(pub['total_injected']).replace(',', ''))); x['pub']['eff_approx'] = True
                        except (KeyError, TypeError, ValueError): pass
            if tot[1]: out['agree'] = tot
            out['under_investigation'] = (not out['reconciled']) and any(x.get('status') == 'differs' for x in out['experiments'])
            by = rr.get('beyond') or {}
            run = next((r for r in ((by.get('ibex_pc_native') or {}).get('runs') or []) if r.get('verdict') == 'ATTACK_FOUND'), None)
            if run:
                sf = run.get('surface') or {}
                out['whole'] = dict(cycles=run.get('cycles'), min_faults=run.get('min_faults'), attacks=sf.get('attacks'), complete=sf.get('complete'))
            hl = ((by.get('lint') or {}).get('hier_lint') or [None])[0]
            if isinstance(hl, dict): out['lint'] = dict(cross=hl.get('cross_copy_reads'), verdict=hl.get('verdict'))
        except Exception as e:                 # noqa: BLE001  (the file may be half-written while the run is going)
            out['experiments_error'] = f'{type(e).__name__}'
    out['fsm'] = []
    for fn in files:
        if fn.startswith('fsm_state_') and fn.endswith('.json') and '_cadical' not in fn:     # *_cadical: the same run with a second solver
            try:
                j = _jload(os.path.join(res, fn))
                out['fsm'].append(dict(file=fn, second_solver=os.path.isfile(os.path.join(res, fn[:-5] + '_cadical.json')), experiment=j.get('experiment'), top=j.get('top'), cycles=j.get('cycles'), kmax=j.get('kmax'), rails=len(j.get('state_nets') or []),
                                       model=j.get('model'), summary=j.get('summary'), when=_mtime(os.path.join(res, fn))))
            except Exception:                  # noqa: BLE001
                pass
    if 'adapter_validation.json' in files:
        try:
            a = _jload(os.path.join(res, 'adapter_validation.json'))
            cc = a.get('cell_check') or {}
            out['adapter'] = dict(cell_pins=cc.get('cell_pins'), rows=cc.get('rows'), mismatches=cc.get('mismatches'), keys=[k for k in a.keys() if k != 'cell_check'])
        except Exception:                      # noqa: BLE001
            pass
    return out

def _real_status(pub, basis):
    """reproduced: the published count and percentage are met exactly; different_plan: the paper used another netlist; differs: same flow, other numbers."""
    if not pub: return 'none'
    if 'different netlist' in str(pub.get('flow') or ''): return 'different_plan'
    if not basis: return 'none'
    try:
        ps = str(pub.get('effective_percent')); pt = int(str(pub.get('total_injected')).replace(',', '')); pp = float(ps)
    except (TypeError, ValueError):
        return 'none'
    nd = len(ps.split('.')[1]) if '.' in ps else 0
    same = pt == basis.get('injected_faults') and abs(round(float(basis.get('effective_percent') or 0), nd) - pp) < 1e-9
    return 'reproduced' if same else 'differs'

MOD_READERS = dict(surface=_m_surface, harden=_m_harden, unbounded=_m_unbounded, shots=_m_shots, vlab=_m_vlab,
                   firmware=_m_firmware, secboot_hw=_m_secboot, product=_m_product, real=_m_real)

def mod_data(name, q=None):
    """One module's data for its Explore view; a missing or unreadable module gives a plain explanation, not an error page."""
    if name not in MOD_READERS: return dict(error='unknown module')
    d = mod_dir(name)
    looked = [_mrel(x) for x in mod_dirs(name)]
    if not d and name != 'product':
        return dict(missing=True, looked=looked)
    try:
        o = MOD_READERS[name](d, q or {}) if name == 'firmware' else MOD_READERS[name](d)
    except Exception as e:                     # noqa: BLE001
        return dict(broken=True, looked=looked, where=_mrel(d), detail=f'{type(e).__name__}: {e}'[:300])
    o['where'] = _mrel(d); o['looked'] = looked
    if name == 'firmware' and o.get('cells'):
        qq = q or {}
        v, op, md = qq.get('variant') or 'rom_naive', qq.get('opt') or 'O0', qq.get('mode') or 'plain'
        with_findings(o, 'from_firmware', o, variants=[v], opt=op, mode=md)
    o['in_repo'] = bool(d and os.path.abspath(d).startswith(os.path.abspath(P('tools')) + os.sep))
    return o

_PF = []
def plain_findings():
    """The shared plain-words explainer (findings module: tools/findings, or ext/findings next to the Studio's folder)."""
    if not _PF:
        m = None
        d = mod_dir('findings')
        if d and os.path.isfile(os.path.join(d, 'plain_findings.py')):
            try:
                import importlib.util as ilu
                sp = ilu.spec_from_file_location('plain_findings', os.path.join(d, 'plain_findings.py'))
                m = ilu.module_from_spec(sp); sp.loader.exec_module(m)
            except Exception as e:             # noqa: BLE001 - results still show without the explainer
                print(f'plain findings not loaded: {e}', file=sys.stderr); m = None
        _PF.append(m)
    return _PF[0]

def study_reference(q, r):
    """For a rebuilt lock: the stored chip plan of the same design, for the same goal and limits (the reference that
    pattern (a) compares against). None when there is no such stored result."""
    des = str(q.get('design') or '')
    if not des.endswith('_rtl') or des[:-4] not in DESIGNS:
        return None
    try:
        rr, _ = recorded(DESIGNS[des[:-4]], r.get('_k'), 'plain', r.get('_goal'), r.get('_cycles'))
    except Exception:                          # noqa: BLE001 - no reference: the finding says it cannot tell
        return None
    if rr is None:
        return None
    return dict(design=des[:-4], goal=r.get('_goal'), verdict=rr.get('verdict'),
                min=rr.get('min_faults') if rr.get('verdict') == 'ATTACK_FOUND' else None)

def with_findings(o, fn, *a, **kw):
    pf = plain_findings()
    if pf:
        try: o['findings'] = getattr(pf, fn)(*a, **kw)
        except Exception as e:                 # noqa: BLE001
            o['findings_error'] = f'{type(e).__name__}: {e}'[:200]
    return o

def chip_data():
    """The whole-chip view data (soc module, studio/explore_chip.json). Labels: BOUNDED = exact within T cycles; the
    Studio's PROVED (for any waiting time) is never used for these results."""
    d = mod_dir('soc')
    looked = [_mrel(x) for x in mod_dirs('soc')]
    f = os.path.join(d, 'studio', 'explore_chip.json') if d else None
    if not f or not os.path.isfile(f):
        return dict(missing=True, looked=looked)
    try:
        o = _jload(f)
    except Exception as e:                     # noqa: BLE001
        return dict(broken=True, where=_mrel(d), detail=f'{type(e).__name__}: {e}'[:300])
    for c in o.get('chips', []):               # an older file may still carry PROVED for bounded results: never show it
        for v in c.get('variants', []):
            for g in v.get('goals', []):
                if g.get('label') == 'PROVED': g['label'] = 'BOUNDED'
    o['file'] = _mrel(f); o['when'] = _mtime(f)
    for c in o.get('chips', []): with_findings(c, 'from_soc_chip', c)
    return o

def mod_index():
    return {n: dict(found=bool(mod_dir(n)) or (n == 'product' and bool(_evidence_dir(None))), where=_mrel(mod_dir(n)), looked=[_mrel(x) for x in mod_dirs(n)]) for n in MODULES}

MOD_FILE_EXT = ('.html', '.c', '.h', '.S', '.md', '.png', '.json', '.v', '.txt')

def mod_file(name, rel):
    d = mod_dir(name)
    if not d or not rel.endswith(MOD_FILE_EXT): return None
    p = os.path.realpath(os.path.join(d, rel))
    return p if p.startswith(os.path.realpath(d) + os.sep) and os.path.isfile(p) else None

# ---- live studies for the modules (EXTENSION POINT in use: register_engine + register_study)
SOLVERS = {}

def register_engine(name, fn):
    """fn(unit, path, token, limit) -> dict(state='ok', v=...). Lets a study call a tool that is not the GlitchSAT engine."""
    SOLVERS[name] = fn

def _mod_script(name, *rel):
    d = mod_dir(name)
    p = os.path.join(d, *rel) if d else None
    return p if p and os.path.isfile(p) else None

def _solve_lint(u, path, token, limit):
    sp = u['solve']
    argv = [sys.executable, _mod_script('surface', 'scripts', 'merge_lint.py'), path, '--top', sp['top'], '--json', '-'] + (['--copies', str(sp['copies'])] if sp.get('copies') else [])
    st, rc, out, err, secs = run_proc(argv, limit, token, cwd=ROOT)
    if st != 'ok': raise UnitStop('unknown', 'stopped at the time limit' if st == 'timeout' else 'stopped')
    try: j = json.loads(out)
    except ValueError: raise UnitStop('error', ((err or out).strip().splitlines() or ['no output'])[-1][:200])
    return dict(state='ok', v=j.get('verdict'), secs=secs, w=[x.get('net') if isinstance(x, dict) else str(x) for x in (j.get('single_points') or [])][:5])

def _solve_surface(u, path, token, limit):
    sp = u['solve']
    td = tempfile.mkdtemp(dir=WORK)
    try:
        outp = os.path.join(td, 's.json')
        argv = [sys.executable, _mod_script('surface', 'scripts', 'attack_surface.py'), path, '--top', sp['top'], '--cycles', str(sp['cycles']), '--k', str(sp['k']),
                '--method', 'exhaustive', '--json', outp]
        st, rc, out, err, secs = run_proc(argv, limit, token, cwd=ROOT)
        if st != 'ok': raise UnitStop('unknown', 'stopped at the time limit' if st == 'timeout' else 'stopped')
        if not os.path.isfile(outp): raise UnitStop('error', ((err or out).strip().splitlines() or ['no output'])[-1][:200])
        j = _jload(outp)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    if not j.get('complete'): raise UnitStop('unknown', 'the listing did not finish (%s)' % j.get('stop_reason'))
    return dict(state='ok', v=[j.get('min_faults'), j.get('count')], secs=secs)

def _solve_forever(u, path, token, limit):
    sp = u['solve']
    td = tempfile.mkdtemp(dir=WORK)
    try:
        outp = os.path.join(td, 'u.json')
        argv = [sys.executable, _mod_script('unbounded', 'src', 'unbounded.py'), 'check', path, '--top', sp['top'], '--k', str(sp['k']), '--out', outp,
                '--timeout', str(int(max(5, limit)))] + (['--goal-out', sp['goal_out'], '--goal-value', str(sp['goal_value'])] if sp.get('goal_out') else [])
        st, rc, out, err, secs = run_proc(argv, limit, token, cwd=ROOT)
        if st != 'ok': raise UnitStop('unknown', 'stopped at the time limit' if st == 'timeout' else 'stopped')
        if rc == 4: raise UnitStop('error', 'the methods disagreed, so no verdict was given')
        if rc == 2: raise UnitStop('unknown', 'a method hit its limit')
        if not os.path.isfile(outp): raise UnitStop('error', ((err or out).strip().splitlines() or ['no output'])[-1][:200])
        v = _jload(outp).get('verdict')
    finally:
        shutil.rmtree(td, ignore_errors=True)
    return dict(state='ok', v=v, secs=secs)

register_engine('lint', _solve_lint)
register_engine('surface', _solve_surface)
register_engine('forever', _solve_forever)

def _plan_lint(p):
    m = _m_surface(mod_dir('surface'))
    recs = {r['netlist']: r['verdict'] for r in ((m.get('lint') or {}).get('rows') or [])}
    units, seen = [], set()
    for x in m['designs']:
        if x['netlist'] in seen or not x['netlist']: continue
        seen.add(x['netlist'])
        units.append(dict(cell='lint|' + x['id'], netlist=x['netlist'], rec=recs.get(x['netlist']), est=0.3,
                          solve=dict(engine='lint', top=x['top'], copies=3 if x['fam'] == 'v2' else None, tool=_sha_file(_mod_script('surface', 'scripts', 'merge_lint.py')))))
    return units, dict(note='structural check of the copies (ext surface merge lint), milliseconds per circuit, no solver')

def _plan_surface(p):
    m = _m_surface(mod_dir('surface'))
    units = []
    for x in m['designs']:
        if not x['netlist'] or x['id'].endswith('_k2'): continue
        units.append(dict(cell='surface|' + x['id'], netlist=x['netlist'], rec=[x['min_faults'], x['count']], est=max(0.3, float(x.get('runtime_s') or 1)),
                          solve=dict(engine='surface', top=x['top'], cycles=x['cycles'], k=x['max_faults'] or 3, tool=_sha_file(_mod_script('surface', 'scripts', 'attack_surface.py')))))
    return units, dict(note='every cheapest attack listed by exhaustive simulation (no solver)')

def _plan_forever(p):
    m = _m_unbounded(mod_dir('unbounded'))
    units = []
    for x in m['designs']:
        if not x.get('netlist') or (not p.get('all') and not x['main']): continue
        ks = sorted(set([max(x['proved'])] if x['proved'] else []) | set([x['attack']] if x['attack'] is not None else []))
        for k in ks:
            sp = dict(engine='forever', top=x['top'], k=k, tool=_sha_file(_mod_script('unbounded', 'src', 'unbounded.py')))
            if x['id'] == 'v2_stored_ok': sp.update(goal_out='boot_ok', goal_value=1)
            units.append(dict(cell='forever|%s|%d' % (x['id'], k), netlist=x['netlist'], rec=x['verdicts'].get(str(k)), est=2.0, solve=sp))
    return units, dict(note='re-proves the largest proved budget and checks the smallest attack, for any number of steps (pure-Python solver, no z3)')

def _have_mod(need):
    if need == 'numpy':
        try:
            import numpy  # noqa: F401
            return True, ''
        except Exception:                      # noqa: BLE001
            return False, 'numpy is not installed on this computer'
    if need.startswith('mod:'):
        n = need[4:]
        return bool(mod_dir(n)), f'the {n} module is not in tools/{n}'
    return None

_have_base = _have
def _have(need):                               # noqa: F811  (extends the checks above with module needs)
    r = _have_mod(need)
    return r if r is not None else _have_base(need)

register_study('lint',    'Are the copies kept apart? (all saved circuits)', _plan_lint, needs=('mod:surface',))
register_study('surface', 'Every cheapest attack (exhaustive listing)', _plan_surface, needs=('mod:surface', 'numpy'))
register_study('forever', 'Proof for any number of steps', _plan_forever, needs=('mod:unbounded',))


def studies_status(peek=False):
    out = collections.OrderedDict()
    for sid, s in STUDIES.items():
        if sid == 'ladder': continue
        ok, why = study_available(sid)
        o = dict(title=s['title'], available=ok, reason=why, heavy=s['heavy'], needs=list(s['needs']))
        if ok:
            try:
                variants = [({}, 'run')] + ([({'all': True}, 'run_all')] if sid in ('dial', 'width') else [])
                for params, name in variants:
                    units, info = s['plan'](params)
                    todo = [u for u in units if not u.get('skip')]
                    o[name] = dict(cells=len(todo), skipped=len(units) - len(todo), est_s=round(sum(u.get('est', 1.5) for u in todo) / NWORKERS, 1))
                    if name == 'run': o['info'] = info
                    if peek:
                        cached = {}
                        for u in units:
                            r = peek_unit(u)
                            if r: cached[u['cell']] = r
                        o.setdefault('cached', {}).update(cached)
            except Exception as e:             # noqa: BLE001
                o.update(available=False, reason=f'could not be set up from the project files ({type(e).__name__}: {e})')
        running = next((j for j in JOBS.values() if j.study == sid and j.status == 'running'), None)
        last = next((j for j in reversed(list(JOBS.values())) if j.study == sid), None)
        o['job'] = (running or last).id if (running or last) else None
        out[sid] = o
    return out

def findings():
    out = {}
    for k, fn in FINDINGS.items():
        try: out[k] = fn()
        except Exception as e:     # a moved or missing file degrades one card, not the page
            out[k] = dict(error=f'{type(e).__name__}: {e}')
    d = explainer_dir()
    out['pages'] = [dict(file=n, title=t) for n, t in (('dial.html', 'Assumption dial'), ('wall.html', 'Build settings wall'), ('theatre.html', 'Attack replay'), ('explainer.html', 'Explainer'))
                    if d and os.path.isfile(P(d, n))]
    try: out['studies'] = studies_status(peek=True)
    except Exception as e:         # noqa: BLE001
        out['studies'] = {}; out['studies_error'] = f'{type(e).__name__}: {e}'
    out['local'] = dict(yosys=YOSYS_SHORT, e2_build=_rec_yosys_label('e2'), rep_ver=_rec_yosys_label('rep'), workers=NWORKERS)
    return out

def project_found():
    """Is ROOT a GlitchSAT project folder? (the engine file and the saved results the path needs)"""
    return os.path.isfile(P('scripts', 'glitchsat.py')) and os.path.isdir(P('results'))

def status():
    rt = _recorded_tools()
    return dict(project_found=project_found(), boot=BOOT_ID, live=LIVE, why=WHY, z3=Z3V, yosys=YOSYS_V, yosys_short=YOSYS_SHORT, root=ROOT, python=sys.version.split()[0],
                version=ENGINE_VERSION, studio=STUDIO_VERSION, engine='scripts/glitchsat.py', engine_present=os.path.isfile(P('scripts', 'glitchsat.py')),
                families={k: dict(code=v['code'], name=v['name'], what=v['what']) for k, v in FAMILY.items()},
                idle_limit_min=IDLE_LIMIT_S // 60, workers=NWORKERS, cache_dir=CACHE_DIR, recorded_tools=rt, browser=BROWSER_USED[0],
                studies=[k for k in STUDIES if k != 'ladder'],
                plugins=[p['name'] for p in PLUGINS], plugin_notes=PLUGIN_NOTES[:4], gallery=bool(gallery_dir()))

# ---- example gallery of the own-design tool: lesson texts and SAVED results, read as plain data files (nothing is run).
# This is what makes the hands-on part work on a computer without any build tool.
PLUGINS, PLUGIN_NOTES = [], []
PLUGIN_FILE = os.path.join('tools', 'studio', 'studio_byod.py')

def _plugin_candidates():
    here = os.path.dirname(os.path.abspath(__file__))
    c = [P(PLUGIN_FILE), os.path.join(here, 'studio_byod.py'), P('tools', 'byod', PLUGIN_FILE), os.path.join(EXT_FALLBACK, 'byod', PLUGIN_FILE)]
    if os.environ.get('GLITCHSAT_BYOD'): c.insert(0, os.path.join(os.environ['GLITCHSAT_BYOD'], PLUGIN_FILE))
    return [p for p in c if os.path.isfile(p)]

def gallery_dir():
    roots = []
    for p in _plugin_candidates():
        r = os.path.dirname(os.path.dirname(os.path.dirname(p)))
        roots += [r, os.path.join(r, 'byod')]
    roots += [P('tools', 'byod'), os.path.join(EXT_FALLBACK, 'byod')]
    for r in roots:
        d = os.path.join(r, 'examples')
        if os.path.isdir(d) and any(os.path.isfile(os.path.join(d, n, 'expected_results.json')) for n in os.listdir(d)):
            return d
    return None

def gallery():
    d = gallery_dir()
    if not d: return dict(missing=True)
    out = []
    for n in sorted(os.listdir(d)):
        lp, ep = os.path.join(d, n, 'lesson.json'), os.path.join(d, n, 'expected_results.json')
        if not (os.path.isfile(lp) and os.path.isfile(ep)): continue
        try: L, E = _jload(lp), _jload(ep)
        except Exception: continue             # noqa: BLE001
        runs = []
        for r in (L.get('runs') or []):
            key = (r.get('file') or 'glitchsat.yaml') + (' --task ' + r['task'] if r.get('task') else '')
            e = E.get(key) or {}
            for cid, c in (e.get('checks') or {}).items():
                ml = c.get('merge_lint') or {}
                runs.append(dict(label=r.get('label'), expect=r.get('expect'), key=key, check=cid, top=e.get('top'), frontend=e.get('frontend'),
                                 runtime_s=e.get('runtime_s'), verdict=c.get('verdict'), min_faults=c.get('min_faults'), max_faults=c.get('max_faults'),
                                 horizon=c.get('horizon'), witness=c.get('witness') or [], survival=c.get('survival'), unbounded=c.get('unbounded'),
                                 surface=c.get('attack_surface'), kept=ml if isinstance(ml, dict) else {}))
                break
        pf = plain_findings()
        for r in runs if pf else []:           # plain-words findings from the saved full report of the same run
            sp = os.path.join(d, n, 'saved', r['key'].replace('.yaml', '').replace(' --task ', '.') + '.report.json')
            try:
                rep = _jload(sp)
                fs = [f for f in pf.from_byod_report(rep) if f.get('tech', {}).get('check') == r['check']]
                for f in fs:
                    f['next']['check_cmd'] = 'glitchsat run %s' % r['key']
                r['findings'] = fs
            except Exception:                  # noqa: BLE001 - no saved report: the card says nothing extra
                pass
        out.append(dict(id=n, order=L.get('order', 99), title=L.get('title'), what=L.get('what'), why=L.get('why'), teaches=L.get('teaches'),
                        after=L.get('lesson_after'), runs=runs, file=_mrel(ep), when=_mtime(ep)))
    out.sort(key=lambda x: x['order'])
    return dict(examples=out, where=_mrel(d), yosys=bool(YOSYS_V))

# Sent with every response. Same policy as the plug-in asks for, except that pages of this app may frame each other
# (the Evidence report is a same-origin frame): frame-ancestors 'self', not 'none'.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")

class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def log_message(self, *a): pass
    def _send(self, code, body, ctype='application/json'):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if not getattr(self, '_csp', False):   # a launcher that wraps this class may already add its own policy
            self.send_header('Content-Security-Policy', CSP); self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(b)
    def _local(self):
        """Only this computer's own pages may talk to the server (blocks DNS rebinding and cross-site requests)."""
        host = (self.headers.get('Host') or '').lower()
        if host not in ('127.0.0.1:%d' % PORT[0], 'localhost:%d' % PORT[0]):
            return False
        org = self.headers.get('Origin')
        return not org or org.lower() in ('http://127.0.0.1:%d' % PORT[0], 'http://localhost:%d' % PORT[0])
    def _query(self):
        q = {}
        if '?' in self.path:
            for kv in self.path.split('?', 1)[1].split('&'):
                if '=' in kv:
                    a, b = kv.split('=', 1); q[a] = b
        return q
    def _touch(self, cid=None):
        cid = (cid or 'window')[:64]
        CLIENTS[cid] = time.time(); EVER_CLIENT[0] = True
    def do_GET(self):
        if not self._local(): return self._send(403, '{"error":"forbidden"}')
        path, q = self.path.split('?')[0], self._query()
        for pl in PLUGINS:                     # PLUGIN hook: a plug-in answers its own requests
            if pl['handle'](self, 'GET', path, q): return
        if labs_view and labs_view.handle(self, path, q, os.path.dirname(mod_dir('labs') or os.path.join(EXT_FALLBACK, 'labs'))): return   # LABS-VIEW hook (labs_view.py)
        if first_run_view and first_run_view.handle(self, 'GET', path, q, ROOT): return   # FIRST-RUN-VIEW hook (first_run_view.py)
        if path in ('/', '/index.html'):
            return self._send(200, PAGE, 'text/html')
        if path in ('/teach', '/project') and learn_view and hasattr(learn_view, 'page'):   # printable pages of the lesson module
            LAST_PAGE_GET[0] = time.time()
            return self._send(200, learn_view.page(path[1:], dict(theme=q.get('theme'), gallery=gallery(), version=ENGINE_VERSION, live=LIVE, yosys=bool(YOSYS_V))), 'text/html')
        if path == '/api/gallery':
            return self._send(200, json.dumps(gallery()))
        if path == '/api/ping':
            self._touch(q.get('cid')); return self._send(200, json.dumps(dict(boot=BOOT_ID)))   # boot id: a window notices a restart
        if path == '/api/status':
            return self._send(200, json.dumps(status()))
        if path == '/api/findings':
            return self._send(200, json.dumps(findings()))
        if path == '/api/studies':
            return self._send(200, json.dumps(studies_status()))
        if path == '/api/job':
            j = JOBS.get(q.get('id', ''))
            return self._send(200, json.dumps(j.json() if j else dict(error='no such job')))
        if path == '/api/jobs':
            return self._send(200, json.dumps([j.json(full=False) for j in JOBS.values()]))
        if path == '/api/severity':            # "How we decide severity": the one rule table of the explainer
            pf = plain_findings()
            return self._send(200, json.dumps(dict(rules=pf.SEVERITY_RULES, urgency=pf.URGENCY, levels=pf.LEVELS, icons=pf.ICON) if pf else dict(missing=True)))
        if path == '/api/chip':                # "Explore a real chip": the guided whole-chip view (data of the soc module)
            return self._send(200, json.dumps(chip_data()))
        if path == '/api/modules':
            return self._send(200, json.dumps(mod_index()))
        if path == '/api/mod':
            return self._send(200, json.dumps(mod_data(q.get('name', ''), {k: urllib.parse.unquote(v) for k, v in q.items()})))
        if path.startswith('/mod/'):
            parts = path[5:].split('/', 1)
            f = mod_file(parts[0], urllib.parse.unquote(parts[1])) if len(parts) == 2 and parts[0] in MODULES else None
            if f:
                LAST_PAGE_GET[0] = time.time()
                ct = {'.html': 'text/html', '.png': 'image/png', '.json': 'application/json'}.get(os.path.splitext(f)[1], 'text/plain')
                with open(f, 'rb') as fh:
                    return self._send(200, fh.read(), ct)
            return self._send(404, '{"error":"not found"}')
        if path.startswith('/pages/'):
            name = os.path.basename(path); d = explainer_dir()
            p = P(d, name) if d else ''
            if os.path.isfile(p) and name.endswith(('.html', '.json')):
                LAST_PAGE_GET[0] = time.time()
                with open(p, 'rb') as fh:
                    return self._send(200, fh.read(), 'text/html' if name.endswith('.html') else 'application/json')
        self._send(404, '{"error":"not found"}')
    def do_POST(self):
        # A custom header cannot be sent cross-site without a CORS preflight, which this server never answers.
        if not self._local() or self.headers.get('X-GlitchSAT') != '1':
            return self._send(403, '{"error":"forbidden"}')
        try:
            n = int(self.headers.get('Content-Length', 0) or 0)
            q = json.loads(self.rfile.read(n) or b'{}') if n < 1_000_000 else {}
            if not isinstance(q, dict): raise ValueError('not an object')
        except Exception:                      # noqa: BLE001
            return self._send(400, '{"error":"bad request"}')
        path = self.path.split('?')[0]
        for pl in PLUGINS:                     # PLUGIN hook (before the window bookkeeping: plug-in requests carry no window id)
            if pl['handle'](self, 'POST', path, q): return
        if first_run_view and first_run_view.handle(self, 'POST', path, q, ROOT): return  # FIRST-RUN-VIEW hook (first_run_view.py)
        if path == '/api/bye':                 # sent by a window when it closes
            CLIENTS.pop(str(q.get('cid') or 'window')[:64], None); LAST_BYE[0] = time.time()
            return self._send(200, '{}')
        self._touch(q.get('cid'))
        try:
            if path == '/api/analyze':
                if not isinstance(q.get('design'), str) or q.get('design') not in DESIGNS:
                    return self._send(400, '{"error":"unknown design"}')
                res = analyze(q)
                if isinstance(res, dict) and not res.get('error'):
                    res['_ref'] = study_reference(q, res)
                    with_findings(res, 'from_studio_result', res, q)
                return self._send(200, json.dumps(res))
            if path == '/api/stop':
                t = RUNS.get(str(q.get('run_id') or ''))
                if t: t['cancel'] = True
                return self._send(200, json.dumps(dict(ok=bool(t))))
            if path == '/api/job':
                return self._send(200, json.dumps(start_job(str(q.get('study')), q.get('params') if isinstance(q.get('params'), dict) else {})))
            if path == '/api/job/cancel':
                return self._send(200, json.dumps(cancel_job(str(q.get('id')))))
            if path == '/api/cache/clear':
                CACHE.clear(); return self._send(200, '{"ok":true}')
        except Exception as e:                 # noqa: BLE001
            return self._send(200, json.dumps(dict(error='The Studio hit an internal error.', error_kind='engine', error_detail=f'{type(e).__name__}: {e}')))
        self._send(404, '{"error":"not found"}')

LAST_BYE = [0.0]

PAGE = r'''<!doctype html><html lang="en" data-theme="dark" data-view="plain"><head><meta charset="utf-8">
<title>GlitchSAT Studio</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0e1116;--panel:#151a21;--raised:#1b222b;--inset:#10141a;--line:#2a323d;--line2:#39434f;--txt:#e3e8ee;--mut:#96a1af;--dim:#7d8996;
--acc:#4c8dff;--acc-t:#0b1220;--hot:#ff6b4a;--warn:#e0a13a;--c0:#38bdf8;--c1:#c297ff;--c2:#3ecfbe;--shared:#aab4c0;
--f0:#e5534b;--f1:#e8833a;--f2:#cfa646;--f3:#6ea0d8;--f4:#5687c4;--none:#9aa5b1;--ok:#8fb8a8;
--mono:ui-monospace,"DejaVu Sans Mono","Liberation Mono",Menlo,Consolas,monospace;
--sans:system-ui,-apple-system,"Segoe UI",Ubuntu,"Noto Sans","DejaVu Sans",sans-serif}
html[data-theme=light]{--bg:#f3f5f8;--panel:#ffffff;--raised:#f0f3f7;--inset:#f7f9fb;--line:#d5dbe3;--line2:#bcc5d0;--txt:#18212c;--mut:#4f5c6b;--dim:#5b6774;
--acc:#1f63d8;--acc-t:#ffffff;--hot:#b8371e;--warn:#8a5700;--c0:#0a6c9f;--c1:#7a4bd1;--c2:#08766b;--shared:#5b6775;
--f0:#c63a33;--f1:#c9641a;--f2:#9a7412;--f3:#2f6fb5;--f4:#255a96;--none:#5d6975;--ok:#3d7a66}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font:13px/1.45 var(--sans);font-variant-numeric:tabular-nums}
button,select,input{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--acc);outline-offset:1px}
.mono{font-family:var(--mono)}
:not(text).mono{font-size:12px}
.app{display:grid;grid-template-columns:288px minmax(0,1fr);grid-template-rows:44px minmax(0,1fr) 26px;height:100vh}
/* ---- header */
header{grid-column:1/3;display:flex;align-items:center;gap:6px;padding:0 12px;border-bottom:1px solid var(--line);background:var(--panel)}
.logo{display:flex;align-items:center;gap:9px;font-weight:650;font-size:14px;letter-spacing:.1px;margin-right:6px;white-space:nowrap}
.logo svg{width:22px;height:22px}
.logo small{display:block;font-weight:400;font-size:11.5px;color:var(--mut);letter-spacing:0;margin-top:-2px}
.tabs{display:flex;height:100%;margin-left:10px}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:0 13px;color:var(--mut);height:100%;font-weight:500}
.tab:hover{color:var(--txt)}
.tab.on{color:var(--txt);border-bottom-color:var(--acc)}
.hsp{flex:1}
.seg{display:inline-flex;background:var(--inset);border:1px solid var(--line);border-radius:5px;padding:2px}
.seg button{background:none;border:0;padding:3px 10px;border-radius:3px;color:var(--mut);font-size:12px;white-space:nowrap}
.seg button.on{background:var(--raised);color:var(--txt);box-shadow:0 0 0 1px var(--line2)}
.seg button:disabled{opacity:.4;cursor:not-allowed}
.hlabel{font-size:11.5px;color:var(--mut);margin:0 2px 0 8px}
.btn{background:var(--raised);border:1px solid var(--line);border-radius:5px;padding:4px 10px;font-size:12px;white-space:nowrap}
.btn:hover{border-color:var(--line2)}
a.btn{text-decoration:none;color:var(--txt);display:inline-block}
td .mono{word-break:break-all}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn.ico{width:28px;padding:4px 0;text-align:center}
/* ---- sidebar */
aside{border-right:1px solid var(--line);background:var(--panel);display:flex;flex-direction:column;min-height:0}
.side-scroll{flex:1;overflow:auto;padding:8px 12px 6px;min-height:0}
h3{font-size:11.5px;letter-spacing:.9px;text-transform:uppercase;color:var(--mut);margin:10px 0 4px;font-weight:600}
h3:first-child{margin-top:0}
.step{display:flex;gap:8px;align-items:center;width:100%;text-align:left;background:none;border:1px solid transparent;border-radius:5px;padding:1px 6px;margin-bottom:0}
.step:hover{background:var(--raised)}
.step.on{background:var(--raised);border-color:var(--line2)}
.step .n{flex:none;width:18px;height:18px;border-radius:50%;border:1px solid var(--line2);font-size:11.5px;display:flex;align-items:center;justify-content:center;color:var(--mut)}
.step.on .n{background:var(--acc);border-color:var(--acc);color:var(--acc-t)}
.step.done .n{color:var(--txt);border-color:var(--mut)}
.step b{display:block;font-size:12.5px;font-weight:550;line-height:1.2}
.step span.s{font-size:11.5px;color:var(--mut);line-height:1.2;display:block}
.step .r{margin-left:auto;font:600 11px var(--mono);color:var(--mut)}
.fld{margin:6px 0 0}
.fld>label{display:flex;justify-content:space-between;font-size:11.5px;color:var(--mut);margin-bottom:3px}
.fld>label b{color:var(--txt);font-weight:600}
.fld .seg{display:flex}.fld .seg button{flex:1;padding:4px 4px}
.fld .hint{font-size:11.5px;color:var(--dim);margin-top:2px;line-height:1.3}
select{width:100%;background:var(--inset);border:1px solid var(--line);border-radius:5px;padding:5px 6px}
input[type=range]{width:100%;accent-color:var(--acc);margin:0;height:18px}
input[type=range]:disabled{opacity:.45}
.runbar{padding:8px 12px;border-top:1px solid var(--line);background:var(--panel)}
.run{width:100%;padding:8px;border:1px solid var(--acc);border-radius:5px;background:var(--acc);color:var(--acc-t);font-weight:650;font-size:13px;display:flex;justify-content:center;gap:10px;align-items:center}
.run kbd{font:11px var(--mono);opacity:.75;border:1px solid currentColor;border-radius:3px;padding:0 4px}
.run:disabled{opacity:.6;cursor:progress}
.runbar .hint{font-size:11.5px;color:var(--mut);margin-top:5px;line-height:1.3}
/* ---- main */
main{display:flex;flex-direction:column;min-height:0;min-width:0}
.view{flex:1;overflow:auto;padding:12px 14px 16px;min-height:0}
.hidden{display:none!important}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;margin-bottom:10px}
.ph{display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--line);min-height:32px}
.ph h4{margin:0;font-size:12px;font-weight:600;letter-spacing:.2px}
.ph .sp{flex:1}
.pb{padding:10px}
.cap{font-size:12px;color:var(--mut);padding:7px 10px;border-top:1px solid var(--line);line-height:1.45}
.cap b.w{color:var(--txt);font-weight:600}
.chip{display:inline-flex;align-items:center;gap:5px;font:600 11px var(--sans);letter-spacing:.6px;text-transform:uppercase;padding:2px 7px;border-radius:3px;border:1px solid var(--line2);color:var(--mut);white-space:nowrap}
.chip.live{color:var(--acc);border-color:var(--acc)}
.chip.rec{color:var(--c1);border-color:var(--c1)}
.chip.sim{color:var(--mut)}
.chip.warn{color:var(--warn);border-color:var(--warn)}
.term{border-bottom:1px dotted var(--mut);cursor:help}
/* tour strip */
.story{display:flex;gap:12px;align-items:center;padding:8px 12px;border-left:3px solid var(--acc)}
.story .stx{flex:1;min-width:0}
.story h2{margin:0;font-size:14px;font-weight:650}
.story p{margin:1px 0 0;color:var(--mut);font-size:12.5px}
.story .take{color:var(--txt);margin-top:3px}
.story .nav{display:flex;gap:6px;align-items:center;flex:none}
.story .cnt{font-size:11.5px;color:var(--mut);margin-right:4px;white-space:nowrap}
/* verdict */
.verdict{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:14px;align-items:center;padding:10px 12px}
.vnum{min-width:74px;height:62px;border-radius:5px;border:1px solid var(--vc);background:color-mix(in srgb,var(--vc) 13%,transparent);display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--vc)}
.vnum b{font-size:28px;line-height:1;font-weight:700}
.vnum span{font-size:11.5px;letter-spacing:.8px;text-transform:uppercase;margin-top:3px}
.vt{font-size:17px;font-weight:650;line-height:1.25}
.vt .chip{vertical-align:3px;margin-left:8px}
.vm{color:var(--mut);margin-top:2px;font-size:12.5px;max-width:860px}
.vm b{color:var(--txt);font-weight:600}
.ladder{display:flex;gap:3px;align-items:flex-end}
.ladder div{width:44px;text-align:center;border:1px solid var(--line);border-radius:4px;padding:3px 0;font-size:11.5px;color:var(--mut);line-height:1.25}
.ladder div b{display:block;font-size:13px;color:var(--txt)}
.ladder div.hit{border-color:var(--vc);color:var(--vc)}.ladder div.hit b{color:var(--vc)}
.ladder-t{font-size:11.5px;color:var(--mut);margin-bottom:3px;text-align:right}
.bound{display:flex;flex-wrap:wrap;gap:4px 14px;padding:6px 12px;border-top:1px solid var(--line);font-size:11.5px;color:var(--mut)}
.bound b{color:var(--txt);font-weight:600}
.bound .k{color:var(--dim);margin-right:4px}
.prov{display:flex;flex-wrap:wrap;gap:3px 14px;padding:5px 12px;border-top:1px solid var(--line);font-size:11.5px;color:var(--mut);align-items:center}
.prov .k{color:var(--dim);margin-right:4px}
.prov .v{font-family:var(--mono);color:var(--txt);font-size:11.5px}
details.more{border-top:1px solid var(--line)}
details.more>summary{padding:5px 12px;font-size:11.5px;color:var(--mut);cursor:pointer;list-style:none}
details.more>summary::before{content:"▸ ";color:var(--dim)}
details.more[open]>summary::before{content:"▾ "}
details.more .kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:3px 10px;padding:2px 12px 10px;font-size:11.5px}
details.more .kv div:nth-child(odd){color:var(--mut)}
details.more .kv div:nth-child(even){font-family:var(--mono);font-size:11.5px;word-break:break-all}
.cols{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(300px,1fr);gap:10px;align-items:start}
.cols .panel{margin-bottom:10px}
/* tables */
table{width:100%;border-collapse:collapse}
td,th{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;font-size:12px;vertical-align:top}
tr:last-child td{border-bottom:0}
th{color:var(--mut);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.6px;background:var(--inset)}
tr.frow{cursor:pointer}tr.frow:hover td{background:var(--raised)}
.dot{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;vertical-align:0}
.bolt{color:var(--hot)}
/* waveform + map svg */
svg text{font-family:var(--sans);fill:var(--txt)}
svg .m{fill:var(--mut)}svg .d{fill:var(--dim)}
svg .mono{font-family:var(--mono)}
.wave{display:block;width:100%;user-select:none}
.wave:focus-visible{outline-offset:-2px}
.mapwrap{overflow:auto;max-height:560px;background:var(--inset)}
.gate{fill:var(--panel);stroke:var(--shared);stroke-width:1.3}
.wire{fill:none;stroke:var(--line2);stroke-width:1.1}
.wire.cone{stroke:var(--mut)}
.wire.hot{stroke:var(--hot);stroke-width:1.7}
.wire.hl{stroke:var(--acc);stroke-width:2}
.node.dimmed{opacity:.35}
.node:hover .gate{stroke-width:2.2}
.node.pulse .gate{animation:pulse 1.2s ease-out 2}
@keyframes pulse{0%{stroke-width:6}100%{stroke-width:1.3}}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:11.5px;color:var(--mut);align-items:center}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
.legend i.sq{height:10px;width:10px;border-radius:2px}
/* ownership */
.own{display:grid;grid-template-columns:repeat(8,1fr);gap:4px}
.ob{border:1px solid var(--oc);border-radius:4px;text-align:center;padding:4px 0 3px;background:color-mix(in srgb,var(--oc) 10%,transparent)}
.ob.chg{box-shadow:inset 0 -3px 0 var(--oc)}
.ob .i{font-size:11.5px;color:var(--mut)}
.ob .c{font-weight:650;font-size:12px;color:var(--oc)}
.ob .v{font:11px var(--mono);color:var(--txt)}
.ob .v s{text-decoration:none;color:var(--dim)}
/* log */
.logdock{flex:none;border-top:1px solid var(--line);background:var(--panel)}
.logbar{display:flex;align-items:center;gap:8px;padding:0 10px;height:26px;cursor:pointer;font-size:11.5px;color:var(--mut)}
.logbar b{color:var(--txt);font-weight:600;font-size:11.5px;letter-spacing:.6px;text-transform:uppercase}
.logbar .last{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--mono);font-size:11.5px}
.logbody{height:132px;overflow:auto;padding:4px 10px 8px;font:11.5px/1.55 var(--mono);border-top:1px solid var(--line);background:var(--inset);white-space:pre-wrap}
.logbody .t{color:var(--dim)}.logbody .g{color:var(--acc)}.logbody .p{color:var(--mut)}.logbody .e{color:var(--hot)}.logbody .ok{color:var(--txt);font-weight:600}
.logdock:not(.open) .logbody{display:none}
/* status bar */
footer{grid-column:1/3;border-top:1px solid var(--line);font-size:11.5px;color:var(--mut);display:flex;align-items:center;padding:0 10px;gap:0;background:var(--panel);white-space:nowrap;overflow:hidden}
footer span.i{padding:0 9px;border-right:1px solid var(--line);height:100%;display:flex;align-items:center;gap:5px}
footer span.i:first-child{padding-left:0}
footer .mono{font-size:11.5px;color:var(--txt)}
footer .credit{margin-left:auto;padding-left:10px}
.led{width:7px;height:7px;border-radius:50%;background:var(--c1)}.led.live{background:var(--acc)}.led.off{background:var(--hot)}.led.busy{background:var(--warn);animation:bl .8s infinite alternate}
@keyframes bl{to{opacity:.3}}
/* states */
.empty{color:var(--mut);text-align:center;padding:54px 20px;border:1px dashed var(--line2);border-radius:6px}
.empty b{display:block;color:var(--txt);font-size:15px;margin-bottom:4px}
.empty kbd,.kb kbd{font:11px var(--mono);border:1px solid var(--line2);border-radius:3px;padding:1px 5px;background:var(--raised)}
.err{border:1px solid var(--hot);border-radius:6px;padding:12px 14px;background:color-mix(in srgb,var(--hot) 8%,transparent)}
.err b{display:block;font-size:14px;margin-bottom:3px}.err p{margin:3px 0;color:var(--mut)}
.busy{opacity:.42;pointer-events:none;transition:opacity .15s}
.note{font-size:12px;color:var(--mut);padding:10px;line-height:1.5}
.banner{display:flex;gap:10px;align-items:center;padding:7px 12px;font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:6px;margin-bottom:10px;background:var(--panel)}
/* findings */
.fgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.fgrid .wide{grid-column:1/3}
.fq{font-size:13.5px;font-weight:650;margin:0}
.fsrc{font:11px var(--mono);color:var(--dim);padding:5px 10px;border-top:1px solid var(--line);word-break:break-all}
html[data-view=plain] .tech-only{display:none!important}
html[data-view=tech] .plain-only{display:none!important}
.big{font-size:22px;font-weight:700;line-height:1}
.sbar{display:flex;height:22px;border-radius:3px;overflow:hidden;border:1px solid var(--line)}
.sbar div{display:flex;align-items:center;justify-content:center;font:600 11px var(--sans);color:#0c0f13;min-width:0;overflow:hidden}
.tile{width:15px;height:15px;border-radius:2px;display:inline-block}
.t0{background:var(--f0)}.t1{background:var(--f1)}.t2{background:var(--f2)}.t3{background:var(--f3)}.t4{background:var(--f4)}
.tx{background:repeating-linear-gradient(45deg,var(--line),var(--line) 2px,transparent 2px,transparent 4px);border:1px solid var(--line)}
.wall{display:grid;gap:2px;align-items:center}
.wall .rl{font-size:11.5px;color:var(--mut);white-space:nowrap;padding-right:6px;text-align:right}
.wall .ch{font-size:11.5px;color:var(--mut);text-align:center;white-space:nowrap;overflow:hidden}
.cellnum{border:1px solid var(--cc);background:color-mix(in srgb,var(--cc) 14%,transparent);color:var(--cc);border-radius:4px;text-align:center;padding:7px 2px;font-weight:700;font-size:17px}
.cellnum small{display:block;font-weight:400;font-size:11.5px;color:var(--mut);margin-top:1px}
.fact{display:grid;grid-template-columns:128px minmax(0,1fr);gap:10px;align-items:baseline;padding:5px 0;border-bottom:1px solid var(--line)}
.fact:last-child{border-bottom:0}
.fact .n{font:650 15px var(--mono);text-align:right}
.fact .n small{font-weight:400;color:var(--mut);font-size:11.5px}
/* modal + tooltip */
.modal{position:fixed;inset:0;background:#0009;display:flex;align-items:center;justify-content:center;z-index:20}
.dlg{width:min(720px,94vw);max-height:92vh;display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line2);border-radius:8px;box-shadow:0 18px 60px #0008}
.dlg .dh{display:flex;align-items:center;gap:4px;padding:8px 10px 0 12px;border-bottom:1px solid var(--line)}
.dlg .dh .tab{height:34px}
.dlg .db{padding:16px 20px;overflow:auto;min-height:330px}
.dlg .df{display:flex;align-items:center;gap:8px;padding:10px 14px;border-top:1px solid var(--line)}
.dots{display:flex;gap:5px;flex:1}.dots i{width:7px;height:7px;border-radius:50%;background:var(--line2)}.dots i.on{background:var(--acc)}
.card h2{margin:0 0 6px;font-size:18px}.card p{margin:6px 0;color:var(--mut);font-size:13.5px;line-height:1.55}.card p b{color:var(--txt)}
.card svg{display:block;margin:10px auto 6px;max-width:100%}
.gl{display:grid;grid-template-columns:120px 1fr;gap:6px 14px;font-size:12.5px}.gl dt{font-weight:600}.gl dd{margin:0;color:var(--mut)}
.kb{display:grid;grid-template-columns:130px 1fr;gap:7px 12px;font-size:12.5px}
#tip{position:fixed;z-index:40;max-width:320px;background:var(--raised);border:1px solid var(--line2);border-radius:5px;padding:6px 9px;font-size:12px;line-height:1.4;box-shadow:0 6px 24px #0006;pointer-events:none;display:none}
#tip .mono{color:var(--mut);display:block;margin-top:3px;word-break:break-all}
.about{max-width:860px}.about p,.about li{color:var(--mut);font-size:13px;line-height:1.6}.about b{color:var(--txt)}.about ul{margin:4px 0;padding-left:18px}

.logo .ver{font:600 10.5px var(--mono);color:var(--mut);border:1px solid var(--line2);border-radius:3px;padding:0 5px;margin-left:7px;vertical-align:1px}
.vnum.none{background:none;border-style:dashed}
.ladder div.unk{border-style:dashed;color:var(--warn)}.ladder div.unk b{color:var(--warn)}
.ladder div.chk{border-color:var(--line2)}
.chip.drv,.chip.stin{color:var(--warn);border-color:var(--warn)}
.chip.ok{color:var(--ok);border-color:var(--ok)}
.chip.diff{color:var(--hot);border-color:var(--hot)}
.run.stop{background:none;color:var(--hot);border-color:var(--hot)}
.srcline{padding:5px 12px;border-top:1px solid var(--line);font-size:11.5px;color:var(--mut)}
.sb{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:6px 10px;border-bottom:1px solid var(--line);font-size:11.5px;color:var(--mut);background:var(--inset)}
.sb .bar{flex:1;min-width:80px;max-width:240px;height:6px;border-radius:3px;background:var(--line);overflow:hidden}
.sb .bar i{display:block;height:100%;background:var(--acc)}
.sb b{color:var(--txt);font-weight:600}
.lv{font-size:11.5px;color:var(--mut);display:block;font-weight:400;margin-top:1px;line-height:1.25}
.lv .m{color:var(--ok)}.lv .x{color:var(--hot);font-weight:600}
.tile.live{box-shadow:0 0 0 1.5px var(--txt)}
.tile.diff{box-shadow:0 0 0 2px var(--hot)}
.tile.pend{opacity:.35}
.tile.unk{background:none;border:1px dashed var(--warn)}
.tile.errt{background:none;border:1px dashed var(--hot)}
.cellnum.live{box-shadow:inset 0 0 0 1px var(--cc)}
.cellnum.pend{opacity:.5}
.maskd{display:inline-flex;gap:1.5px;vertical-align:middle}
.maskd i{width:6px;height:6px;border-radius:50%;border:1px solid var(--mut)}.maskd i.on{background:var(--txt);border-color:var(--txt)}
.hd45{height:44px;position:relative}.hd45 span{position:absolute;left:50%;bottom:2px;transform-origin:left bottom;transform:rotate(-40deg);white-space:nowrap;font-size:11.5px;color:var(--mut)}
details.raw{margin-top:6px}details.raw summary{cursor:pointer;color:var(--mut);font-size:11.5px}details.raw pre{white-space:pre-wrap;word-break:break-all;font:11px var(--mono);color:var(--mut);margin:6px 0 0}
.cellnum.none{background:none;border-style:dashed}


#design-hint{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fld{margin-top:5px}
/* ---- 3.0 */
html{font-size:14px}
body{font-size:13.5px}
.app.nosb{grid-template-columns:0 minmax(0,1fr)}.app.nosb aside{display:none}.app.nosb main{grid-column:1/3}
.btn.primary{background:var(--acc);border-color:var(--acc);color:var(--acc-t);font-weight:650}
.btn.primary:hover{filter:brightness(1.08)}
.btn.big{font-size:16px;padding:10px 22px;border-radius:7px}
.btn:focus-visible,.tab:focus-visible,.step:focus-visible,.pcard:focus-visible,.xcard:focus-visible,.xn:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
.linkb{background:none;border:0;color:var(--acc);padding:0;text-decoration:underline;font-size:inherit}
#run-hint{white-space:normal}
.kick{font-size:12px;color:var(--mut);margin-bottom:4px;letter-spacing:.2px}
.kick b{color:var(--txt)}
details#setdet{margin-top:10px;border-top:1px solid var(--line);padding-top:6px}
details#setdet>summary{cursor:pointer;font-size:12px;font-weight:600;color:var(--txt);padding:4px 0;list-style:none}
details#setdet>summary::before{content:"▸ ";color:var(--mut)}details#setdet[open]>summary::before{content:"▾ "}
html[data-view=plain] .step span.s{font-size:11.5px}
/* orientation strip: what am I looking at / what does it mean / what can I do */
.orient{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0 0 10px}
.orient>div{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 11px}
.orient h5{margin:0 0 3px;font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;color:var(--acc);font-weight:700}
.orient p{margin:0;font-size:13px;color:var(--txt);line-height:1.45}
.plainstory .orient{margin:8px 0 2px}.plainstory .orient>div{background:var(--inset)}
.plainstory{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:12px;align-items:start}.plainstory .shead{grid-column:1;grid-row:1}.plainstory .sbody{grid-column:1;grid-row:2;min-width:0}.plainstory .nav{grid-column:2;grid-row:1/3;flex-direction:column;align-items:stretch;min-width:130px}
.vnum{height:auto;min-height:62px;padding:4px 6px}
.sentence{font-size:18px;line-height:1.4;font-weight:600;padding:12px 14px;color:var(--txt)}
.sentence b{color:var(--acc)}
.vt.sentence0{font-size:18px;line-height:1.35}
.chiprow{display:flex;gap:6px;flex-wrap:wrap;margin:5px 0 2px}
.chip{font-size:11px}
.chip.h-live,.chip.h-cached{color:var(--acc);border-color:var(--acc)}.chip.h-recorded{color:var(--c1);border-color:var(--c1)}
.chip.h-simulated{color:var(--c2);border-color:var(--c2)}.chip.h-bounded{color:var(--c0);border-color:var(--c0);border-style:dashed}.chip.h-proved{color:var(--ok);border-color:var(--ok)}
.chip.h-notrun{color:var(--warn);border-color:var(--warn);border-style:dashed}.chip.h-estimate{color:var(--warn);border-color:var(--warn)}.chip.h-ok{color:var(--ok);border-color:var(--ok)}
/* start page */
.home{max-width:1180px;margin:0 auto}
.hero{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:24px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:22px 26px;margin-bottom:14px}
.hero h1{margin:0 0 8px;font-size:26px;line-height:1.2}
.hero p{margin:0 0 10px;color:var(--mut);font-size:15px;line-height:1.55}.hero p b{color:var(--txt)}
.hero .small{font-size:13px;margin-top:10px}
.hart svg{width:100%;height:auto}
.cta{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:14px 0 4px}
.ctah{font-size:13px;color:var(--mut);max-width:330px}.ctah b{color:var(--txt)}
h3.sec{font-size:13px;text-transform:none;letter-spacing:0;color:var(--txt);margin:16px 0 8px}h3.sec .m{color:var(--mut);font-weight:400}
.pgrid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px}
.pcard{display:flex;flex-direction:column;gap:4px;text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 11px;min-height:120px}
.pcard:hover{border-color:var(--acc)}.pcard .n{width:24px;height:24px;border-radius:50%;border:1px solid var(--line2);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12.5px}
.pcard.done .n{background:var(--acc);color:var(--acc-t);border-color:var(--acc)}.pcard b{font-size:13.5px}.pcard .g{font-size:12px;color:var(--mut);line-height:1.35}.pcard .res{margin-top:auto;font-size:12px;font-weight:650;color:var(--acc)}
.xgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.xcard{display:grid;grid-template-columns:30px 1fr;grid-template-rows:auto auto auto;column-gap:10px;text-align:left;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.xcard:hover{border-color:var(--acc)}.xcard .xi{grid-row:1/4;color:var(--mut)}.xcard .xi svg,.xn .xi svg{width:26px;height:26px}.xcard b{font-size:13.5px}.xcard span{font-size:12.5px;color:var(--mut)}.xcard .xl{margin-top:5px}
.foot-note{font-size:12.5px;color:var(--mut);margin:16px 0 4px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
/* explore */
.xwrap{display:grid;grid-template-columns:250px minmax(0,1fr);gap:14px;align-items:start}
.xnav{position:sticky;top:0;display:flex;flex-direction:column;gap:3px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px}
.xh{font-size:11.5px;text-transform:uppercase;letter-spacing:.8px;color:var(--mut);font-weight:700;padding:2px 6px 6px}
.xn{display:flex;gap:9px;align-items:flex-start;text-align:left;background:none;border:1px solid transparent;border-radius:6px;padding:6px 7px}
.xn:hover{background:var(--raised)}.xn.on{background:var(--raised);border-color:var(--line2)}.xn .xi{color:var(--mut);flex:none}.xn.on .xi{color:var(--acc)}
.xn b{display:block;font-size:13px;font-weight:600}.xn span>span{display:block;font-size:11.5px;color:var(--mut);line-height:1.3}
.xt{margin:0 0 10px;font-size:20px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.lbl{font-size:11.5px;color:var(--mut);margin-bottom:4px;font-weight:600}
.seg.wrap{flex-wrap:wrap;gap:2px}.seg.wrap button{padding:5px 10px;font-size:12.5px}
.rowflex{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.rowflex .sp,.sp{flex:1}
.hint{font-size:12px;color:var(--mut)}
.okc{color:var(--ok)}.badc{color:var(--hot)}.warnc{color:var(--warn)}
.big2{font-size:20px;font-weight:700;margin-bottom:2px}
.hbar{display:grid;grid-template-columns:minmax(170px,1.3fr) minmax(80px,1fr) 88px;gap:8px;align-items:center;padding:3px 0;font-size:12.5px}
.hbar .hl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hbar .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.hbar .hb{height:12px;background:var(--inset);border-radius:3px;overflow:hidden;border:1px solid var(--line)}.hbar .hb i{display:block;height:100%}.hbar .hv{text-align:right;font-variant-numeric:tabular-nums}
.sbar2{display:flex;height:34px;border-radius:5px;overflow:hidden;border:1px solid var(--line2)}
.sseg{display:flex;align-items:center;justify-content:center;font-size:11.5px;min-width:0;overflow:hidden;white-space:nowrap;border-right:2px solid var(--panel);background:var(--raised)}
.sseg:nth-child(1){box-shadow:inset 0 -4px 0 var(--c0)}.sseg:nth-child(2){box-shadow:inset 0 -4px 0 var(--c1)}.sseg:nth-child(3){box-shadow:inset 0 -4px 0 var(--c2)}.sseg:nth-child(4){box-shadow:inset 0 -4px 0 var(--shared)}
.kv2{display:grid;grid-template-columns:150px minmax(0,1fr);gap:4px 12px;font-size:12px}.kv2>div:nth-child(odd){color:var(--mut)}.kv2>div:nth-child(even){word-break:break-word}
details.learn{border:1px solid var(--line);border-radius:6px;background:var(--panel);margin-bottom:10px}details.learn>summary{padding:8px 12px;font-size:12.5px}
.sug{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:12px;align-items:start;padding:9px 10px;border-top:1px solid var(--line)}
.sug .ba{display:flex;align-items:center;gap:5px}.sug .bn{font:700 18px var(--sans);min-width:28px;text-align:center;border:1px solid var(--line2);border-radius:5px;padding:2px 6px}.sug .bn.hi{border-color:var(--ok);color:var(--ok)}.sug .arr{color:var(--mut)}
.ftab td.fcell{text-align:center;font-weight:600;font-size:12.5px}.ftab td.pr{color:var(--ok);background:color-mix(in srgb,var(--ok) 9%,transparent)}.ftab td.at{color:var(--hot);background:color-mix(in srgb,var(--hot) 8%,transparent)}.ftab td.un{color:var(--warn)}
.lvm{display:block;font-size:10.5px;color:var(--acc);font-weight:500}
.chk{display:flex;gap:5px;align-items:center;font-size:12.5px;color:var(--mut)}
.code{font:12.5px/1.55 var(--mono);max-height:520px;overflow:auto;background:var(--inset)}
.code .cl{display:grid;grid-template-columns:34px 118px minmax(0,1fr);gap:6px;padding:0 8px}.code .cl.mk{background:color-mix(in srgb,var(--warn) 12%,transparent)}
.code .ln{color:var(--dim);text-align:right;user-select:none}.code code{white-space:pre;font:inherit}
.fm{display:inline-block;font:700 10.5px var(--sans);color:var(--hot);border:1px solid var(--hot);border-radius:3px;padding:0 3px;margin-right:2px;line-height:15px}
.sbgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.sbc{margin-bottom:0}.sbc h4{font-size:12.5px;font-weight:600;line-height:1.3}
.tags{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px}.tag{font-size:11.5px;border:1px solid var(--line2);border-radius:10px;padding:1px 8px;color:var(--mut)}
.notx th{text-transform:none;letter-spacing:0;font-size:12px}
.evf{width:100%;height:620px;border:0;border-top:1px solid var(--line);background:#fff}
.empty.coming{padding:40px 30px;border-style:dashed}
.story-dlg{width:min(680px,95vw)}.story-dlg .db{min-height:0;padding:20px 26px 10px}.story-dlg .card p{font-size:15px;color:var(--txt)}.story-dlg .card h2{font-size:22px}
.story-dlg svg{width:100%;height:auto;max-height:200px}
/* ---- 3.1: five labels with a gloss, plain notes, one-minute summary */
.tg{display:inline-flex;align-items:baseline;gap:6px;flex-wrap:wrap;vertical-align:baseline}
.gloss{font-size:12px;color:var(--mut);font-weight:400;letter-spacing:0;text-transform:none}
.ntag{font-size:11.5px;font-weight:500;color:var(--warn);border-bottom:1px dotted currentColor;cursor:help;white-space:nowrap;letter-spacing:0;text-transform:none}
.ntag.ok{color:var(--ok)}.ntag.bad{color:var(--hot)}.ntag.mut{color:var(--mut)}
.vt .ntag,.chiprow .ntag{margin-left:10px}.vt .tg{margin-left:8px}.vt .tg .chip{margin-left:0}
.xcard .xl .gloss{font-size:11.5px}
.found{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;padding:14px 18px;margin-bottom:14px}
.found h2{margin:0 0 2px;font-size:17px}.found .sub{color:var(--mut);font-size:12.5px;margin:0 0 8px}
.found .fcols{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);gap:22px;align-items:start}
.found ol{margin:0;padding-left:20px}.found li{margin:0 0 7px;font-size:13.5px;line-height:1.45;color:var(--mut)}.found li b.h{color:var(--txt);font-weight:650}.found li b{color:var(--txt)}
.found h5{margin:0 0 5px;font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;color:var(--acc);font-weight:700}
.found .next li{margin-bottom:6px}.found .scope{font-size:12.5px;color:var(--mut);margin:8px 0 0;line-height:1.5}.found .scope b{color:var(--txt)}
.dirty{display:flex;gap:10px;align-items:center;padding:7px 12px;font-size:12.5px;border:1px solid var(--warn);border-radius:6px;margin-bottom:10px;background:color-mix(in srgb,var(--warn) 10%,transparent);color:var(--txt)}
.vnum .sub2{font-size:10px;letter-spacing:0;text-transform:none;margin-top:1px;color:var(--mut)}
.howlive ol{margin:4px 0 6px;padding-left:20px}.howlive li{margin-bottom:5px;font-size:13px;line-height:1.5;color:var(--mut)}.howlive p{font-size:12.5px;color:var(--mut);margin:4px 0 0}
.howlive code,.keep code{font:12px var(--mono);background:var(--inset);border:1px solid var(--line);border-radius:4px;padding:1px 6px;color:var(--txt);white-space:nowrap}
details.inl{display:inline}details.inl>summary{display:inline;cursor:pointer;color:var(--acc);text-decoration:underline;list-style:none}details.inl>summary::-webkit-details-marker{display:none}
details.inl[open]{display:block;margin-top:6px}
.banner .bt{flex:1;min-width:0}
.runbar{position:sticky;top:0;z-index:2;padding:8px 0;border-top:0;border-bottom:1px solid var(--line);margin-bottom:4px}
.fmx{position:relative;display:inline-block;font:700 10.5px var(--sans);color:var(--hot);border:1px solid var(--hot);border-radius:3px;padding:0 4px;line-height:15px;cursor:help}
.fmx .fmall{display:none;position:absolute;left:0;top:100%;z-index:5;background:var(--raised);border:1px solid var(--line2);border-radius:4px;padding:3px 4px;white-space:nowrap;box-shadow:0 6px 24px #0006}
.fmx:hover .fmall,.fmx:focus .fmall,.fmx:focus-within .fmall{display:block}
.uinv{font-weight:650;color:var(--warn)}
.rtab td{font-size:12.5px}.rtab td b.n{font-size:15px}
h2.sth:focus,h2.sth:focus-visible,#found:focus{outline:none}
.found.indlg{border:0;padding:0;margin:0;background:none}
.chipt{width:100%}.chipt td{vertical-align:top}.chipn{margin:2px 0}.chipn b{font-size:18px}.chipnote{margin:6px 0 0;padding:6px 8px;border:1px solid var(--warn);border-radius:6px;font-size:13px;max-width:460px}
details.startmore{margin:14px 0 4px}details.startmore>summary{font-size:15px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.fcard{border:1px solid var(--line);border-left:6px solid var(--line2);border-radius:8px;padding:8px 12px;margin:8px 0;background:var(--panel)}
.fhead{display:flex;gap:10px;align-items:flex-start}.fstat{font-size:15px}.freal,.furg{margin:6px 0}.fsum{margin:0 0 6px}
.sev{display:inline-flex;gap:5px;align-items:center;white-space:nowrap;font:700 12px var(--sans);padding:2px 8px;border-radius:4px;border:2px solid}
.sev-crit{color:#fff;background:#b3261e;border-color:#b3261e}.sev-high{color:#fff;background:#b35c00;border-color:#b35c00}.sev-med{color:#1d1d1d;background:#e8c547;border-color:#a98a12}
.sev-low{color:var(--txt);background:transparent;border-color:var(--line2)}.sev-info{color:var(--mut);background:transparent;border-color:var(--line);border-style:dashed}.sev-unknown{color:var(--txt);background:transparent;border-color:var(--warn);border-style:dotted}
.sevb-crit{border-left-color:#b3261e}.sevb-high{border-left-color:#b35c00}.sevb-med{border-left-color:#a98a12}.sevb-low{border-left-color:var(--line2)}.sevb-unknown{border-left-color:var(--warn);border-left-style:dotted}
.ftrace{margin:6px 0}.fctx{font-size:12px;padding:6px;background:var(--inset);border:1px solid var(--line);border-radius:6px;overflow:auto}.fctx .fhit{background:rgba(229,83,75,.22);font-weight:700}.fsteps li{margin:3px 0}.ftl{display:block;margin:4px 0}
.legend5{display:flex;flex-wrap:wrap;gap:6px 18px;margin:6px 0 4px}
@media (max-width:1100px){.found .fcols{grid-template-columns:1fr}}
@media (max-width:1500px){.pgrid{grid-template-columns:repeat(3,minmax(0,1fr))}.sbgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:1100px){.xgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.hero{grid-template-columns:1fr}.hart{display:none}}
/* ---- UT2: the top bar never wraps or clips; compact labels below 1400 px, a More menu below 1200 px */
header{white-space:nowrap;min-width:0}
.tabs{flex:none}.tab{white-space:nowrap;padding:0 12px}
#tab-more{display:none}#tab-more.has-only{display:block}.tab.monly{display:none!important}
.tmenu{position:fixed;z-index:70;background:var(--panel);border:1px solid var(--line2);border-radius:6px;padding:4px;box-shadow:0 8px 24px rgba(0,0,0,.35);display:flex;flex-direction:column;min-width:160px}
.tmenu button{text-align:left;background:none;border:0;border-radius:4px;padding:7px 10px;font-size:13px}
.tmenu button:hover{background:var(--raised)}.tmenu button.on{box-shadow:inset 3px 0 0 var(--acc)}
@media (max-width:1500px){.logo small{display:none}}
@media (max-width:1400px){.tab{padding:0 9px}.tabs{margin-left:2px}.tab[data-short] .tl{display:none}.tab[data-short]::after{content:attr(data-short)}.hlabel{display:none}header{gap:5px}}
@media (max-width:1200px){.tab.ovf{display:none}#tab-more{display:block}}
@media (max-width:1100px){.logo .ver{display:none}.tab{padding:0 7px}header{padding:0 8px}.logo{margin-right:0}}
/* ---- UT2: predict first (opt-in), fix layer, gallery, small tables */
details.seehow{margin:10px 0}details.seehow>summary{font-size:15px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}details.seehow[open]>summary{margin-bottom:8px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.predict{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 0;padding:7px 10px;border:1px dashed var(--line2);border-radius:6px;font-size:13px}
.predict .btn{min-width:34px}.predict #pred-out:focus{outline:none}
#result.veil{filter:blur(10px);opacity:.45;pointer-events:none;user-select:none}
.step.pend .r{visibility:hidden}
details.fixit>summary{font-size:13px;color:var(--txt);font-weight:600}details.fixit>summary .hint{font-weight:400;margin-left:6px}
.fxlead{margin:0 0 8px;font-size:13.5px;line-height:1.5}
.fxgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.fxc{background:var(--inset);border:1px solid var(--line);border-radius:6px;padding:9px 11px;font-size:13px;line-height:1.45}
.fxc.hi{border-color:var(--acc);box-shadow:inset 3px 0 0 var(--acc)}
.fxc h5{margin:0 0 3px;font-size:13.5px}.fxc h5 .ntag{margin-left:6px}
.fxc p{margin:3px 0}.fxc .tt{font-size:12px;color:var(--mut);border-top:1px dashed var(--line);margin-top:6px;padding-top:5px}
.fxc .tt code,.fxlead code{font-family:var(--mono);font-size:11.5px;background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:0 3px;white-space:nowrap}
.fxc .ev{font-size:12px;margin-top:5px}.fxc .ev b{color:var(--txt)}
@media (max-width:1100px){.fxgrid{grid-template-columns:1fr}}
/* audit 5-S1: links in the theme's link colour (the teacher and project links were the browser's default blue on dark) */
a:not(.btn),a:not(.btn):visited{color:var(--acc)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
/* audit 5-S4: 200 % zoom on a laptop (about 680 px wide) and narrower: one column, the header wraps, nothing scrolls sideways */
@media (max-width:900px){
 .app,.app.nosb{grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto minmax(0,1fr) auto;height:auto;min-height:100vh}
 header{grid-column:1/-1;flex-wrap:wrap;white-space:normal;height:auto;min-height:44px;padding:4px 8px;row-gap:4px}
 .tabs{flex-wrap:wrap;height:auto}.tabs .tab{height:40px}.app aside{border-right:0;border-bottom:1px solid var(--line);max-height:38vh;overflow:auto}
 .app>*,.app.nosb>*{grid-column:1/-1!important;min-width:0}.app.nosb aside{display:none}
 .orient,.cols,.gal3,.fxgrid,.hero,.found .fcols{grid-template-columns:minmax(0,1fr)!important}
 .pgrid,.xgrid,.sbgrid,.lz-grid{grid-template-columns:minmax(0,1fr)!important}
 .panel,.mapwrap,#wavebox,.xbody,table{max-width:100%;overflow-x:auto}
 .xwrap{display:block}.xnav{position:static;width:auto;max-height:none}
 main,.view{min-width:0;overflow-x:hidden}
}
.galx{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:0 12px 10px}
.galr{background:var(--inset);border:1px solid var(--line);border-radius:6px;padding:9px 11px}
.galr .who{font-size:11.5px;letter-spacing:.5px;text-transform:uppercase;color:var(--mut);font-weight:700}
.galr .ans{font-size:17px;font-weight:650;margin:2px 0 4px}.galr.weak{border-left:4px solid var(--hot)}.galr.held{border-left:4px solid var(--ok)}
.galr table td,.galr table th{font-size:12.5px;padding:2px 8px 2px 0;border:0;text-align:left;vertical-align:top}
.gal3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:10px 12px;font-size:13px;line-height:1.45}.gal3 b{display:block;color:var(--acc);font-size:11.5px;letter-spacing:.5px;text-transform:uppercase}
table.jt{width:auto;border-collapse:collapse}table.jt td{font-size:12px;padding:1px 10px 1px 0;vertical-align:top;border:0}table.jt td:first-child{color:var(--mut);white-space:nowrap}
.teachline{margin:8px 0 0;font-size:13px}
</style></head><body><div class="app">
<header>
 <div class="logo"><svg viewBox="0 0 32 32" aria-hidden="true"><rect x="3" y="3" width="26" height="26" rx="5" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".55"/><path d="M5 20h6v-8h5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M19 7l-5 10h4l-2 8 7-11h-4z" fill="var(--warn)"/></svg>
  <div>GlitchSAT Studio<span class="ver" id="ver" data-tip="GlitchSAT version, read from the project files"></span><small>how many glitches does it take to fool a lock?</small></div></div>
 <nav class="tabs" id="tabs" role="tablist"></nav>
 <span class="hsp"></span>
 <button class="btn" id="b-story" data-tip="The short story of locks, thieves and glitches that explains this app (S)">How it works</button>
 <span class="hlabel">View</span><div class="seg" id="viewseg"><button data-v="plain" class="on" data-tip="Everyday words for people new to hardware. Same numbers as Technical. (V)">Plain</button><button data-v="tech" data-tip="For engineers: wire names, hex values, bounds and file names. (V)">Technical</button></div>
 <button class="btn hidden" id="b-export" disabled data-tip="Save the result on screen as a JSON file, with its limits and source">Export</button>
 <button class="btn ico" id="b-theme" data-tip="Switch dark / light theme (T)" aria-label="Switch dark or light theme">◐</button>
 <button class="btn ico" id="b-help" data-tip="Glossary and keyboard keys (?)" aria-label="Glossary and keyboard keys">?</button>
</header>

<aside>
 <div class="side-scroll">
 <h3><span class="plain-only">Your path</span><span class="tech-only">Walk-through</span></h3><div id="steps"></div>
 <details id="setdet"><summary><span class="plain-only">Change the experiment yourself</span><span class="tech-only">Settings</span></summary>
 <div class="runbar"><button class="run" id="run" aria-label="Run with these settings (Enter)"><span id="run-t">Run with these settings</span><kbd id="run-k">Enter</kbd></button>
 <div class="hint tech-only" style="display:flex;align-items:center;gap:6px;margin-top:6px"><label for="tl" style="white-space:nowrap"><span class="plain-only">Stop searching after</span><span class="tech-only">Time limit</span></label><select id="tl" style="padding:2px 4px;font-size:11.5px;flex:1" data-tip="A live search is stopped at this limit. A stopped search gives no conclusion; it is never reported as 'no attack'."><option value="10">10 seconds</option><option value="30">30 seconds</option><option value="60" selected>1 minute</option><option value="120">2 minutes</option><option value="300">5 minutes</option><option value="900">15 minutes</option></select></div>
 <div class="hint" id="run-hint"></div></div>
 <div class="fld"><label for="design"><span class="plain-only">Which lock</span><span class="tech-only">Design</span></label>
  <select id="design" data-tip="Four small example locks: one check, two checks, three copies, and three copies with one pattern changed."></select><div class="hint" id="design-hint" data-tip="What this design is"></div></div>
 <div class="fld"><label><span class="plain-only">Chip plan</span><span class="tech-only">Netlist source</span></label>
  <div class="seg" id="src"><button data-v="stored" class="on" data-tip="The first chip plan, kept in the project files"><span class="plain-only">First (saved)</span><span class="tech-only">Stored netlist</span></button><button data-v="rtl" data-tip="A second chip plan, made again from the written design by the build tool"><span class="plain-only">Made again</span><span class="tech-only">Rebuilt (Yosys)</span></button></div></div>
 <div class="fld"><label><span class="plain-only">How the build tool works</span><span class="tech-only">Synthesis flow</span></label>
  <div class="seg" id="flow"><button data-v="plain" class="on" data-tip="Each part is built as written" data-tipm="scripts/synth.sh plain">As written</button><button data-v="opt" data-tip="The build tool first tidies the design up, then builds it" data-tipm="scripts/synth.sh opt">Tidied first</button></div></div>
 <div class="fld"><label><span class="plain-only">What the thief must fake</span><span class="tech-only">Attack goal</span></label>
  <div class="seg" id="goal"><button data-v="word" class="on" data-tip="The rest of the chip reads the lock’s whole answer (8 signals); the thief must fake all of it" data-tipm="boot_word == 0x96"><span class="plain-only">The whole answer</span><span class="tech-only">boot_word</span></button><button data-v="flag" data-tip="The rest of the chip reads only one “open” signal" data-tipm="boot_ok == 1"><span class="plain-only">One “open” signal</span><span class="tech-only">boot_ok</span></button></div></div>
 <div class="fld"><label for="k"><span><span class="plain-only">Glitches the thief may use</span><span class="tech-only">Fault budget k</span></span><b id="kv">3</b></label>
  <input type="range" id="k" min="0" max="4" value="3" data-tip="The search looks for an attack with at most this many glitches, and reports the smallest number that works."></div>
 <div class="fld"><label for="cyc"><span><span class="plain-only">Time window (steps)</span><span class="tech-only">Cycles N</span></span><b id="cv">6</b></label>
  <input type="range" id="cyc" min="2" max="12" value="6" data-tip="How many steps of the chip's clock the thief can act in. Longer windows take the search longer.">
  <div class="hint" id="cyc-hint"></div></div></details>
 </div>
</aside>

<main>
 <div id="views" style="display:contents"></div>
 <div class="logdock tech-only" id="logdock"><div class="logbar" id="logbar" data-tip="Run log: what the program did, step by step (`)"><b>Run log</b><span class="last" id="loglast">nothing run yet</span><span id="logtog">▴</span></div><div class="logbody" id="logbody"></div></div>
</main>
<footer id="foot"></footer><div id="sr-live" class="sr-only" role="status" aria-live="polite"></div>
</div>
<div id="tip"></div><div id="modal"></div>
<script>
"use strict";
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const hex=(v,w=2)=>'0x'+Number(v).toString(16).toUpperCase().padStart(w,'0');
const LS={get(k,d){try{const v=localStorage.getItem(k);return v==null?d:JSON.parse(v)}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
const CID=(crypto.randomUUID?crypto.randomUUID():String(Math.random()).slice(2)+Date.now());
const S={story:null,view:LS.get('gs_view','plain'),theme:LS.get('gs_theme',(window.matchMedia&&matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark'),status:null,last:null,lastQ:null,ti:-1,keep:LS.get('gs_keep',false),hist:[],cursor:null,honest:false,mapMode:'focus',zoom:null,busy:false,runId:null,log:[],tourRes:LS.get('gs_path',{}),
 find:null,live:{},jobs:{},pending:{},ladder:null,encSet:null,dial:{design:'v2',reader:'word',build:'stored',inputs:'no',power:'known'},tab:'start'};
if(S.keep)S.hist=LS.get('gs_hist',[]);
const tech=()=>S.view==='tech';
const T=(p,t)=>tech()?t:p;
const pl=(n,w)=>n+' '+w+(n===1?'':'s');
const secs=s=>s==null?'':s<90?Math.max(1,Math.round(s))+' s':Math.round(s/60)+' min';
const GLOSS={flip:'One wire made to give the wrong answer (0 instead of 1, or 1 instead of 0) for one clock tick. A model of an electrical glitch.',
 tick:'One step of the chip’s clock. The circuit moves forward one step per tick.',
 wire:'A connection that carries a single 0 or 1 between gates (engineers call it a net).',
 gate:'A tiny building block that combines 0s and 1s, for example AND, OR, NOT.',
 'memory bit':'A cell that remembers a 0 or 1 from one tick to the next (a flip-flop).',
 copy:'A repeated key check. The idea: an attacker must fool every copy, not just one.',
 circuit:'The design as a list of gates and wires (a netlist), produced by Yosys, a free program that turns a design into gates.',
 limit:'The search only covers up to a stated number of flips and ticks. Nothing is claimed beyond that.',
 solver:'z3, a program that reasons about every combination exactly instead of trying samples.',
 live:'Computed on this computer by the engine, in this session.',
 cached:'Computed live on this computer earlier and kept in a local cache (same circuit, same engine version, same settings).',
 recorded:'Computed earlier and stored in the project files; shown from the file, not re-run.',
 unknown:'The search was stopped or gave no answer. Nothing can be concluded; it does not mean "no attack".',
 key:'The 8-bit input the lock checks. Only one value (the right key) should be accepted.',
 V0:'The naive design: one check of the key.',V1:'Two copies of the check, joined by one shared wire.',V2:'Three copies of the check; each copy sets its own bits of the 8-bit result.',V2e:'V2 with one constant changed: the Armed code is 0xA5 instead of 0xCC.',
 Idle:'The lock has not started checking yet.',Armed:'The lock is checking the key (one tick).',Accept:'The lock is open: the key was accepted.',Reject:'The lock is shut: the key was rejected.'};
const PK={flip:'glitch',tick:'step','memory bit':'memory cell',circuit:'chip plan',solver:'checking program',V0:'one-check lock',V1:'two-check lock',V2:'three-copy lock',V2e:'three-copy lock, one pattern changed',Idle:'Waiting',Armed:'Checking',Accept:'Open',Reject:'Shut'};
const gloss=w=>tech()?(GLOSS[w]||''):(PG[PK[w]||w]||plainText(GLOSS[w]||''));
const term=(w,label)=>`<span class="term" data-tipk="1" data-tip="${esc(gloss(w))}">${esc(tech()?(label||w):(label?plainText(label):(PK[w]||w)))}</span>`;
const FC=n=>n==null?'var(--none)':`var(--f${Math.min(4,n)})`;

/* ---------------- server calls (the custom header and the client id are required by the server) */
const api={get:p=>fetch(p).then(r=>r.json()),post:(p,b)=>fetch(p,{method:'POST',headers:{'X-GlitchSAT':'1','Content-Type':'application/json'},body:JSON.stringify(Object.assign({cid:CID},b||{}))}).then(r=>r.json())};

/* ---------------- tooltip */
const tipEl=$('#tip');let tipFor=null;
function showTip(el){const t=el.getAttribute('data-tip');if(!t)return;tipFor=el;const m=el.getAttribute('data-tipm');
 tipEl.innerHTML=esc(el.hasAttribute('data-tipk')?t:tech()?techText(t):plainText(t))+(m&&tech()?`<span class="mono">${esc(m)}</span>`:'');tipEl.style.display='block';
 const r=el.getBoundingClientRect(),w=tipEl.offsetWidth,h=tipEl.offsetHeight;let x=Math.min(innerWidth-w-8,Math.max(8,r.left+r.width/2-w/2)),y=r.bottom+7;if(y+h>innerHeight-8)y=r.top-h-7;
 tipEl.style.left=x+'px';tipEl.style.top=Math.max(4,y)+'px'}
function hideTip(){tipEl.style.display='none';tipFor=null}
document.addEventListener('mouseover',e=>{const el=e.target.closest&&e.target.closest('[data-tip]');if(el){if(el!==tipFor)showTip(el)}else hideTip()});
document.addEventListener('focusin',e=>{const el=e.target.closest&&e.target.closest('[data-tip]');if(el&&e.target.matches(':focus-visible'))showTip(el)});
document.addEventListener('focusout',hideTip);document.addEventListener('scroll',hideTip,true);document.addEventListener('mousedown',hideTip);document.addEventListener('click',hideTip);
document.addEventListener('keydown',e=>{if(e.key!=='Tab')hideTip()});

/* ---------------- views registry (EXTENSION POINT)
   Studio.registerView({id, title, tip, mount(el), show(el)})            adds a tab
   Studio.registerView({id, card:true, wide, title, study, render(F)})   adds a card to Findings
   Background work goes through Studio.startJob(study, params) -> POST /api/job; results arrive in Studio.live[cellId]. */
const VIEWS=[];
const Studio={state:S,api,live:S.live,registerView(v){if(v.group==='explore'){EXPLORE.push(v);return}VIEWS.push(v);if(!v.card)buildTabs()},startJob:(s,p)=>startStudy(s,p),esc};
window.Studio=Studio;
/* Tabs. A view may say  after:'start'  (where it sits in the bar) and  short:'…'  (label used when the window is narrow).
   Number keys follow the order in which views were registered, so they stay the same when the bar is rearranged. */
const TAB_SHORT={mine:'My design'},TAB_OVF=['compare','findings','about'],TAB_MORE_ONLY=[];   /* TAB_MORE_ONLY: pages that live in the More menu at every width (Labs) */
const narrowTabs=()=>matchMedia('(max-width:1200px)').matches,moreOn=id=>TAB_MORE_ONLY.includes(id)||(narrowTabs()&&TAB_OVF.includes(id));
function tabOrder(){const t=VIEWS.filter(v=>!v.card),out=t.filter(v=>!v.after);t.filter(v=>v.after).forEach(v=>{const k=out.findIndex(x=>x.id===v.after);out.splice(k<0?out.length:k+1,0,v)});return out}
function buildTabs(){const reg=VIEWS.filter(v=>!v.card),tabs=tabOrder();$('#tabs').innerHTML=tabs.map(v=>{const n=reg.indexOf(v)+1,sh=v.short||TAB_SHORT[v.id];return `<button class="tab${v.id===S.tab?' on':''}${TAB_OVF.includes(v.id)?' ovf':''}${TAB_MORE_ONLY.includes(v.id)?' monly':''}" role="tab" aria-selected="${v.id===S.tab}" data-v="${v.id}"${sh?` data-short="${esc(sh)}" aria-label="${esc(v.title)}"`:''} data-tip="${esc(v.tip||v.title)}${n<10?' ('+n+')':''}"><span class="tl">${esc(v.title)}</span></button>`}).join('')+`<button class="tab${moreOn(S.tab)?' on':''}${TAB_MORE_ONLY.length?' has-only':''}" id="tab-more" aria-haspopup="menu" aria-expanded="false" data-tip="More pages: ${esc(VIEWS.filter(v=>TAB_OVF.includes(v.id)).map(v=>v.title).join(', '))}">More ▾</button>`;
 const host=$('#views');tabs.forEach(v=>{if(!$('#v-'+v.id)){const d=document.createElement('div');d.className='view'+(v.id===S.tab?'':' hidden');d.id='v-'+v.id;host.appendChild(d);if(v.mount)v.mount(d)}});
 $$('#tabs .tab[data-v]').forEach(t=>t.onclick=()=>show(t.dataset.v));$('#tab-more').onclick=e=>{e.stopPropagation();tabMenu()}}
function closeTabMenu(focus){const m=$('#tmenu');if(!m)return;m.remove();const b=$('#tab-more');if(b){b.setAttribute('aria-expanded','false');if(focus)b.focus()}}
function tabMenu(){if($('#tmenu')){closeTabMenu();return}const b=$('#tab-more'),r=b.getBoundingClientRect(),m=document.createElement('div');m.id='tmenu';m.className='tmenu';m.setAttribute('role','menu');m.setAttribute('aria-label','More pages');
 m.innerHTML=VIEWS.filter(v=>TAB_OVF.includes(v.id)&&(narrowTabs()||TAB_MORE_ONLY.includes(v.id))).map(v=>`<button role="menuitem" data-v="${v.id}" class="${v.id===S.tab?'on':''}">${esc(v.title)}</button>`).join('');
 m.style.top=(r.bottom+2)+'px';m.style.left=Math.max(4,Math.min(innerWidth-170,r.left))+'px';document.body.appendChild(m);b.setAttribute('aria-expanded','true');
 const it=[...m.querySelectorAll('button')];it.forEach(x=>x.onclick=()=>{closeTabMenu();show(x.dataset.v);const t=$('#tab-more');t&&t.focus()});it[0]&&it[0].focus();
 m.addEventListener('keydown',e=>{const i=it.indexOf(document.activeElement);if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeTabMenu(true)}else if(e.key==='ArrowDown'){e.preventDefault();e.stopPropagation();it[(i+1)%it.length].focus()}else if(e.key==='ArrowUp'){e.preventDefault();e.stopPropagation();it[(i-1+it.length)%it.length].focus()}else if(e.key==='Tab'){closeTabMenu()}})}
document.addEventListener('click',e=>{if($('#tmenu')&&!e.target.closest('#tmenu'))closeTabMenu()});addEventListener('resize',()=>closeTabMenu());
function show(id){S.tab=id;$$('#tabs .tab').forEach(t=>{const on=t.dataset.v?t.dataset.v===id:moreOn(id);t.classList.toggle('on',on);if(t.dataset.v)t.setAttribute('aria-selected',on)});$('.app').classList.toggle('nosb',id!=='analyze');$$('main .view').forEach(s=>s.classList.toggle('hidden',s.id!=='v-'+id));
 const v=VIEWS.find(x=>x.id===id);if(v&&v.show)v.show($('#v-'+id))}

/* ---------------- settings + tour */
const FAMS=[['v0','V0 · one check','One check of the key.'],['v1','V1 · two copies','Two copies, joined by one shared wire.'],['v2','V2 · three copies','Three copies; each sets its own result bits.'],['v2e','V2e · re-encoded armed word','V2 with the Armed code changed.']];
const FAMN=Object.fromEntries(FAMS.map(f=>[f[0],f[1]]));
const FAMP={v0:['Lock with one check','One check of the key.'],v1:['Two checks, one shared wire','Two copies of the check that report through one shared wire.'],v2:['Three copies, kept apart','Three copies; each controls its own part of the answer.'],v2e:['Three copies, one pattern changed','Three copies with the pattern for Checking changed.']};
function fillDesign(){const cur=$('#design').value||'v2';$('#design').innerHTML=FAMS.map(f=>`<option value="${f[0]}">${esc(tech()?f[1]:FAMP[f[0]][0])}</option>`).join('');$('#design').value=cur}
const ys=()=>S.status&&S.status.yosys_short?'Yosys '+S.status.yosys_short:'Yosys';
function recNote(r){return r&&r._src==='recorded'?' (recorded)':''}
function encMerge(){/* fewest flips on the two copy-merging build flows for V2e: live if this session computed them, else recorded */
 const names=['plain_opt_merge','flatten_before_abc'],lv=names.map(n=>S.live['enc|v2e|'+n]).filter(x=>x&&x.state==='ok');
 if(lv.length===2)return{v:lv.map(x=>x.v==null?'none':x.v),src:lv.every(x=>x.src==='live')?'live':'live, cached'};
 const F=S.find&&S.find.enc&&S.find.enc.sets;if(F){const s=F.find(x=>x.design==='v2e');if(s){const v=names.map(n=>(s.flows.find(f=>f[0]===n)||[])[2]);if(v.every(x=>x!=null))return{v,src:'recorded, '+s.yosys.replace(/\s*\(git.*$/,'')}}}return null}
const TOUR=[
 {t:'One check',s:'V0 · saved gate list',fam:'v0',src:'stored',g:'word',
  q:()=>'V0 compares the input with the key once. How many '+term('flip','flips')+' does it take to make it accept a wrong key?',
  take:r=>r.min_faults===1?'One flip is enough. This is the unprotected starting point.':null},
 {t:'Do the check twice',s:'V1 · saved gate list',fam:'v1',src:'stored',g:'word',
  q:()=>'V1 is the textbook defence: two '+term('copy','copies')+' of the check, and both must agree. Does that force the attacker to use two flips?',
  take:r=>r.min_faults===1?'Still one flip. Both copies report into a single shared wire, and flipping that one wire is enough.':null},
 {t:'Three copies, no shared wire',s:'V2 · saved gate list',fam:'v2',src:'stored',g:'word',
  q:()=>'V2 has three copies and no single deciding wire: each copy sets its own part of the 8-bit result.',
  take:r=>r.min_faults===3?'Three flips were needed here, one per copy. No attack was found with one or two (within the limits shown).':null},
 {t:'Same design, built again',s:'V2 · rebuilt from design',fam:'v2',src:'rtl',g:'word',
  q:()=>'Exactly the same V2 design text, turned into gates again by the build tool (Yosys). Does the count stay the same? The answer depends on the Yosys version and on how it builds.',
  take:r=>{const y=r._prov&&r._prov.yosys?r._prov.yosys.replace(/\s*\(git.*$/,''):'Yosys version not stored',fp=r._prov&&r._prov.netlist_sha?', circuit fingerprint '+r._prov.netlist_sha.slice(0,8)+(r._prov.nl_standin?' (stand-in)':''):'',rec=r._src==='recorded';
   if(r.verdict==='NO_ATTACK_UP_TO_BOUND')return `No attack within ${pl(r._k,'flip')} on this build (${y}${fp}). With Yosys 0.33 the project recorded 2 for the same design text: the count belongs to one circuit file, not to the design idea.`;
   if(r.min_faults==null)return null;
   return r.min_faults<3?`This build gives ${r.min_faults}${rec?' (recorded)':''} (${y}${fp}). The design text did not change; the gate-level build did. The project recorded 3 for the same text with Yosys 0.38+92 (straightforward build): the count belongs to one circuit file, not to the design idea.`
    :`This build gives ${r.min_faults}${rec?' (recorded)':''}, the same as the saved gate list (${y}${fp}). With Yosys 0.33 the project recorded 2 for the same design text.`}},
 {t:'Changing one constant',s:'V2e · rebuilt from design',fam:'v2e',src:'rtl',g:'word',
  q:()=>'A re-encoding test. The project traced the drop on some builds to one constant, the Armed code. V2e changes only that constant (0xCC to 0xA5) and is built the same way.',
  take:r=>{const m=encMerge(),tail=m?` The two build styles that merge the copies give ${m.v.join(' and ')} (${m.src}), and re-encoding does nothing when only the 1-bit flag is read.`:' Re-encoding does nothing when only the 1-bit flag is read.';
   return r.min_faults!=null?`${r.min_faults===3?'Three flips':pl(r.min_faults,'flip')} on this build${recNote(r)}. This is not a general fix.${tail}`:null}},
 {t:'What if only one bit is read?',s:'V2 · 1-bit flag',fam:'v2',src:'stored',g:'flag',
  q:()=>'The same V2 circuit, but the rest of the chip looks only at the single accept bit instead of all eight result bits.',
  take:r=>r.min_faults===1?'One flip, on the flag wire itself. Three copies in front of a single wire do not protect that wire.':null}];
/* Predict first (Plain view): steps 1 to 3 ask for a guess by default (audit 1-S2); the box turns it on for every step
   or off for all. gs_predict: null = steps 1 to 3 (default), true = every step, false = never. */
S.predOn=LS.get('gs_predict',null);S.predPick={};S.seeHow=LS.get('gs_seehow',false);
const predAsk=i=>S.predOn===true||(S.predOn!==false&&i>=0&&i<3);
function predPending(){return !tech()&&S.ti>=0&&predAsk(S.ti)&&S.predPick[S.ti]==null}
function predictHTML(r){const pend=predPending(),pk=S.predPick[S.ti],on=predAsk(S.ti);let h=`<div class="predict"><label class="chk" data-tip="Ask for a guess before each result is shown. Steps 1 to 3 ask by default."><input type="checkbox" id="pred-on" ${on?'checked':''}> Predict first</label>`;
 if(pend)h+=`<span><b>Before you look:</b> how many glitches will this lock need?</span>${[1,2,3].map(n=>`<button class="btn" data-pred="${n}" aria-label="I predict ${n}">${n}</button>`).join('')}<button class="btn" data-pred="0">no way in with up to 3</button><button class="linkb" data-pred="skip">skip: just show me</button><button class="linkb" data-pred="never">stop asking</button>`;
 else if(on&&pk!=null&&pk!=='skip'&&r&&!r.error&&!r._stop){const act=r.verdict==='ATTACK_FOUND'?r.min_faults:0,ok=+pk===act;h+=`<span id="pred-out" role="status" tabindex="-1">You predicted <b>${+pk?pk:'no way in'}</b>. The result: <b>${act?gl(act):'no way in'}</b>. ${ok?'✓ You were right.':'Not what you expected? “What it means” says why.'}</span>`}
 else if(!on)h+=`<span class="hint">Switch this on to guess each number before it is shown.</span>`;
 return h+'</div>'}
function wirePredict(){const c=$('#pred-on');if(c)c.onchange=()=>{S.predOn=c.checked;LS.set('gs_predict',S.predOn);if(!S.predOn)S.predPick={};else if(S.ti>=0&&S.last&&!S.last.error)S.predPick[S.ti]='skip';render();drawSteps();const n=$('#pred-on');n&&n.focus()};
 $$('[data-pred]').forEach(b=>b.onclick=()=>{if(b.dataset.pred==='never'){S.predOn=false;LS.set('gs_predict',false);S.predPick={}}else S.predPick[S.ti]=b.dataset.pred;render();drawSteps();const o=$('#pred-out')||$('#sth2');o&&o.focus({preventScroll:true})})}
function plainTake(i,r){const n=r.min_faults;if(n==null&&r.verdict!=='NO_ATTACK_UP_TO_BOUND')return null;const ts=[...new Set((r.faults||[]).map(f=>f.cycle))].sort((a,b)=>a-b);
 if(i===0)return n===1?'One glitch is enough. This is the unprotected starting point.':null;
 if(i===1)return n===1?'Still one glitch. Both copies report through one shared wire, and glitching that single wire is enough. A second copy did not help. (This design was written that way: the designer drew the shared wire.)':null;
 if(i===2)return n===3?'Three glitches, one per copy, all at the same step. With one or two there was no way in. Keeping the copies apart works.':null;
 if(i===3){if(r.verdict==='NO_ATTACK_UP_TO_BOUND')return `No way in with up to ${gl(r._k)} on this second chip plan. The project saved 2 for another chip plan of the same design: the count belongs to one chip plan, not to the idea.`;
  return n<3?`Only ${gl(n)} on this second chip plan, fewer than the 3 on the first one. The written design did not change; the build tool arranged the parts differently, and the copies no longer fully protect each other.${ts.length>1?` Here the ${words(n)} glitches are ${ts[ts.length-1]-ts[0]===1?'one step':words(ts[ts.length-1]-ts[0])+' steps'} apart: glitches do not have to land together.`:''}`:`${n} glitches, the same as on the first chip plan. Other chip plans of the same design gave fewer: the count belongs to one chip plan.`}
 if(i===4)return n!=null?`${n===3?'Three glitches':gl(n)} on this chip plan${r._src==='recorded'?' (saved result)':''}: changing one pattern helped here. It is not a general fix: chip plans in which the copies got merged stay weak, and it does nothing when only one signal is read.`:null;
 if(i===5)return n===1?'One glitch, on the "open" signal itself. The lock stays shut, but the rest of the chip only looks at that signal, so it starts anyway. Three copies in front of a single signal do not protect that signal: the rest of the chip must read the whole answer.':null;return null}
function drawSteps(){$('#steps').innerHTML=TOUR.map((p,i)=>{const res=S.tourRes[i],q=PATH[i];return `<button class="step${i===S.ti?' on':''}${res!==undefined?' done':''}${i===S.ti&&predPending()?' pend':''}" data-i="${i}" aria-current="${i===S.ti?'step':'false'}"${tech()?` data-tip="${esc('Step '+(i+1)+': loads these settings and runs them')}"`:''}><span class="n">${i+1}</span><span><b>${esc(q.p)}</b><span class="s">${esc(tech()?p.s:q.goal)}</span></span>${res!==undefined?`<span class="r" style="color:${res==='unknown'?'var(--warn)':FC(res)}" data-tip="${res==='unknown'?'unknown: the search did not finish':res==null?'no attack found within the limits':'fewest glitches found'}">${res==='unknown'?'?':res==null?'none':res}</span>`:''}</button>`}).join('')}
function seg(id,v){$$('#'+id+' button').forEach(b=>b.classList.toggle('on',b.dataset.v===v))}
function segv(id){return $('#'+id+' button.on').dataset.v}
function willLive(q){const st=S.status||{};return !!(st.live&&(!q.design.endsWith('_rtl')||st.yosys))}
function syncControls(){const fam=$('#design').value,st=S.status||{};
 $('#design-hint').textContent=tech()?((FAMS.find(f=>f[0]===fam)||[])[2]||''):FAMP[fam][1];
 const b=$('#src button[data-v=stored]');b.disabled=fam==='v2e';if(fam==='v2e')seg('src','rtl');
 const rtl=segv('src')==='rtl';$$('#flow button').forEach(x=>x.disabled=!rtl);
 $('#flow').setAttribute('data-tip',rtl?'How Yosys turns the design text into gates':'Greyed out: this only applies to a circuit rebuilt from the design text');
 const live=willLive(query());$('#cyc').disabled=!live;$('#tl').disabled=!live;if(!live){$('#cyc').value=6}
 $('#cyc-hint').textContent=live||!st.version?'':'Saved results exist for 6 ticks only.';drawDirty();
 $('#kv').textContent=$('#k').value;$('#cv').textContent=$('#cyc').value;
 if(!S.busy)$('#run-hint').innerHTML=!st.studio?'':live?'Live: computed on this computer.':T('Shows a <b>saved result</b> for these settings. ',st.live?'Yosys not installed: shows a <b>saved result</b>. ':'Solver not installed: shows a <b>saved result</b>. ')+'<button class="linkb" data-go="live">How to run it live</button>'}
const qkey=q=>[q.design,q.design.endsWith('_rtl')?q.flow:'',q.goal,q.k,q.cycles].join('|');
function drawDirty(){const el=$('#dirty');if(!el)return;const ch=!!(S.last&&!S.last.error&&S.lastQ&&!S.busy&&qkey(query())!==qkey(S.lastQ));
 el.innerHTML=ch?`<div class="dirty" role="status"><span style="flex:1"><b>Settings changed.</b> The result below is still for the old settings.</span><button class="btn primary" id="d-run">Run to update</button></div>`:'';if(ch)$('#d-run').onclick=()=>$('#run').click()}
['design','k','cyc'].forEach(id=>$('#'+id).addEventListener('input',syncControls));
$$('aside .seg').forEach(s=>s.addEventListener('click',e=>{const b=e.target.closest('button');if(b&&!b.disabled){seg(s.id,b.dataset.v);syncControls()}}));
function query(){const fam=$('#design').value,rtl=segv('src')==='rtl'||fam==='v2e';return{design:rtl?fam+'_rtl':fam,flow:segv('flow'),goal:segv('goal'),k:+$('#k').value,cycles:+$('#cyc').value,time_limit_s:+$('#tl').value}}
function loadStep(i){if(S.busy)return;S.ti=i;S.focusStep=true;const p=TOUR[i];$('#design').value=p.fam;seg('src',p.src);seg('goal',p.g);seg('flow','plain');$('#k').value=3;$('#cyc').value=6;syncControls();show('analyze');drawSteps();run()}
$('#steps').addEventListener('click',e=>{const b=e.target.closest('.step');if(b)loadStep(+b.dataset.i)});
function drawStory(r){const el=$('#story');if(!el)return;if(S.ti<0){el.innerHTML='';return}
 const p=TOUR[S.ti];const good=r&&!r.error,unk=good&&r._stop;const take=good&&!unk&&p.take(r);
 const recnote=good&&r._src==='recorded'?`<p>This step shows a value measured earlier and kept in the project records (${esc(r._prov.record||'')}). On a computer with the engine installed, the same step is computed live.</p>`:'';
 if(!tech()){const q=PATH[S.ti],nx=S.ti<TOUR.length-1;
  const means=predPending()&&good&&!unk?'Make your prediction first. The explanation appears here afterwards.':take?esc(plainTake(S.ti,r)||take):unk?esc(unkText(r))+'. Raise the time limit and try again.':good?'':'Waiting for the result…';
  el.innerHTML=`<div class="panel story plainstory"><div class="shead"><div class="kick">Step ${S.ti+1} of ${TOUR.length} · <b>Goal:</b> ${esc(q.goal)}</div><h2 class="sth" id="sth2" tabindex="-1">${esc(q.p)}</h2></div>
  <div class="nav"><button class="btn" id="prev" ${S.ti===0?'disabled':''} data-tip="Previous step (←)">← Back</button>${nx?'<button class="btn primary" id="next" data-tip="Next step (→)">Next step →</button>':'<button class="btn primary" id="next">Explore more →</button>'}</div>
  <div class="sbody">${orient(esc(q.look),means||'See the result below.',q.next)}${predictHTML(r)}</div></div>`;
  $('#prev').onclick=()=>loadStep(S.ti-1);$('#next').onclick=()=>nx?loadStep(S.ti+1):openExplore();wirePredict();return}
 el.innerHTML=`<div class="panel story"><div class="stx"><h2 class="sth" id="sth2" tabindex="-1">${S.ti+1}. ${esc(PATH[S.ti].p)}</h2><p>${p.q()}</p>${take?`<p class="take"><b>Result:</b> ${esc(take)}</p>`:unk?`<p class="take"><b>Result:</b> ${esc(unkText(r))}. Raise the time limit and run the step again.</p>`:''}${recnote}</div>
 <div class="nav"><span class="cnt">step ${S.ti+1} of ${TOUR.length}</span><button class="btn" id="prev" ${S.ti===0?'disabled':''} data-tip="Previous step (←)">← Back</button><button class="btn" id="next" ${S.ti===TOUR.length-1?'disabled':''} data-tip="Next step (→)">Next →</button></div></div>`;
 $('#prev').onclick=()=>loadStep(S.ti-1);$('#next').onclick=()=>loadStep(S.ti+1)}

/* ---------------- run + stop */
function logLine(tag,text,cls){const d=new Date(),ts=[d.getHours(),d.getMinutes(),d.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':');S.log.push({ts,tag,text,cls});
 if(S.log.length>400)S.log.shift();drawLog()}
function drawLog(){const b=$('#logbody');b.innerHTML=S.log.map(l=>`<span class="t">[${l.ts}]</span> <span class="g">${esc(l.tag.padEnd(6))}</span> <span class="${l.cls||''}">${esc(l.text)}</span>`).join('\n');b.scrollTop=b.scrollHeight;
 const l=S.log[S.log.length-1];$('#loglast').textContent=l?`[${l.ts}] ${l.tag} ${l.text}`:'no run yet'}
function pushServerLog(r){(r._log||[]).forEach(l=>logLine(l.tag,tech()?l.tech:l.plain+'  ·  '+l.tech,l.tag==='DONE'?(r._stop?'e':'ok'):(/MISMATCH|INCOMPLETE|error/.test(l.tech+l.tag)?'e':'')))}
$('#logbar').onclick=()=>toggleLog();function toggleLog(){const d=$('#logdock');d.classList.toggle('open');$('#logtog').textContent=d.classList.contains('open')?'▾':'▴';if(S.last)requestAnimationFrame(drawWave)}
function unkText(r){const s=r._stop||{};return s.why==='timeout'?`UNKNOWN: search stopped at ${s.limit} s; no conclusion`:s.why==='stopped'?`UNKNOWN: search stopped by you after ${s.elapsed} s; no conclusion`:'UNKNOWN: the solver gave no answer; no conclusion'}
function setBusy(on,live){S.busy=on;const b=$('#run');b.classList.toggle('stop',on&&live);$('#run-t').textContent=on?(live?'Stop':'Loading…'):T('Run with these settings','Run analysis');$('#run-k').textContent=on&&live?'Esc':'Enter';b.disabled=on&&!live;
 const R=$('#result');if(R)R.classList.toggle('busy',on);if(!on)syncControls()}
async function run(extra){if(S.busy)return;const q=Object.assign(query(),extra||{});const live=willLive(q)&&!q.force_recorded;q.run_id='r'+Date.now()+Math.random().toString(16).slice(2,6);S.runId=q.run_id;S.lastQ=q;S.ladder=null;
 setBusy(true,live);$('#run-hint').textContent=live?`Searching; stops at ${secs(q.time_limit_s)}.`:'';
 logLine('start',`${q.design} goal=${q.goal} k<=${q.k} N=${q.cycles} flow=${q.flow}`+(live?`  limit ${q.time_limit_s} s`:'  (saved result)'),'p');
 const t0=performance.now();const tick=()=>drawFoot(live?`Searching… ${((performance.now()-t0)/1000).toFixed(1)} s of ${q.time_limit_s} s`:'Loading saved result…');tick();const tk=setInterval(tick,200);
 let r;try{r=await api.post('/api/analyze',q)}catch(e){r={error:'The Studio’s background program is not answering.',error_kind:'server'}}
 clearInterval(tk);S.runId=null;setBusy(false);
 if(r.error){(r._log||[]).forEach(l=>logLine(l.tag,l.tech,'e'));logLine('error',r.error,'e')}else{pushServerLog(r);addHist(r)}
 if(S.ti>=0&&!r.error){S.tourRes[S.ti]=r._stop?'unknown':r.verdict==='ATTACK_FOUND'?r.min_faults:null;LS.set('gs_path',S.tourRes);drawSteps()}
 S.last=r;S.cursor=null;S.zoom=null;S.mapMode='focus';render();drawDirty();
 if(!r.error&&r._src==='live'&&r.verdict==='ATTACK_FOUND'&&r.min_faults>0)startLadder(r,q)}
function stopRun(){if(S.busy&&S.runId){logLine('stop','stop requested','e');api.post('/api/stop',{run_id:S.runId}).catch(()=>{})}}
$('#run').onclick=()=>{if(S.busy){stopRun();return}S.ti=-1;drawSteps();run()};
/* each smaller flip count searched on its own, in the background (live only) */
async function startLadder(r,q){const key=q.run_id;S.ladder={key,res:{},status:'running',n:r.min_faults};render1();
 let j;try{j=await api.post('/api/job',{study:'ladder',params:{design:q.design,flow:q.flow,goal:q.goal,cycles:q.cycles,upto:r.min_faults,time_limit_s:q.time_limit_s}})}catch(e){return}
 if(!j.id){S.ladder.status='error';render1();return}
 const poll=async()=>{if(!S.ladder||S.ladder.key!==key)return;let s;try{s=await api.get('/api/job?id='+j.id)}catch(e){return}
  if(!S.ladder||S.ladder.key!==key)return;S.ladder.res=s.results||{};S.ladder.status=s.status;drawLadder();
  if(s.status==='running')setTimeout(poll,400);else{const bad=Object.values(S.ladder.res).filter(x=>x.state==='ok'&&x.v!=null).length,unk=Object.values(S.ladder.res).filter(x=>x.state!=='ok').length;
   logLine('ladder',bad?'A SMALLER ATTACK WAS FOUND by the separate searches: the minimum shown is not minimal':unk?`fewer flips: ${unk} separate search(es) did not finish; fewer flips are not ruled out by them`:`each smaller flip count searched separately: no attack with 0..${r.min_faults-1} flips`,bad||unk?'e':'p')}};poll()}
function render1(){drawLadder()}

/* ---------------- render result */
function boundBits(r){const g=r._goal==='flag';return [
 ['flips',T(`up to <b>${r._k}</b>`,`k ≤ <b>${r._k}</b>`)],['time window',T(`<b>${r._cycles}</b> ticks`,`N = <b>${r._cycles}</b> cycles`)],
 [T('thief must fake','goal'),T(g?'one “open” signal':'the whole answer',g?'<b>boot_ok == 1</b>':'<b>boot_word == 0x96</b>')],
 [T('key','attacker input'),T('any wrong key, held steady','`sig` free, constant, ≠ 0xC3')],
 [T('glitch model','fault model'),T('one wire or memory cell gives the wrong answer for one step','single-cycle bit flip of a gate output or flop Q')],
 [T('chip plan','netlist / flow'),T(r._build==='stored'?'the first (saved) chip plan only':'this one chip plan only',esc(r._flow))]]}
function meaning(r){const n=r.min_faults,k=r._k,N=r._cycles;
 if(r._stop)return `The search did not finish, so <b>nothing can be concluded</b>: there may or may not be an attack with up to ${pl(k,'flip')} in ${N} ticks. This is not "no attack found". Raise the time limit or lower the flips or ticks, and run again.`;
 if(r.verdict==='ATTACK_FOUND'){const ts=[...new Set(r.faults.map(f=>f.cycle))].sort();
  const when=ts.length===1?` at ${term('tick')} ${ts[0]}`:` at ticks ${ts.join(' and ')}`;
  const fg=r._goal==='flag',subj=fg?T('The “open” signal said yes for a wrong','boot_ok read 1 for a wrong'):'The lock accepted a wrong';
  let s=n===0?'The lock accepts a wrong key with no flip at all.':n===1?`${subj} ${term('key')} when <b>one</b> ${term('wire')} gave the wrong answer for one tick${when}.`:
   `${subj} ${term('key')} when <b>${n}</b> wires each gave the wrong answer for one tick${when}.`;
  if(fg&&n>0)s+=T(' Only that signal was faked, and it is all the rest of the chip reads here.',' Only that one bit was faulted; it is all the consumer reads in this setting.');
  if(n>1)s+=` With fewer than ${n} flips the search found no attack inside the limits below.`;
  return s+' More flips needed means a harder attack in this model. This is a computer model of a toy circuit; no chip was glitched.'}
 return `No way was found to make the lock accept a wrong key with up to <b>${k}</b> ${term('flip',k===1?'flip':'flips')} inside <b>${N}</b> ticks. That is the ${term('limit')} of this search, not a guarantee: more flips, more ticks and other kinds of glitch were not tried. Computer model of a toy circuit.`}
function happened(r){const fs=r.faults||[],n=fs.length;if(!n)return '';const g=fs.map(f=>f.group),copies=[...new Set(g.filter(x=>/^c\d$/.test(x)))];
 const ts=[...new Set(fs.map(f=>f.cycle))];let s;const f=fs[0],rt=f.reach_total;
 const reachTxt=fs.every(x=>x.reach!=null)?(fs.every(x=>x.reach===rt)?`each can reach all ${rt} result bits before Accept`:'the last column shows how many result bits each can still reach before Accept'):'';
 if(n===1&&f.group==='flag')s='No check had to be fooled. The single accept bit itself was flipped for one tick, and that bit is all the rest of the chip reads here.';
 else if(n===1&&f.group==='state')s='One memory bit of the lock state was flipped directly, and the state then read as Accept.';
 else if(n===1&&f.reach!=null&&f.reach===rt&&f.key_bits>=8)s=`This one wire depends on all ${f.key_bits} key bits and can reach all ${rt} result bits: the copies report into it, and it alone decides. Flipping it once makes a wrong key look right.`;
 else if(n===1)s=`Flipping this one wire was enough: it can reach ${f.reach===rt?'all '+rt:(f.reach??'some')+' of the '+(rt??'')} result bits before Accept.`;
 else if(copies.length===n&&g.every(x=>/^c\d$/.test(x)))s=`One flip landed inside each of the ${n} copies${ts.length===1?', all in the same tick':''}. Every copy was fooled separately; no single wire was enough.`;
 else if(g.every(x=>x==='merged'||x==='state'))s=`The flips land on wires that do not belong to any one copy in this ${T('chip plan','netlist')} (the build tool rearranged the logic)${reachTxt?'; '+reachTxt:''}.`;
 else s=`The ${n} flips are listed above with where and when they happen.`;
 return s+' The solver reports one smallest attack; other equally small ones can exist.'}
function ladderHTML(r){const atk=r.verdict==='ATTACK_FOUND',n=r.min_faults;if(r._stop)return '';let lad='';const top=atk?n:r._k,L=S.ladder&&S.lastQ&&S.ladder.key===S.lastQ.run_id?S.ladder:null;
 for(let j=0;j<=top;j++){if(atk&&j===n){lad+=`<div class="hit" data-tip="An attack with ${pl(j,'flip')} exists (shown below)"><b>${j}</b>${T('gets in','accept')}</div>`;continue}
  const x=L&&L.res['ladder|'+j];let cls='',lab=T('no way in','ruled out'),tip=atk?`No attack with ${pl(j,'flip')}: ruled out by the same search, which lowers the count until none is left (minimisation)`:`No attack with ${pl(j,'flip')} inside the limits: covered by the same search`;
  if(x){if(x.state==='ok'&&x.v==null){cls='chk';lab='none ✓';tip=`Searched on its own just now: no attack with ${pl(j,'flip')} (${x.src}, ${x.secs} s)`}
   else if(x.state==='ok'){cls='hit';lab='ATTACK';tip=`The separate search FOUND an attack with ${pl(j,'flip')}: the minimum shown is not minimal`}
   else{cls='unk';lab='unknown';tip=`The separate search with ${pl(j,'flip')} did not finish (${x.note||x.state}): fewer flips are not ruled out by it`}}
  else if(L&&L.status==='running'){lab='…'}
  lad+=`<div class="${cls}" data-tip="${esc(tip)}"><b>${j}</b>${lab}</div>`}
 return `<div class="ladder-t">${T('fewer flips','k below the minimum')}${L?(L.status==='running'?' · checking each separately…':' · each searched separately'):''}</div><div class="ladder">${lad}</div>`}
function drawLadder(){const el=$('#ladbox'),r=S.last;if(el&&r&&!r.error)el.innerHTML=ladderHTML(r)}
/* audit 5-S3: one polite live region; a screen reader hears the result, a stopped search and a server that stopped answering */
function announce(t){const n=$('#sr-live');if(n&&t&&n.textContent!==t){n.textContent='';setTimeout(()=>{n.textContent=t},60)}}
function render(){const r=S.last,R=$('#result');if(!R)return;$('#b-export').disabled=!r||!!r.error;$('#b-export').classList.toggle('hidden',!r||!!r.error);drawStory(r);drawFoot();
 {const pend=predPending()&&!!r&&!r.error&&!r._stop;R.classList.toggle('veil',pend);R.inert=pend;if(pend)R.setAttribute('aria-hidden','true');else R.removeAttribute('aria-hidden')}
 const st=S.status||{};const mode=st.studio&&!st.live?savedBanner():'';
 if(!r){R.innerHTML=mode+`<div class="empty"><b>Nothing tried yet</b>Press the button to watch the recommended first example, or pick a step of the path on the left.<br><br><button class="btn primary" id="e-try">▶ Watch the first attack</button><br><br>The app finds the fewest ${term('glitch','glitches')} that make a small example lock accept a wrong key.</div>`;$('#e-try').onclick=tryAttack;return}
 if(r.error){const k=r.error_kind;R.innerHTML=noProjectBanner()+`<div class="err"><b>${k==='no_record'?'No saved result for these settings':k==='server'?'The Studio has stopped':k==='bad_settings'?'The settings are not valid':'The analysis could not run'}</b><p>${esc(r.error)}</p>
  ${k==='no_record'?'<p><button class="btn" id="e-near">Load the closest saved setting</button></p>':k==='server'?'<p>Start GlitchSAT Studio again from the menu or the terminal, then reload this window.</p>':''}
  ${r.can_fallback?'<p><button class="btn" id="e-rec">Show the saved result instead</button></p>':''}
  ${r.error_detail?`<details class="raw"><summary>Details from the engine</summary><pre>${esc(r.error_detail)}</pre></details>`:''}</div>`;
  if($('#e-rec'))$('#e-rec').onclick=()=>run({force_recorded:true});
  if($('#e-near'))$('#e-near').onclick=()=>{seg('goal','word');if(+$('#k').value>3)$('#k').value=3;$('#cyc').value=6;syncControls();run()};return}
 const atk=r.verdict==='ATTACK_FOUND',unk=!!r._stop,n=r.min_faults,pv=r._prov,rec=r._src==='recorded';
 announce(predPending()?'Result ready. Make your prediction first.':unk?'Search stopped before it finished: no result.':atk?`Result: ${gl(n)} needed.`:`Result: no way in found with up to ${gl(r._k)}.`);
 const vc=unk?'var(--warn)':FC(atk?n:null);
 const title=unk?unkText(r):atk?T(`Cheapest attack found: ${pl(n,'flip')}`,`ATTACK_FOUND · minimum k = ${n}`):T(`No attack found within the limits (up to ${pl(r._k,'flip')}, ${r._cycles} ticks)`,`NO_ATTACK_UP_TO_BOUND · k ≤ ${r._k}, N = ${r._cycles}`);
 let chips=hon(rec?'recorded':'live');
 if(pv.derived)chips+=ntag(T('worked out from a saved result','derived from a recorded run'),`The saved run used a limit of ${pv.k_rec} flip(s) and found a minimum of ${pv.min_rec}. A minimum does not change with a larger limit, so it gives the answer for your limit.`);
 if(pv.nl_standin)chips+=ntag(T('pictures drawn on a similar chip plan','views on a stand-in netlist'),'The recorded run did not keep its circuit file. The pictures, the Yosys version and the fingerprint come from a stored build with the same gate count and wire names, on which the recorded attack was re-checked.');
 if(r._cmp)chips+=r._cmp.same?ntag('same as the recorded result ✓',`The project's saved result for the same settings gives the same answer${tech()?' ('+r._cmp.file+')':''}.`,'ok')
   :ntag(`differs from the recorded result (${r._cmp.min==null?'none found':r._cmp.min})`,`The project's saved result for the same settings differs${tech()?' ('+r._cmp.file+(r._cmp.yosys?', built with '+r._cmp.yosys:'')+')':''}. A rebuilt circuit depends on the Yosys version; both numbers are shown.`,'bad');
 const y=pv.yosys?pv.yosys.replace(/\s*\(git.*$/,'').replace(/^Yosys\s+/,''):null;
 const srcPlain=rec?`Saved result from the project files${pv.nl_standin?'; the pictures are drawn on a similar chip plan with the same parts':''}.`:`Computed just now on this computer in ${(+r._wall).toFixed(1)} s.`;
 let h=`<div class="panel" style="--vc:${vc}"><div class="verdict"><div class="vnum${!atk&&!unk?' none':''}">${unk?'<b>?</b><span>unknown</span>':atk?`<b>${n}</b><span>${T(G(n),n===1?'fault':'faults')}</span>`:tech()?`<b>&gt;${r._k}</b><span>none found</span>`:`<b>0</b><span>ways in</span><span class="sub2">with up to ${gl(r._k)}</span>`}</div>
  <div>${tech()?`<div class="vt">${esc(title)} ${chips}</div>`:`<div class="vt sentence0">${esc(resultSentence(r))}</div><div class="chiprow">${chips}</div>`}<div class="vm"><b>What this means.</b> ${meaning(r)}</div></div>
  <div id="ladbox">${ladderHTML(r)}</div></div>
  <div class="bound tech-only" data-tip="Every result holds only inside these limits."><span><span class="k">Bound</span></span>${boundBits(r).map(b=>`<span><span class="k">${b[0]}</span>${b[1]}</span>`).join('')}</div>
  <div class="srcline plain-only"><b style="color:var(--txt)">Limits.</b> We tried every wrong key and up to ${gl(r._k)} within ${r._cycles} steps, on this one chip plan. Nothing is claimed beyond that.</div>
  <div class="srcline plain-only">${srcPlain} ${r.netlist&&r.netlist.gates?`Size of this lock: ${r.netlist.gates} gates, ${r.netlist.flops} memory bits.`:''}</div>
  <div class="prov tech-only"><span><span class="k">source</span><span class="v">${rec?'recorded':'live'}</span></span><span><span class="k">engine</span><span class="v">${esc(pv.engine.split(' (')[0])}</span></span>
   <span><span class="k">z3</span><span class="v">${esc(pv.z3||'n/a')}</span></span><span data-tip="${esc('Where this version comes from: '+pv.yosys_from)}"><span class="k">Yosys</span><span class="v">${esc(y||'n/a')}</span></span>
   <span data-tip="Fingerprint of the exact circuit file used for the pictures and the replay"><span class="k">netlist sha256</span><span class="v">${pv.netlist_sha?pv.netlist_sha.slice(0,16)+'…':'not kept'}</span></span>
   ${r.netlist&&r.netlist.gates?`<span><span class="k">netlist</span><span class="v">${r.netlist.gates} gates, ${r.netlist.flops} flops</span></span>`:''}
   ${r._wall!=null&&!rec?`<span><span class="k">wall time</span><span class="v">${(+r._wall).toFixed(2)} s of ${pv.time_limit_s} s</span></span>`:''}
   ${S.lastQ&&FAMP[S.lastQ.design.replace(/_rtl$/,'')]?`<span><span class="k">design</span><span class="v keep">${esc(S.lastQ.design.replace(/_rtl$/,'').toUpperCase().replace('V2E','V2e'))} (${esc(PK[S.lastQ.design.replace(/_rtl$/,'').toUpperCase().replace('V2E','V2e')]||'')})</span></span>`:''}</div>
  ${pv.nl_standin?`<div class="srcline tech-only keep"><b style="color:var(--txt)">Which netlist.</b> Count: recorded run (its netlist was not kept). Waveform and schematic: re-checked on a stored netlist with the same count${pv.netlist_sha?' (sha256 '+esc(pv.netlist_sha.slice(0,12))+'…)':''}; the Yosys version shown is that stored netlist’s.</div>`:''}
  <details class="more"><summary>${T('Learn more (technical details and how to reproduce)','Provenance and reproduce')}</summary><div class="kv">
   ${tech()?'':boundBits(r).map(b=>`<div>limit: ${b[0]}</div><div style="font-family:var(--sans)">${b[1]}</div>`).join('')}
   <div>source</div><div>${rec?'recorded: '+esc(pv.record)+(pv.record_extra?' · '+esc(pv.record_extra):''):'live run on this computer'}</div>
   ${pv.derived?`<div>derived</div><div>saved run used k ≤ ${pv.k_rec} and found minimum ${pv.min_rec}; the answer for k ≤ ${r._k} follows from that minimum</div>`:''}
   ${r._cmp?`<div>recorded for the same settings</div><div>${r._cmp.min==null?'no attack found':'minimum '+r._cmp.min} (${esc(r._cmp.file)}${r._cmp.yosys?'; '+esc(r._cmp.yosys):''}): ${r._cmp.same?'same as this live run':'DIFFERENT from this live run'}</div>`:''}
   <div>engine</div><div>${esc(pv.engine)}</div><div>solver</div><div>z3 ${esc(pv.z3||'n/a')}</div><div>Yosys</div><div>${esc(pv.yosys||'n/a')} (${esc(pv.yosys_from)})</div>
   <div>design file</div><div>${esc(pv.design)}${pv.design_sha?' · sha256 '+esc(pv.design_sha)+'…':''}</div>
   <div>netlist used for views</div><div>${esc(pv.netlist||'not available')}${pv.netlist_sha?' · sha256 '+esc(pv.netlist_sha):''}${pv.nl_standin?' (stand-in for the recorded run’s own file)':''}</div>
   <div>fault model</div><div>${esc(pv.fault_model)}</div><div>attacker input</div><div>${esc(pv.attacker_input)}</div><div>goal</div><div>${esc(pv.goal)}</div>
   ${r.model&&r.model.sites_total?`<div>fault sites</div><div>${r.model.sites_total} (site × cycle) in total, ${r.model.sites_modelled} modelled after reduction (${esc(r.model.reduce)})</div>`:''}
   ${rec&&r._wall!=null?`<div>solver time in the record</div><div>${(+r._wall).toFixed(2)} s${/results\/reproduce/.test(pv.record||'')?' (as stored; these files predate the current at-most-k encoding, so a live run is not expected to take the same time)':' (as stored)'}</div>`:''}
   ${!rec?`<div>time limit</div><div>${pv.time_limit_s} s; the engine runs in its own process without a solver timeout and is stopped from outside at the limit, so a finished run is exact and a stopped run is UNKNOWN</div>`:''}
   ${r.honest_key_boots_fault_free!=null?`<div>${T('right key, no glitches','honest key, no faults')}</div><div>${r.honest_key_boots_fault_free?'reaches Accept (sanity check passed)':'DOES NOT reach Accept'}</div>`:''}
   ${atk&&r.attacker_input?`<div>wrong key in this attack</div><div>${esc(r.attacker_input.sig)} (right key 0xC3)${r._replay&&r._replay.key_from_replay?' · not stored in the record; found by trying wrong keys in the replay':''}</div>`:''}
   <div>equivalent command</div><div>${esc(pv.cli)} <button class="btn" id="b-copy" style="padding:1px 7px;font-size:11px;margin-left:6px">copy</button></div>
   ${(S.status||{}).gallery?`<div>two tools, one name</div><div style="font-family:var(--sans)">This command is the built-in engine (scripts/glitchsat.py, solver z3). It produced every number on the path, in Explore and in Studies; its “check” runs the analysis. The own-design tool behind “Open my design” and the example gallery is a separate program (“glitchsat”, with its own solver and a project file): there --k is called max_faults, --cycles is called horizon, and “check” only validates the project file.</div>`:''}
   <div>versions</div><div>GlitchSAT ${esc(pv.engine_version||'?')} · Studio interface ${esc(pv.studio)}</div></div></details></div>`;
 const wave=`<div class="panel"><div class="ph"><h4>${T('What happens, tick by tick','Witness waveform')}</h4><span class="hint" data-tip="Not a new result and not a measurement: the answer above, played back step by step on the same circuit file by a small simulator inside this app.">${T('replay of the result above','replay of the witness above (built-in simulator)')}</span><span class="sp"></span>
   <label style="font-size:11.5px;color:var(--mut);display:flex;gap:5px;align-items:center" data-tip="Add the run with the right key and no flips, for comparison"><input type="checkbox" id="honest" ${S.honest?'checked':''}> ${T('show the right key too','show honest key 0xC3')}</label></div>
   <div id="wavebox"></div><div class="cap" id="wavecap"></div></div>`;
 const nowave=`<div class="panel"><div class="ph"><h4>${T('What happens, tick by tick','Witness waveform')}</h4></div><div class="note">${unk?'<b style="color:var(--warn)">'+esc(unkText(r))+'.</b> There is no attack to replay and no "no attack" result either, so nothing is drawn here.':esc(pv.nl_note)}</div></div>`;
 let ft='';if(atk){const tot=r.model&&r.model.sites_total;ft=`<div class="panel"><div class="ph"><h4>${T('The flips in this attack','Faults in the witness')}</h4><span class="sp"></span>${tot?`<span style="font-size:11px;color:var(--mut)" data-tip="Every wire or memory bit, at every tick, is one place a flip could hit">${T(`${r.faults.length} of ${tot} places a flip could hit`,`${r.faults.length} of ${tot} site × cycle`)}</span>`:''}</div>
  <table><thead><tr><th>#</th><th>${T('when','cycle')}</th><th>${T('where','net')}</th><th>${T('what','driver')}</th><th data-tip="How many of the result bits this wire can still influence between its flip and the tick where Accept is seen">${T('how much of the answer it controls','reach before goal')}</th></tr></thead><tbody>${r.faults.map((f,i)=>`<tr class="frow" data-net="${f.net_id??''}" data-tip="Click to find this wire on the circuit map" data-tipm="${esc(f.net)}"><td><span class="bolt">⚡</span>${i+1}</td><td>${T('tick ','')}${f.cycle}</td>
   <td>${tech()?`<span class="mono">${esc(f.net)}</span>`:`<span class="dot" style="background:${GC(f.group)}"></span>${esc(f.plain)}`}</td><td>${f.gate?esc(f.gate==='DFF'?T('memory bit','DFF Q'):f.gate+T(' gate','')):'<span style="color:var(--dim)">n/a</span>'}</td><td>${f.reach!=null?(f.reach_total===1?T('all of it: it is the “open” signal','1 of 1'):tech()?`${f.reach} of ${f.reach_total}`:f.reach===f.reach_total?'all of it':`${f.reach} of ${f.reach_total} parts`):'<span style="color:var(--dim)">n/a</span>'}</td></tr>`).join('')}</tbody></table>
  <div class="cap"><b class="w">What this means.</b> ${esc(happened(r))}</div></div>`}
 let own='';if(r._own){const o=r._own,need=o.copies_needed.length,nchg=o.bits.filter(b=>b.change).length;own=`${tech()?'<div class="panel"><div class="ph"><h4>Result-word bit ownership</h4></div>':'<details class="more learn"><summary>Learn more: which copy sets which answer signal</summary>'}<div class="pb"><div class="own">${[7,6,5,4,3,2,1,0].map(i=>{const b=o.bits[i],hit=(r.faults||[]).some(f=>f.group==='c'+b.copy);
   return `<div class="ob${b.change?' chg':''}" style="--oc:var(--c${b.copy})" data-tip="Result bit ${i} is set by copy ${b.copy+1}. In the Armed state it is ${b.armed}; for Accept it must be ${b.open}${b.change?' (it has to change)':''}.${hit?' A flip in this attack landed in copy '+(b.copy+1)+'.':''}"><div class="i">${T('signal','bit')} ${i}</div><div class="c">copy ${b.copy+1}</div><div class="v">${b.change?`${b.armed}→${b.open}`:`<s>${b.armed}</s>`}</div></div>`}).join('')}</div></div>
   <div class="cap"><b class="w">What this means.</b> ${tech()?`To turn the Armed pattern (${hex(o.armed)}) into Accept (${hex(o.open)}, XOR ${hex(o.xor)}), the ${nchg} bits marked with a bar must change. They belong to <b style="color:var(--txt)">${need} of the 3 copies</b>${need<3?', so in principle fooling those '+need+' copies could be enough':', so every copy has to be fooled'}.`
     :`Each of the 8 answer signals is set by one copy. To fake Open, the ${nchg} signals marked with a bar must change. ${need<3?`Those belong to <b style="color:var(--txt)">${need} of the 3 copies</b> only, so on some chip plans ${gl(need)} are enough (step 4 of the path shows one).`:'They belong to <b style="color:var(--txt)">all 3 copies</b>, so every copy has to be fooled.'}`}
   ${atk?(n>need?` This chip plan does not reach that lowest count: it needed ${n}.`:n===need?` This chip plan reaches exactly that count (${n}).`:` This chip plan needed only ${n}: its flips are not inside the copies.`):''}<span class="tech-only"> Source: ${esc(o.source)}; docs/report/WHY_TWO_FLIPS.md.</span></div>${tech()?'</div>':'</details>'}`}
 const map=r._map?`<div class="panel"><div class="ph"><h4>${T('Circuit map','Schematic')}</h4><span class="hint" data-tip="Drawn automatically from the circuit file to show connections. It is not the physical layout of a chip.">${T('drawn automatically; not how the chip is laid out','auto-drawn schematic, not a layout')}</span><span class="sp"></span>
   <div class="seg" id="mapmode">${r._map.focus?`<button data-v="focus" data-tip="Only the gates that feed the flipped wires and the gates the wrong value travels through">${T('Attack path','Fault cone')}</button>`:''}<button data-v="full" data-tip="Every gate of the circuit">${T('Whole circuit','Full netlist')}</button></div>
   <button class="btn ico" id="zo" data-tip="Zoom out">−</button><button class="btn ico" id="zi" data-tip="Zoom in">+</button><button class="btn" id="zf" data-tip="Fit to the panel width">Fit</button></div>
   <div class="mapwrap" id="mapbox"></div><div class="cap" id="mapcap"></div></div>`:'';
 h+=findingsHTML(r.findings);
 const deep=`<div class="cols"><div>${r._replay?wave:nowave}</div><div>${ft}${own}</div></div>${unk?'':fixHost(fixKindOf(r))}${map}`;
 /* Plain view: the replay, the glitch table, the fix and the map wait behind "See how" (audit 1-S1); once a learner has opened
    it, it stays open on the next steps. Technical view shows everything. */
 h+=tech()?deep:`<details class="more seehow" id="seehow"${S.seeHow?' open':''}><summary><b>See how</b>: the step-by-step replay, where the glitches land, how to fix it, and the circuit map</summary>${deep}</details>`;
 if(pv.nl_note&&r._replay)h+=`<div class="banner"><span><b style="color:var(--txt)">Note.</b> ${tech()?esc(pv.nl_note):pv.nl_standin?'The saved result did not keep its own chip plan. The pictures are drawn on a stored plan with the same parts, and the attack was re-checked on it.':esc(pv.nl_note)}</span></div>`;
 R.innerHTML=h;
 const cp=$('#b-copy');if(cp)cp.onclick=e=>{e.preventDefault();navigator.clipboard&&navigator.clipboard.writeText(pv.cli);cp.textContent='copied'};
 const hb=$('#honest');if(hb)hb.onchange=()=>{S.honest=hb.checked;drawWave()};
 if($('#mapmode')){if(!r._map.focus)S.mapMode='full';seg('mapmode',S.mapMode);$('#mapmode').onclick=e=>{const b=e.target.closest('button');if(b){S.mapMode=b.dataset.v;S.zoom=null;seg('mapmode',S.mapMode);drawMap()}};
  $('#zi').onclick=()=>{S.zoom=(S.zoom||mapFit())*1.25;drawMap()};$('#zo').onclick=()=>{S.zoom=(S.zoom||mapFit())/1.25;drawMap()};$('#zf').onclick=()=>{S.zoom=null;drawMap()}}
 $$('tr.frow').forEach(tr=>tr.onclick=()=>locate(tr.dataset.net));
 const shw=$('#seehow');if(shw)shw.addEventListener('toggle',()=>{if(shw.open){if(!S.seeHow){S.seeHow=true;LS.set('gs_seehow',true)}drawWave();drawMap()}});
 drawWave();drawMap();if(S.focusStep){S.focusStep=false;const hh=$('#sth2');if(hh&&S.tab==='analyze')hh.focus({preventScroll:true})}}
const GC=g=>/^c\d$/.test(g)?`var(--${g})`:g==='flag'||g==='state'?'var(--warn)':'var(--shared)';

/* ---------------- waveform */
const SHORT={Idle:'Idl',Armed:'Arm',Accept:'Acc',Reject:'Rej'};
function drawWave(){const r=S.last,box=$('#wavebox');if(!box||!r||r.error||!r._replay)return;const rp=r._replay,N=rp.ticks;
 const Wd=Math.max(520,box.clientWidth),nameW=Math.min(250,Math.max(170,Wd*0.31)),valW=tech()?62:70,x0=nameW+valW,cw=(Wd-x0-8)/N;
 if(S.cursor==null)S.cursor=rp.fault_ticks&&rp.fault_ticks.length?rp.fault_ticks[0]:rp.opens_at!=null?rp.opens_at:Math.min(2,N-1);
 const lockRow=rp.rows.find(x=>x.plain==='Lock state'),lockOpens=!!(lockRow&&lockRow.attack.some(v=>(lockRow.names||{})[v]==='Accept')),fgoal=r._goal==='flag'&&!rp.no_attack&&rp.opens_at!=null;
 const lockAt=fgoal&&lockRow?((lockRow.names||{})[lockRow.attack[rp.opens_at]]||null):null;
 const cur=Math.min(N-1,S.cursor);let y=44,o='';
 const vtxt=(row,v,lane)=>{if(row.kind==='bus'){if(row.id==='sig')return tech()?hex(v).slice(2):(lane==='honest'?'right key':'wrong key');const nm=row.names&&row.names[v];
   if(tech())return hex(v,Math.ceil(row.width/4)).slice(2)+(nm?' '+nm:'');return nm||'garbled'}
  return tech()||/^n\d/.test(row.id)&&!/says/.test(row.plain)?String(v):(v?'yes':'no')};
 const fitTxt=(row,v,lane,w,fs)=>{const full=vtxt(row,v,lane),cap=c=>c.length*fs*0.58+8<=w;if(cap(full))return full;const nm=row.names&&row.names[v];
  if(row.kind==='bus'&&row.id!=='sig'){const alts=tech()?[hex(v,Math.ceil(row.width/4)).slice(2)]:[nm?SHORT[nm]:'n/v',nm?nm[0]:'?'];for(const a of alts)if(cap(a))return a}return ''};
 const lanesOf=row=>{const l=[['attack',rp.no_attack?'wrong key, no flips':'with the flips']];const diff=(a,b)=>row[a].some((v,i)=>v!==row[b][i]);
  if(!rp.no_attack&&diff('attack','clean'))l.push(['clean','same key, no flips']);if(S.honest&&(row.id==='sig'||row.id==='boot_word'||row.id==='st'||row.id==='boot_ok'||diff('honest','attack')))l.push(['honest','right key, no flips']);return l};
 const X=t=>x0+t*cw;
 let body='';
 rp.rows.forEach(row=>{const lanes=lanesOf(row);
  lanes.forEach(([lane,lname],li)=>{const main=li===0,vals=row[lane];
   const col=lane==='honest'?'var(--acc)':main?'var(--txt)':'var(--mut)',dash=lane==='clean'?' stroke-dasharray="4 3"':'';
   let label=main?(tech()?row.tech:plainText(row.plain)):lname,l2=null,l3=null;const maxc=Math.floor((nameW-16)/6.3);
   if(label.length>maxc){if(main&&!tech()){const cut=label.lastIndexOf(' ',maxc);if(cut>0){l2=label.slice(cut+1);label=label.slice(0,cut);if(l2.length>maxc){const c2=l2.lastIndexOf(' ',maxc);if(c2>0){l3=l2.slice(c2+1);l2=l2.slice(0,c2);if(l3.length>maxc)l3=l3.slice(0,maxc-1)+'…'}else l2=l2.slice(0,maxc-1)+'…'}}}if(!l2)label=label.slice(0,maxc-1)+'…'}
   const hgt=main?(l3?44:l2?30:20):15,yc=y+hgt/2;
   body+=`<g data-tip="${esc(main?row.plain:lname)}" data-tipm="${esc(row.tech)}"><rect x="0" y="${y}" width="${nameW}" height="${hgt}" fill="transparent"/><text x="${main?10:22}" y="${l3?yc-9:l2?yc-2:yc+4}" font-size="${main?12:10.5}" class="${main?(tech()?'mono':''):'m'}" ${main&&row.group?`fill="${GC(row.group)}"`:''}>${esc(label)}</text>${l2?`<text x="10" y="${l3?yc+4:yc+11}" font-size="12" ${row.group?`fill="${GC(row.group)}"`:''}>${esc(l2)}</text>`:''}${l3?`<text x="10" y="${yc+17}" font-size="12" ${row.group?`fill="${GC(row.group)}"`:''}>${esc(l3)}</text>`:''}</g>`;
   body+=`<text x="${nameW+valW-10}" y="${yc+4}" font-size="11" text-anchor="end" class="mono" fill="${col}">${esc(fitTxt(row,vals[cur],lane,valW+26,11)||vtxt(row,vals[cur],lane).slice(0,9))}</text>`;
   if(row.kind==='bus'){let s=0;for(let t=1;t<=N;t++){if(t===N||vals[t]!==vals[s]){const xa=X(s)+1,xb=X(t)-1,sl=4,v=vals[s],nm=row.names&&row.names[v];
      const open=row.id!=='sig'&&nm==='Accept',fill=open?(lane==='honest'?'color-mix(in srgb,var(--acc) 18%,transparent)':'color-mix(in srgb,var(--warn) 24%,transparent)'):'none',st=open&&lane!=='honest'?'var(--warn)':col;
      const fs=main?11.5:10,tx=fitTxt(row,v,lane,xb-xa,fs);
      body+=`<g data-tip="${esc(row.id==='sig'?(lane==='honest'?'the right key':'a wrong key, held steady'):nm?nm+': '+GLOSS[nm]:'Not one of the four valid lock states')}" data-tipm="${hex(v,Math.ceil(row.width/4))}"><path d="M${xa+sl},${yc-hgt/2+2}H${xb-sl}L${xb},${yc}L${xb-sl},${yc+hgt/2-2}H${xa+sl}L${xa},${yc}Z" fill="${fill==='none'?'transparent':fill}" stroke="${st}" stroke-width="${main?1.3:1}"${dash}/>
      ${tx?`<text x="${(xa+xb)/2}" y="${yc+4}" font-size="${fs}" text-anchor="middle" class="${tech()?'mono':''}" fill="${st}" pointer-events="none">${esc(tx)}</text>`:''}</g>`;s=t}}}
   else{const hi=yc-hgt/2+3,lo=yc+hgt/2-3;let d='';for(let t=0;t<N;t++){const yy=vals[t]?hi:lo;d+=(t?`V${yy}`:`M${X(0)+1},${yy}`)+`H${X(t+1)-(t===N-1?1:0)}`}
    const on=row.id==='boot_ok'&&lane!=='honest';
    if(on){for(let t=0;t<N;t++)if(vals[t])body+=`<rect x="${X(t)}" y="${hi}" width="${cw}" height="${lo-hi}" fill="color-mix(in srgb,var(--warn) 22%,transparent)" pointer-events="none"/>`}
    body+=`<path d="${d}" fill="none" stroke="${on&&vals.some(v=>v)?'var(--warn)':col}" stroke-width="${main?1.5:1.1}"${dash} pointer-events="none"/>`}
   if(main)row.flips.forEach(t=>{const bx=row.kind==='bus'?X(t)+12:X(t)+cw/2;body+=`<g data-tip="Flip: this wire gives the wrong answer during tick ${t} only"><circle cx="${bx}" cy="${yc}" r="9" fill="var(--panel)" stroke="var(--hot)" stroke-width="1.3"/><path d="M${bx+1.5},${yc-6}l-5,7h3.4l-1.4,5 5.2,-7.4h-3.4z" fill="var(--hot)"/></g>`});
   y+=hgt+3});
  if(row===lockRow&&fgoal&&!lockOpens&&!tech()){body+=`<text x="22" y="${y+9}" font-size="10.5" fill="var(--warn)">the lock never opened; only its “open” signal was faked</text>`;y+=15}
  y+=7;body+=`<line x1="0" x2="${Wd}" y1="${y-4}" y2="${y-4}" stroke="var(--line)" stroke-width="1" opacity=".6"/>`});
 const Ht=y+2;
 for(let t=0;t<N;t++){const ft=rp.fault_ticks.includes(t),op=rp.opens_at===t;
  o+=`<rect class="tcol" data-t="${t}" x="${X(t)}" y="0" width="${cw}" height="${Ht}" fill="${ft?'color-mix(in srgb,var(--hot) 7%,transparent)':'transparent'}" style="cursor:pointer"/>`;
  o+=`<text x="${X(t)+cw/2}" y="15" font-size="11" text-anchor="middle" class="m">${T('tick','cycle')} ${t}</text>`;
  if(ft||op)o+=`<text x="${X(t)+cw/2}" y="31" font-size="10.5" text-anchor="middle" font-weight="600" fill="${ft&&!op?'var(--hot)':'var(--warn)'}">${fgoal&&op?T(ft?'⚡ faked “open”':'faked “open”',ft?'⚡ · boot_ok':'boot_ok = 1'):ft&&op?'⚡ · Accept':ft?'⚡ flip':'Accept'}</text>`;
  o+=`<line x1="${X(t)}" x2="${X(t)}" y1="38" y2="${Ht}" stroke="var(--line)" stroke-width="1"/>`}
 o+=`<line x1="0" x2="${Wd}" y1="38" y2="38" stroke="var(--line)"/><text x="10" y="15" font-size="10.5" class="d">signal</text><text x="${nameW+valW-10}" y="15" font-size="10.5" text-anchor="end" fill="var(--acc)">${T(rp.fault_ticks.includes(cur)?`value at the glitch (step ${cur})`:`value at step ${cur}`,`value at cycle ${cur}`)}</text>`;
 o+=`<rect x="${X(cur)+.5}" y="20" width="${cw-1}" height="${Ht-21}" fill="color-mix(in srgb,var(--acc) 7%,transparent)" stroke="var(--acc)" stroke-width="1" pointer-events="none" rx="2"/>`;
 box.innerHTML=`<svg class="wave" id="wsvg" tabindex="0" viewBox="0 0 ${Wd} ${Ht}" height="${Ht}" role="img" aria-label="${T('step by step view: use the left and right arrow keys to move the highlighted step','cycle by cycle view of the witness: left and right arrow keys move the cursor')}">${o}${body}</svg>`;
 const sv=$('#wsvg');sv.onclick=e=>{const bb=sv.getBoundingClientRect(),pt=(e.clientX-bb.left)*(Wd/bb.width);const t=Math.floor((pt-x0)/cw);if(t>=0&&t<N){S.cursor=t;drawWave();$('#wsvg').focus()}};
 sv.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();e.stopPropagation();S.cursor=Math.max(0,Math.min(N-1,cur+(e.key==='ArrowRight'?1:-1)));drawWave();$('#wsvg').focus()}};
 const gl=T(' States: Idle, then Armed (the key is being checked), then Accept (lock open) or Reject (lock shut); “garbled” means a pattern that is none of the four.','');
 let cap;if(rp.no_attack)cap=`No attack was found, so there is no attack to replay. Shown for orientation: an example wrong key with no flips${rp.clean_opens_at==null?' (it ends in Reject)':''}. Select the box above to add the right key, which reaches Accept at tick ${rp.honest_opens_at}.`;
 else if(!rp.verified)cap='<b style="color:var(--hot)">The replay did not reproduce the attack on this circuit file.</b> Treat this picture with caution.';
 else cap=`Solid lines: what the circuit does <b class="w">with the ${pl(r.min_faults,'flip')}</b> (⚡, at tick ${rp.fault_ticks.join(' and ')}). Dashed lines: the <b class="w">same wrong key without flips</b>. ${fgoal?T(`With the ${r.min_faults===1?'glitch':'glitches'} the “open” signal says yes at step ${rp.opens_at}${lockOpens?'':`, although the lock itself ${lockAt?'reads '+plainText(lockAt):'is garbled'} and never opens`}. The rest of the chip only looks at that signal, so it starts anyway. Without the ${r.min_faults===1?'glitch':'glitches'} the signal never says yes.`,`With the ${r.min_faults===1?'flip':'flips'} boot_ok reads 1 at tick ${rp.opens_at}${lockOpens?'':' while the state word never reads Accept'}; without them it never does.`):`With the ${r.min_faults===1?'flip':'flips'} the lock state reads Accept at tick ${rp.opens_at}; without them it never does.`} Click a tick: the highlighted column then shows every value at that tick. It starts on the ${T('glitch','first fault')}, so the first column of numbers shows what the ${T('glitch','fault')} changed.`;
 $('#wavecap').innerHTML=`<b class="w">How to read this.</b> ${cap}${gl}`;drawFoot()}

/* ---------------- circuit map */
const outLabel=n=>tech()?n.out.join(','):(n.out.includes('boot_ok')?'“open” signal':n.out.map(o=>'answer '+o.replace(/boot_word\[(\d)\]/,'signal $1')).join(','));
const mapW=m=>Math.ceil(Math.max(m.w,...m.nodes.filter(n=>n.kind==='gate'&&(n.out||n.fault)).map(n=>n.x+36+Math.max(n.out?outLabel(n).length*5.6+16:0,n.fault?62:0))));
function mapFit(){const box=$('#mapbox'),m=S.last&&S.last._map&&(S.last._map[S.mapMode]||S.last._map.full);if(!box||!m)return 1;return Math.min(1.35,Math.max(.4,(box.clientWidth-4)/mapW(m)))}
function gateShape(n){const x=n.x,y=n.y,col=n.fault?'var(--hot)':GC(n.group||'shared'),sw=n.fault?2.2:1.3;let s='';const st=`class="gate" style="stroke:${col};stroke-width:${sw}"`;
 if(n.type==='AND')s=`<path ${st} d="M${x},${y-12}h13a12,12 0 0 1 0,24h-13z"/><path class="wire${n.hot?' hot':''}" d="M${x+25},${y}H${x+34}"/>`;
 else if(n.type==='OR')s=`<path ${st} d="M${x-1},${y-12}q7,12 0,24q18,0 27,-12q-9,-12 -27,-12z"/><path class="wire${n.hot?' hot':''}" d="M${x+26},${y}H${x+34}"/>`;
 else if(n.type==='XOR')s=`<path ${st} d="M${x+3},${y-12}q7,12 0,24q16,0 24,-12q-8,-12 -24,-12z"/><path style="fill:none;stroke:${col};stroke-width:${sw}" d="M${x-2},${y-12}q7,12 0,24"/><path class="wire${n.hot?' hot':''}" d="M${x+27},${y}H${x+34}"/>`;
 else if(n.type==='NOT')s=`<path ${st} d="M${x},${y-9}L${x+19},${y}L${x},${y+9}z"/><circle ${st} cx="${x+22.5}" cy="${y}" r="3"/><path class="wire${n.hot?' hot':''}" d="M${x+25.5},${y}H${x+34}"/>`;
 else if(n.type==='MUX')s=`<path ${st} d="M${x},${y-14}L${x+18},${y-8}V${y+8}L${x},${y+14}z"/><path class="wire${n.hot?' hot':''}" d="M${x+18},${y}H${x+34}"/>`+(tech()?`<text x="${x+3}" y="${y-6}" font-size="7" class="m">0</text><text x="${x+3}" y="${y+3}" font-size="7" class="m">1</text><text x="${x+3}" y="${y+12}" font-size="7" class="m">s</text>`:'');
 (n.pins||[]).forEach(p=>{if(p.tag){const k=p.tag[0]==='k';s+=`<g data-tip="${esc(p.tagplain)}" data-tipm="${esc(p.tagtech)}"><rect x="${x-18}" y="${y+p.y-5}" width="15" height="10" rx="${k?5:1.5}" fill="var(--inset)" stroke="${k?'var(--mut)':'var(--warn)'}" stroke-width=".8"/><text x="${x-10.5}" y="${y+p.y+3}" font-size="7.5" text-anchor="middle" class="mono">${esc(p.tag)}</text><path class="wire" d="M${x-3},${y+p.y}H${x}"/></g>`}else if(p.const!=null){if(tech())s+=`<text x="${x-4}" y="${y+p.y+3}" font-size="8" text-anchor="end" class="m mono">${esc(p.const)}</text>`}else if(p.stub)s+=`<path class="wire" stroke-dasharray="2 2" d="M${x-9},${y+p.y}H${x}"/>`});
 if(n.fault)s+=`<g><circle cx="${x+14}" cy="${y-20}" r="8" fill="var(--panel)" stroke="var(--hot)" stroke-width="1.2"/><path d="M${x+15.3},${y-25.5}l-4.4,6.2h3l-1.2,4.4 4.6,-6.5h-3z" fill="var(--hot)"/><text x="${x+25}" y="${y-17}" font-size="9.5" fill="var(--hot)" font-weight="600">${T('tick ','@')}${n.fault.join(',')}</text></g>`;
 if(n.out)s+=`<text x="${x+36}" y="${n.fault?y+13:y-5}" font-size="9.5" fill="var(--warn)">→ ${esc(outLabel(n))}</text>`;
 return s}
const GATE={AND:'AND gate: output is 1 only when both inputs are 1',OR:'OR gate: output is 1 when at least one input is 1',XOR:'XOR gate: output is 1 when the two inputs differ',NOT:'NOT gate: output is the opposite of its input',MUX:'Selector: passes one of two inputs, chosen by a third'};
function drawMap(){const r=S.last,box=$('#mapbox');if(!box||!r||r.error||!r._map)return;const m=r._map[S.mapMode]||r._map.full;const z=S.zoom||mapFit();
 let o='';m.wires.forEach(w=>{o+=`<path class="wire${w.hot?' hot':w.cone?' cone':''}" data-net="${w.net}" d="M${w.pts.map(p=>p.join(',')).join('L')}"/>`});
 m.dots.forEach(d=>{o+=`<circle cx="${d[0]}" cy="${d[1]}" r="2" fill="${d[2]?'var(--hot)':'var(--mut)'}"/>`});
 m.nodes.forEach(n=>{const tip=n.kind==='gate'?`${GATE[n.type]||n.type}. ${n.fault?'FLIPPED in this attack at tick '+n.fault.join(', ')+'. ':''}${n.hot&&!n.fault?'The wrong value passes through here. ':''}Location: ${n.plain}.`:
   n.kind==='in'?`One bit of the key the attacker types in (${n.plain}).`:n.kind==='q'?`Memory: the lock's ${n.plain} as it is now.${n.fault?' FLIPPED at tick '+n.fault.join(', ')+'.':''}`:`Memory: what ${n.plain.replace('next ','')} will become at the next tick.`;
  let s;if(n.kind==='gate')s=gateShape(n);else{const col=n.fault?'var(--hot)':n.kind==='in'?'var(--mut)':'var(--warn)';const lab=tech()?n.tech:n.plain;
   s=`<rect class="gate" style="stroke:${col}${n.fault?';stroke-width:2.2':''}" x="${n.x}" y="${n.y-8}" width="${n.w}" height="16" rx="${n.kind==='in'?8:2}"/><text x="${n.x+n.w/2}" y="${n.y+3.5}" font-size="9" text-anchor="middle" class="${tech()?'mono':''}">${esc(lab.length>17?lab.slice(0,16)+'…':lab)}</text>`;
   if(n.fault)s+=`<path d="M${n.x+n.w/2+1.3},${n.y-21}l-4.4,6.2h3l-1.2,4.4 4.6,-6.5h-3z" fill="var(--hot)"/>`}
  o+=`<g class="node" data-net="${n.net}" data-tip="${esc(tip)}" data-tipm="${esc(n.tech)}">${s}</g>`});
 const MW=mapW(m);box.innerHTML=`<svg id="msvg" width="${MW*z}" height="${m.h*z}" viewBox="0 0 ${MW} ${m.h}" style="display:block;margin:0 auto" role="img" aria-label="${T('Map of the gates and wires this attack uses','Schematic of the fault cone')}">${o}</svg>`;
 const sv=$('#msvg');sv.onmouseover=e=>{const g=e.target.closest('.node');$$('#msvg .wire.hl').forEach(w=>w.classList.remove('hl'));if(g)$$(`#msvg path.wire[data-net="${g.dataset.net}"]`).forEach(w=>w.classList.add('hl'))};
 const nf=(r.faults||[]).length,hasC=/v1|v2/.test(r._fam);
 $('#mapcap').innerHTML=`<div class="legend" style="margin-bottom:5px">${nf?`<span><i style="background:var(--hot)"></i>${T('flipped wire, and where the wrong value travels in that tick','faulted net and its combinational fan-out')}</span>`:''}${hasC?(r._fam==='v1'?'':`<span><i class="sq" style="border:1.5px solid var(--c0)"></i>copy 1</span>`)+`<span><i class="sq" style="border:1.5px solid var(--c1)"></i>copy ${r._fam==='v1'?1:2}</span><span><i class="sq" style="border:1.5px solid var(--c2)"></i>copy ${r._fam==='v1'?2:3}</span>`:''}<span><i class="sq" style="border:1.5px solid var(--shared)"></i>${T(hasC?'logic outside the copies':'logic gates','other logic')}</span><span><i class="sq" style="border:1.5px solid var(--mut);border-radius:6px"></i>${T('k0…k7: the 8 parts of the key','k = sig[i]')}</span><span><i class="sq" style="border:1.5px solid var(--warn)"></i>${T('s0…s7: what the lock remembers now','s = st[i] (Q)')}</span></div>
  <b class="w">How to read this.</b> Signals flow left to right: ${T('the small round tags are the key coming in, the square tags are what the lock remembers right now',"the small tags are inputs (k = a key bit, s = a bit of the current lock state)")}, logic gates combine them, and the boxes on the right are what the lock state becomes at the next tick. ${m.focus?`Showing ${m.shown} of ${m.total} gates: those that feed the ${pl(nf,'flipped wire')} and those the wrong value passes through.${tech()?' Dashed stubs are inputs from gates not shown.':' Only the key parts and memory cells these gates use are drawn, so some of k0…k7 and s0…s7 are missing here.'}`:`Showing all ${m.total} gates and ${m.flops} memory bits.`} Hover a gate for a description.`}
function locate(net){if(!net)return;const g=$$('#msvg .node').find(x=>x.dataset.net===String(net));if(!g)return;g.scrollIntoView({behavior:'smooth',block:'center',inline:'center'});g.classList.remove('pulse');void g.getBBox();g.classList.add('pulse')}

/* ---------------- status bar: engine and mode information only */
function drawFoot(msg){const s=S.status||{},r=S.last&&!S.last.error?S.last:null;
 const run=Object.values(S.jobs).filter(j=>j.status==='running');
 const mode=S.offline?'<span class="led off"></span>disconnected':S.busy?'<span class="led busy"></span>'+esc(msg||'working'):s.live?'<span class="led live"></span>LIVE':'<span class="led"></span>RECORDED RESULTS';
 let h=`<span class="i" data-tip="${s.live?'The analysis engine is installed: results are computed on this computer.':'The solver (z3) is not installed here: results are read from the project’s saved files and labelled recorded.'}">${mode}${s.live||S.offline||S.busy?'':' · <button class="linkb" data-go="live">how to run live</button>'}</span>`;
 h+=`<span class="i" data-tip="GlitchSAT engine version, read from the project files">GlitchSAT <span class="mono">${esc(s.version||'?')}</span></span>`;
 h+=`<span class="i" data-tip="The solver that searches every combination exactly">z3 <span class="mono">${s.z3?esc(s.z3):'not installed'}</span></span>`;
 h+=`<span class="i" data-tip="Yosys turns a design into logic gates. Needed only for rebuilt designs and build studies.">Yosys <span class="mono">${s.yosys_short?esc(s.yosys_short):'not installed'}</span></span>`;
 if(run.length)h+=`<span class="i"><span class="led busy"></span>${run.map(j=>esc(j.title)+' '+j.done+'/'+j.total).join(' · ')}</span>`;
 if(r){h+=`<span class="i">${esc(r._code)} · ${esc(r._build==='stored'?T('first (saved) chip plan','stored netlist'):T('chip plan made again','yosys '+r._flow))}</span>`;
  if(r._prov.netlist_sha)h+=`<span class="i tech-only">sha256 <span class="mono">${r._prov.netlist_sha.slice(0,12)}…</span></span>`;
  h+=`<span class="i">${T('limit','bound')} <span class="mono">≤${r._k} flips · ${r._cycles} ticks</span></span>`;
  h+=`<span class="i">${r._stop?'<span style="color:var(--warn)">unknown</span>':r._src}</span>`;if(r._replay&&S.cursor!=null)h+=`<span class="i">cursor <span class="mono">tick ${S.cursor}</span></span>`}
 h+=`<span class="credit" data-tip="Worker processes for background studies">${s.workers?s.workers+(s.workers===1?' worker':' workers'):''}</span>`;
 if(!tech()){const pm=S.offline?'<span class="led off"></span>The Studio has stopped: start it again, then reload':S.busy?'<span class="led busy"></span>'+esc(msg||'working'):s.live?'<span class="led live"></span>Live: attacks are computed on this computer':'<span class="led"></span>Showing saved results; nothing is missing · <button class="linkb" data-go="live">how to run it live</button>';
  h=`<span class="i">${pm}</span>${run.length?`<span class="i"><span class="led busy"></span>${run.map(j=>esc(j.title)+': '+j.done+' of '+j.total).join(' · ')}</span>`:''}<span class="i">GlitchSAT <span class="mono">${esc(s.version||'?')}</span></span><span class="credit">Switch to <b>Technical</b> view (top right) for tool versions and file names</span>`}
 if(S.restarted&&!S.offline)h+=`<span class="i" style="color:var(--warn)">The Studio was restarted: <button class="linkb" id="f-reload">reload this window</button></span>`;
 $('#foot').innerHTML=h;const fr=$('#f-reload');if(fr)fr.onclick=()=>location.reload()}

/* ---------------- compare */
function addHist(r){const atk=r.verdict==='ATTACK_FOUND',pv=r._prov;const y=pv.yosys?pv.yosys.replace(/\s*\(git.*$/,'').replace(/^Yosys\s+/,''):'';
 const key=[r._design,r._flow,r._goal,r._k,r._cycles,r._src,pv.netlist_sha||''].join('|');S.hist=S.hist.filter(x=>x.key!==key);
 S.hist.push({key,code:r._code,name:r._name,stored:r._build==='stored',flow:r._flow,goal:r._goal,k:r._k,N:r._cycles,n:atk?r.min_faults:null,verdict:r._stop?'UNKNOWN':r.verdict,unk:r._stop?unkText(r):'',src:r._src,gates:r.netlist&&r.netlist.gates,sha:pv.netlist_sha?pv.netlist_sha.slice(0,8):'',yosys:y,standin:!!pv.nl_standin,at:new Date().toISOString().slice(0,19).replace('T',' ')});
 if(S.hist.length>60)S.hist.shift();if(S.keep)LS.set('gs_hist',S.hist);if(S.tab==='compare')drawCompare()}
function cmpChg(x,p){if(!p)return '<span style="color:var(--dim)">first row</span>';const c=[],fam=y=>(y.code||'').toLowerCase();
 if(fam(x)!==fam(p))c.push(({'v0>v1':'second copy added (shared wire)','v1>v2':'three copies, kept apart','v0>v2':'three copies, kept apart','v2>v2e':T('one pattern changed','Armed word re-encoded'),'v2e>v2':T('pattern changed back','original Armed word')})[fam(p)+'>'+fam(x)]||'another lock');
 if(x.stored!==p.stored)c.push(x.stored?T('first (saved) chip plan','stored netlist'):T('chip plan made again','re-synthesised'));else if(!x.stored&&x.flow!==p.flow)c.push(T(x.flow==='opt'?'tidied first':'as written','flow '+x.flow));
 if(x.goal!==p.goal)c.push(x.goal==='flag'?T('reads one signal','goal boot_ok'):T('reads the whole answer','goal boot_word'));if(x.k!==p.k)c.push(T(`up to ${x.k} glitches`,`k ≤ ${x.k}`));if(x.N!==p.N)c.push(T(`${x.N} steps`,`N = ${x.N}`));if(x.src!==p.src)c.push(x.src);
 return c.length?esc(c.join(', ')):'<span style="color:var(--dim)">same settings</span>'}
function drawCompare(){const el=$('#v-compare'),H=S.hist;
 const keepBox=`<label style="font-size:11.5px;color:var(--mut);display:flex;gap:5px;align-items:center" data-tip="Off: the table starts empty each time the Studio is opened. On: rows are kept on this computer."><input type="checkbox" id="h-keep" ${S.keep?'checked':''}> keep runs between sessions</label>`;
 if(!H.length){el.innerHTML=`<div class="empty"><b>No runs yet</b>Every analysis you run in this session is added here. Following the path (Start, then Try an attack) fills this table in six steps.<div style="display:flex;justify-content:center;margin-top:10px">${keepBox}</div></div>`}
 else{const mx=4,W=250,X=v=>18+v*(W-36)/mx;
 el.innerHTML=`${tech()?'':orient('Every attack you tried in this session, one row each.','A longer bar means more glitches were needed: a harder job for the thief. Compare the rows to see which design choices helped.','Try more attacks (the path, or “Change the experiment yourself” on the Try an attack page); each one is added here.')}<div class="panel"><div class="ph"><h4>${T('Runs side by side','Run comparison')}</h4><span class="sp"></span>${keepBox}<button class="btn" id="h-csv" data-tip="Save this table as a CSV file">Export CSV</button><button class="btn" id="h-clr" data-tip="Forget all runs listed here">Clear</button></div>
 <table><thead><tr><th>#</th><th>Design</th><th>${T('Chip plan','Netlist')}</th><th class="tech-only" data-tip="The Yosys version and the first characters of the circuit fingerprint: two rows with different builds are different circuits">Build</th><th>${T('Thief must fake','Goal')}</th><th>${T('Limits','Bound')}</th><th data-tip="What is different from the row above">${T('Changed from the row above','Changed vs previous row')}</th>
 <th style="width:${W}px">${T('Fewest flips found','Min faults')}<svg width="${W}" height="12" style="display:block">${[0,1,2,3,4].map(v=>`<text x="${X(v)}" y="10" font-size="9.5" text-anchor="middle" class="m">${v}</text>`).join('')}</svg></th><th>Source</th></tr></thead><tbody>
 ${H.map((x,i)=>{const c=FC(x.n);const bar=x.verdict==='ATTACK_FOUND'?`<line x1="${X(0)}" x2="${X(x.n)}" y1="9" y2="9" stroke="${c}" stroke-width="3"/><circle cx="${X(x.n)}" cy="9" r="6" fill="${c}"/><text x="${X(x.n)+12}" y="13" font-size="12" font-weight="700" fill="${c}">${x.n}</text>`:
   x.verdict==='NO_ATTACK_UP_TO_BOUND'?`<line x1="${X(0)}" x2="${X(x.k)}" y1="9" y2="9" stroke="${c}" stroke-width="1.5" stroke-dasharray="3 3"/><circle cx="${X(x.k)}" cy="9" r="5" fill="none" stroke="${c}" stroke-width="1.5"/><text x="${X(x.k)+11}" y="13" font-size="11" fill="${c}">none found ≤ ${x.k}</text>`:`<text x="${X(0)}" y="13" font-size="11" font-weight="600" fill="var(--warn)">? unknown: no conclusion</text>`;
  return `<tr ${x.unk?`data-tip="${esc(x.unk)}"`:''}><td>${i+1}</td><td><b>${esc(tech()?x.name:(FAMP[(x.code||'').toLowerCase()]||[x.name])[0])}</b></td><td>${x.stored?T('first (saved)','stored netlist'):T('made again, '+(x.flow==='opt'?'tidied first':'as written'),'rebuilt, flow '+x.flow)}</td>
  <td class="mono tech-only" style="font-size:11px">${x.yosys?'Yosys '+esc(x.yosys):'<span style="color:var(--dim)">Yosys n/a</span>'}<br><span style="color:var(--mut)">${x.gates?x.gates+' gates':''}${x.sha?' · '+x.sha+(x.standin?' (stand-in)':''):''}</span></td>
  <td>${x.goal==='flag'?T('1-bit flag','boot_ok == 1'):T('full 8-bit result','boot_word == 0x96')}</td>
  <td class="mono">≤${x.k} flips · ${x.N} ticks</td><td>${cmpChg(x,H[i-1])}</td><td><svg width="${W}" height="18" style="display:block">${[0,1,2,3,4].map(v=>`<line x1="${X(v)}" x2="${X(v)}" y1="0" y2="18" stroke="var(--line)"/>`).join('')}${bar}</svg></td><td><span class="chip ${x.src==='live'?'live':'rec'}">${x.src}</span></td></tr>`}).join('')}</tbody></table>
 <div class="cap"><b class="w">What this means.</b> More flips needed means a harder attack in this model. A dashed line ending in a hollow circle means "none found up to that many flips", which is a limit of the search and not a guarantee. "Unknown" rows are searches that did not finish and say nothing either way. Each row holds for its own ${T('chip plan','circuit (see the Build column)')} and limits only.</div></div>`;
 $('#h-clr').onclick=()=>{S.hist=[];LS.set('gs_hist',[]);drawCompare()};
 $('#h-csv').onclick=()=>download('glitchsat_runs.csv','design,netlist,flow,yosys,gates,netlist_sha256_8,goal,max_flips,ticks,verdict,min_flips,source,time\n'+H.map(x=>['"'+x.name+'"',x.stored?'stored':'rebuilt',x.flow,x.yosys,x.gates||'',x.sha,x.goal==='flag'?'boot_ok==1':'boot_word==0x96',x.k,x.N,x.verdict,x.n??'',x.src,x.at].join(',')).join('\n'),'text/csv')}
 $('#h-keep').onchange=e=>{S.keep=e.target.checked;LS.set('gs_keep',S.keep);LS.set('gs_hist',S.keep?S.hist:[])}}
function download(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:type||'application/json'}));a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},500)}
$('#b-export').onclick=()=>{const r=S.last;if(!r||r.error)return;const o=JSON.parse(JSON.stringify(r));delete o._map;delete o._log;const st=S.status||{};
 const out={exported_by:'GlitchSAT Studio',engine_version:st.version||null,studio_version:st.studio||null,author:'Kavin.K.K',project:'github.com/Kavin-Re/GlitchSAT-Redundancy',exported_at:new Date().toISOString(),source:r._src,request:S.lastQ,
  conclusion:r._stop?unkText(r):r.verdict,
  reading_note:'Bounded result of a modelled single-cycle bit-flip search on a toy netlist. Holds only for the stated flips, cycles, goal and netlist. No hardware was glitched. UNKNOWN means the search did not finish and nothing is concluded.',
  provenance:r._prov,ladder:S.ladder&&S.lastQ&&S.ladder.key===S.lastQ.run_id?S.ladder.res:null,result:o,run_log:r._log};
 download(`glitchsat_${r._design}_${r._goal}_k${r._k}_n${r._cycles}_${r._src}.json`,JSON.stringify(out,null,1));logLine('export',`result saved as JSON (${r._src})`,'p')};

/* ---------------- findings: recorded data + live studies */
async function loadFindings(force){const el=$('#v-findings');if(!S.find||force){if(!S.find)el.innerHTML='<div class="empty"><b>Reading the project files…</b></div>';try{S.find=await api.get('/api/findings')}catch(e){el.innerHTML='<div class="err"><b>The Studio has stopped</b><p>Start GlitchSAT Studio again, then reload this window.</p></div>';return}
  Object.values(S.find.studies||{}).forEach(s=>Object.assign(S.live,s.cached||{}))}
 if(S.tab==='findings')drawFindings();if(S.tab==='start')drawStart();if(S.tab==='about')drawAbout()}
async function startStudy(sid,params){let j;try{j=await api.post('/api/job',{study:sid,params:params||{}})}catch(e){return}
 if(j.error){logLine('study',j.error,'e');S.jobs[sid]={status:'error',error:j.error,title:sid,done:0,total:0};drawFindings();return}
 S.jobs[sid]={id:j.id,status:'running',done:0,total:0,title:(S.find.studies[sid]||{}).title||sid,counts:{}};logLine('study',`started: ${S.jobs[sid].title}`,'p');pollJobs()}
let pollT=null;
function pollJobs(){if(pollT)return;const step=async()=>{pollT=null;const run=Object.entries(S.jobs).filter(([k,j])=>j.status==='running'&&j.id);if(!run.length){drawFoot();return}
  for(const [sid,j0] of run){let j;try{j=await api.get('/api/job?id='+j0.id)}catch(e){continue}if(j.error)continue;Object.assign(S.live,j.results||{});delete j.results;S.jobs[sid]=j;
   if(j.status!=='running'){const c=j.counts||{};logLine('study',`${j.status==='done'?'finished':'cancelled'}: ${j.title}: ${j.done}/${j.total} cells in ${j.elapsed} s · ${c.match||0} match the record, ${c.mismatch||0} differ, ${c.state_unknown||0} unknown, ${c.state_error||0} failed${c.src_cached?', '+c.src_cached+' from the local cache':''}`,(c.mismatch||c.state_unknown||c.state_error)?'e':'p');
    if(S.runAll&&S.runAll.length){const nx=S.runAll.shift();startStudy(nx[0],nx[1])}}}
  if(S.tab==='findings'){const el=$('#v-findings'),sc=el.scrollTop;drawFindings();el.scrollTop=sc}drawFoot();if(S.ti===4&&S.last&&!S.last.error)drawStory(S.last);pollT=setTimeout(step,600)};pollT=setTimeout(step,250)}
function cancelStudy(sid){const j=S.jobs[sid];if(j&&j.id)api.post('/api/job/cancel',{id:j.id}).catch(()=>{});S.runAll=[]}
/* value of one cell: live if computed, else recorded. Returns {v, kind, rec, cmp, res} */
function cellOf(id,rec){const x=S.live[id];if(!x)return{v:rec,kind:'rec',rec};if(x.state==='ok')return{v:x.v,kind:x.src==='cached'?'cached':'live',rec,cmp:x.cmp,res:x,none:x.v==null,K:x.K};return{v:rec,kind:x.state,rec,res:x}}
function cellTip(c,what){const x=c.res;let s=what?what+'. ':'';if(c.kind==='rec')return s+(c.rec==null?'Not measured.':'Recorded value: '+c.rec+'. Not computed on this computer yet.');
 if(c.kind==='live'||c.kind==='cached')s+=`Computed ${c.kind==='cached'?'on this computer earlier (local cache'+(x.when?', '+x.when:'')+')':'live just now'+(x.secs!=null?' in '+x.secs+' s':'')}: ${c.none?'none found up to '+c.K:c.v}. `+(c.cmp==='match'?'Same as the recorded value.':c.cmp==='mismatch'?`DIFFERS from the recorded value (${c.rec}).`:x.rec_other?`Recorded ${c.rec} was ${x.rec_other.replace('recorded ','')}, so it is shown but not compared.`:'No recorded value for this exact build.');
 else if(c.kind==='unknown'||c.kind==='cancelled')s+=`UNKNOWN: the live search did not finish (${x.note||c.kind}); no conclusion.`+(c.rec!=null?` Recorded value: ${c.rec}.`:'');
 else if(c.kind==='unsupported')s+='Not analysed: this build contains gate types the engine does not model.';
 else if(c.kind==='skipped')s+=`Stays recorded: ${x.note}.`+(c.rec!=null?` Recorded value: ${c.rec}.`:'');
 else s+=`The live run failed (${x.note||''}).`+(c.rec!=null?` Recorded value: ${c.rec}.`:'');return s}
function numCell(id,rec,what,big){const c=cellOf(id,rec),lv=c.kind==='live'||c.kind==='cached',bad=c.kind==='unknown'||c.kind==='cancelled'||c.kind==='error';
 const shown=lv?(c.none?'>'+c.K:c.v):bad?'?':(c.rec==null?'–':c.rec),col=bad?'var(--warn)':lv&&c.none?'var(--none)':shown==='–'?'var(--line2)':`var(--f${Math.min(4,lv?c.v:c.rec)})`;
 const sub=lv?`${c.kind}${c.cmp==='match'?' <span class="m">✓</span>':c.cmp==='mismatch'?` <span class="x">≠ rec ${c.rec}</span>`:c.rec!=null?` · rec ${c.rec}`:''}`:bad?`unknown${c.rec!=null?' · rec '+c.rec:''}`:c.rec==null?'not measured':'recorded';
 return `<div class="cellnum${lv?' live':''}${lv&&c.none?' none':''}" style="--cc:${col}${big?';padding:14px 6px;font-size:34px':''}" data-tip="${esc(cellTip(c,what))}" data-tipm="${esc(c.res&&c.res.w?c.res.w.join(' ; '):'')}">${shown}<span class="lv">${sub}</span></div>`}
function tileCell(id,rec,what,style,label){const c=cellOf(id,rec),lv=c.kind==='live'||c.kind==='cached';let cls;
 if(lv)cls=(c.none?'tx':'t'+Math.min(4,c.v))+' live'+(c.cmp==='mismatch'?' diff':'');else if(c.kind==='unknown'||c.kind==='cancelled')cls='unk';else if(c.kind==='error')cls='errt';else if(c.kind==='unsupported'||rec==='unsupported')cls='tx';else cls=rec==null?'tx':'t'+Math.min(4,rec);
 const txt=label?(lv?(c.none?'–':c.v):(c.kind==='unknown'||c.kind==='error')?'?':(rec==null?'':rec)):'';
 return `<span class="tile ${cls}" style="${style||''}" data-tip="${esc(rec==='unsupported'&&c.kind==='rec'?(what?what+'. ':'')+'Recorded: not analysed, this build contains gate types the engine does not model.':cellTip(c,what))}">${txt}</span>`}
function studyBar(sid,extra){const st=(S.find.studies||{})[sid];if(!st)return '';const j=S.jobs[sid];
 if(!st.available)return `<div class="sb">${hon('recorded',null,true)}<span>Not computed live here: ${esc(st.reason)}. <button class="linkb" data-go="live">How to run it live</button></span></div>`;
 const c=j&&j.counts||{},n=Object.keys(S.live).filter(k=>k.startsWith(sid+'|')&&['ok'].includes(S.live[k].state)).length;
 if(j&&j.status==='running')return `<div class="sb">${hon('live',null,true)}<span>running</span><span class="bar"><i style="width:${j.total?100*j.done/j.total:0}%"></i></span><span><b>${j.done}</b> of ${j.total} cells · ${secs(j.elapsed)}${j.est_s?' of about '+secs(j.est_s):''}${c.mismatch?` · <b style="color:var(--hot)">${c.mismatch} differ</b>`:''}${c.src_cached?' · '+c.src_cached+' from cache':''}</span><button class="btn" data-cancel="${sid}">Cancel</button></div>`;
 const sum=j&&j.status&&j.status!=='error'?`<span>${j.status==='cancelled'?'Cancelled after':'Live:'} <b>${j.done}</b> of ${j.total} cells in ${secs(j.elapsed)} · <b>${c.match||0}</b> match the record${c.mismatch?`, <b style="color:var(--hot)">${c.mismatch} differ</b>`:''}${c.state_unknown||c.state_cancelled?`, <b style="color:var(--warn)">${(c.state_unknown||0)+(c.state_cancelled||0)} unknown</b>`:''}${c.state_error?`, ${c.state_error} failed`:''}${c.state_unsupported?`, ${c.state_unsupported} not supported`:''}${c.src_cached?` · ${c.src_cached} from the local cache`:''}</span>`
   :j&&j.error?`<span style="color:var(--hot)">${esc(j.error)}</span>`:n?`<span><b>${n}</b> cells computed on this computer earlier (local cache).</span>`:`<span>Showing recorded values. ${esc((st.info||{}).note||'')}</span>`;
 const btn=(p,lab,r)=>r&&r.cells?`<button class="btn" data-run="${sid}" data-params='${JSON.stringify(p)}' data-tip="Computes ${r.cells} cells on this computer with ${S.find.local.workers} worker process(es); recorded values stay visible next to the live ones. Estimate from recorded runtimes: about ${secs(r.est_s)}.${r.skipped?' '+r.skipped+' cells stay recorded.':''}">${lab} · ${r.cells} cells, ~${secs(r.est_s)}</button>`:'';
 return `<div class="sb">${sum}<span style="flex:1"></span>${btn({},j&&j.done?'Run again':'Run live',st.run)}${st.run_all?btn({all:true},extra||'Run all',st.run_all):''}</div>`}
const fcard=(cls,q,sid,body,cap,d)=>`<div class="panel ${cls}"><div class="ph"><h4 class="fq">${q}</h4><span class="sp"></span></div>${d.error?`<div class="note">This dataset could not be read from the project files (${esc(d.error)}).</div>`:`${sid?studyBar(sid):''}<div class="pb">${body()}</div><div class="cap"><b class="w">What this means.</b> ${cap()}</div><div class="fsrc tech-only">recorded source: ${esc(d.source)} · register: ${esc(d.register)}</div>`}</div>`;
const lg=()=>`<div class="legend" style="margin-top:8px"><span>fewest flips found:</span>${[0,1,2,3].map(i=>`<span><span class="tile t${i}" style="vertical-align:-3px;margin-right:4px"></span>${i}</span>`).join('')}<span><span class="tile t2 live" style="vertical-align:-3px;margin-right:5px"></span>computed on this computer</span><span><span class="tile t2 live diff" style="vertical-align:-3px;margin-right:5px"></span>differs from the record</span><span><span class="tile unk" style="vertical-align:-3px;margin-right:4px"></span>unknown</span><span><span class="tile tx" style="vertical-align:-3px;margin-right:4px"></span>not analysed</span></div>`;
const maskDots=m=>`<span class="maskd">${[7,6,5,4,3,2,1,0].map(i=>`<i class="${(m>>i)&1?'on':''}"></i>`).join('')}</span>`;
function studiesHead(F){const v=F.synth&&F.synth.designs&&F.synth.designs.v2;if(tech()||!v||!v.min)return '';
 return `<div class="panel"><div class="sentence">Same written design, ${v.solved} ways of turning it into a chip plan: <b>${v.min[1]} need only 1 glitch</b>, ${v.min[2]} need 2, and only ${v.min[3]} need 3.</div><div class="pb rowflex">${hon('recorded')}</div>
 <div class="cap"><b class="w">Why this matters.</b> This is the main result of the studies. The number of glitches belongs to one chip plan, not to the written design: a protection that is there on paper can be gone after the build tool has run, so the final chip plan is what has to be checked.</div></div>`}
function fwrap(c,extra){if(tech())return `<div class="fgrid">${c.join('')}${extra}</div>`;
 return `<div class="fgrid">${c[1]}</div><details class="more learn" id="f-more" ${S.fMore?'open':''}><summary>Six more studies, for engineers: changed assumptions, how a glitch is counted, which signals are read, one pattern changed, an independent check</summary><div class="fgrid" style="padding:10px">${c[0]}${c.slice(2).join('')}${extra}</div></details>`}
function drawFindings(){const F=S.find,el=$('#v-findings');if(!F)return;const L=F.local||{},stz=F.studies||{};
 const BL=(F.synth&&F.synth.builds)||{},AL={'default':'default gate set','noMUX':'no selector gates','AND_OR':'AND and OR only','fast':'fast mapping','dff':T('memory cells mapped too','with flip-flop mapping'),'noabc':'no gate mapping (ABC off)'};
 const synth=()=>{const d=F.synth,v=d.designs.v2,idx={};d.tiles.forEach(t=>idx[t.slice(0,6).join('|')]=t);
  const builds=['apt0.33','conda-eda0.38','conda-formal0.38'],flows=['plain','opt'],orders=['abc_then_flatten','flatten_then_abc'],merges=['nomerge','opt_merge'],abcs=['default','noMUX','AND_OR','fast','dff','noabc'],keeps=['keep_on','keep_off'];
  const localOnly=stz.synth&&stz.synth.available&&!L.e2_build;const rowsB=localOnly?['local'].concat(builds):builds;
  let g=`<div class="wall" style="grid-template-columns:auto repeat(24,15px);width:max-content"><div></div><div class="ch" style="grid-column:span 12;border-bottom:1px solid var(--line2)">${T('copies left as built','no opt_merge')}</div><div class="ch" style="grid-column:span 12;border-bottom:1px solid var(--hot);color:var(--txt)">${T('with a "merge identical logic" step','opt_merge after flatten')}</div><div></div>`;
  for(const m of merges)abcs.forEach((a,i)=>g+=`<div class="ch" style="grid-column:span 2;font-weight:600" data-tip="Gate-mapping option ${i+1}: ${AL[a]}. Left square: keep marks as written; right square: keep marks removed." data-tipm="abc: ${a}">${i+1}</div>`);
  for(const b of rowsB)for(const f of flows)for(const o of orders){const here=b==='local'||b===L.e2_build;
   g+=`<div class="rl" ${here?'style="color:var(--txt)"':`data-tip="Recorded only: these rows need ${esc(BL[b]||b)}, which is not the Yosys on this computer."`}>${b==='local'?'this computer, Yosys '+esc(L.yosys||''):esc((BL[b]||b).replace(/ \(.*$/,''))+(b==='conda-eda0.38'?' (a)':b==='conda-formal0.38'?' (b)':'')} · ${T(f==='plain'?'as written':'simplified first',f)} · ${T(o==='abc_then_flatten'?'copies mapped one by one':'copies mapped together',o==='abc_then_flatten'?'abc→flatten':'flatten→abc')}</div>`;
   for(const m of merges)for(const a of abcs)for(const k of keeps){const t=idx[[b,f,o,a,m,k].join('|')],rec=b==='local'?null:(t&&t[6]?t[8]:'unsupported'),what=`${t&&t[7]?t[7]+' gates, ':''}${AL[a]}`;
    g+=here?tileCell(['synth',f,o,a,m,k].join('|'),rec,what):`<span class="tile ${rec==='unsupported'?'tx':'t'+rec}" data-tip="${esc(what)}. Recorded: ${rec==='unsupported'?'not analysed (gate types the engine does not model)':'fewest flips '+rec}." data-tipm="${[b,f,o,a,m,k].join(' · ')}"></span>`}}
  g+='</div>';const bar=(x,lab)=>`<div style="display:grid;grid-template-columns:${T('112px','34px')} 1fr;gap:8px;align-items:center;margin-top:5px"><span style="font-size:11.5px;color:var(--mut)">${lab}</span><div class="sbar">${[1,2,3].map(i=>x.min[i]?`<div class="t${i}" style="flex:${x.min[i]}${i===3?';color:#fff':''}" data-tip="${x.min[i]} of ${x.solved} analysed settings need ${pl(i,'flip')} (recorded)">${x.min[i]}</div>`:'').join('')}</div></div>`;
  return `<div style="display:flex;gap:22px;flex-wrap:wrap;align-items:flex-start"><div>${g}<div style="font-size:10.5px;color:var(--mut);margin-top:6px;max-width:640px">Columns 1 to 6 = gate-mapping options: ${abcs.map((a,i)=>(i+1)+' '+AL[a]).join(' · ')}. (a) and (b) are two separate installs of the same Yosys 0.38+92.</div>${lg()}</div><div style="flex:1;min-width:250px"><div style="font-size:11px;color:var(--mut);margin-bottom:4px">${T('saved results, three versions of the build tool together','recorded, all three Yosys builds')}</div><div style="display:flex;gap:18px;margin-bottom:6px">${[1,2,3].map(i=>`<div><div class="big" style="color:var(--f${i})">${v.min[i]}</div><div style="font-size:11px;color:var(--mut)">settings need ${pl(i,'flip')}</div></div>`).join('')}</div>
   ${bar(v,T('three-copy lock','V2'))}${bar(d.designs.v1,T('two-check lock','V1'))}${bar(d.designs.v0,T('one-check lock','V0'))}
   <p style="font-size:11.5px;color:var(--mut);margin:10px 0 0">${v.solved} of ${v.rows} V2 settings were analysed; ${v.unsupported} produced gate types the engine does not model (hatched). They give ${d.distinct.n} distinct circuits. With the merge step on: ${d.merge_on[1]} / ${d.merge_on[2]} / ${d.merge_on[3]} settings need 1 / 2 / 3 flips. Largest circuit in the grid: ${d.gates_max} gates.</p></div></div>`};
 const scope=()=>{const d=F.scope,C=(g,i,n)=>d.cells.find(c=>c.goal===g&&c.inputs===i&&c.init===n);const cols=[[false,'known'],[false,'free_nongoal'],[false,'free'],[true,'known'],[true,'free_nongoal'],[true,'free']];
  const IL={known:T('starts Idle (as designed)','init known'),free_nongoal:T('starts in any state except Accept','init free, non-goal'),free:T('starts in any state','init free')};
  let g=`<div style="display:grid;grid-template-columns:auto repeat(6,1fr);gap:4px;align-items:center"><div></div><div style="grid-column:span 3;font-size:10.5px;color:var(--mut);text-align:center;border-bottom:1px solid var(--line2)">${T('a flip cannot hit the key wires','input nets not fault sites')}</div><div style="grid-column:span 3;font-size:10.5px;color:var(--mut);text-align:center;border-bottom:1px solid var(--line2)">${T('a flip can also hit the key wires','input nets are fault sites')}</div><div></div>`;
  cols.forEach(c=>g+=`<div style="font-size:10px;color:var(--mut);text-align:center;line-height:1.2">${IL[c[1]]}</div>`);
  for(const goal of ['boot_word','boot_ok']){g+=`<div style="font-size:11px;color:var(--mut);text-align:right;padding-right:6px">${goal==='boot_word'?T('must fake full<br>8-bit result','boot_word == 0x96'):T('must fake<br>1-bit flag','boot_ok == 1')}</div>`;
   cols.forEach(c=>{const x=C(goal,c[0],c[1]);g+=x?numCell(['scope',goal,c[0]?1:0,c[1]].join('|'),x.min,x.min===0?'Recorded: accepted with no flip, because some start state already reads Accept':'Recorded attack: '+x.faults.map(f=>f[0]+' at tick '+f[2]).join('; ')):'<div class="cellnum" style="--cc:var(--line2)">–</div>'})}
  return g+'</div>'};
 const count=()=>{const d=F.count,v=d.designs.v2,NAME=/^v2_(opt|plain)_(033|038)_s(\d)$/;
  const strip=(ix,rule,lab)=>{let h=`<div style="display:grid;grid-template-columns:150px 1fr;gap:8px;align-items:center;margin-bottom:6px"><span style="font-size:11.5px;color:var(--mut)">${lab}</span><div style="display:flex;gap:2px;flex-wrap:wrap">`;
   v.items.forEach(it=>{const m=it[0].match(NAME),st='width:17px;height:22px;font:600 10px var(--sans);color:#0c0f13;text-align:center;line-height:22px';
    h+=m&&m[2]===L.rep_ver?tileCell(['count',m[1],m[3],rule].join('|'),it[ix],`${it[1]} gates, Yosys ${m[2]==='033'?'0.33':'0.38+92'}, ${m[1]==='opt'?'simplified first':'as written'}, mapping option ${+m[3]+1}`,st,true):`<span class="tile t${it[ix]}" style="${st}" data-tip="${it[1]} gates: fewest flips ${it[ix]} (recorded${m?', Yosys '+(m[2]==='033'?'0.33':'0.38+92'):''})" data-tipm="${it[0]}">${it[ix]}</span>`});
   if(stz.count&&stz.count.available&&!L.rep_ver){h+='<span style="width:8px"></span>';for(const fl of ['opt','plain'])for(let i=0;i<8;i++)h+=tileCell(['count',fl,i,rule].join('|'),null,`this computer, Yosys ${L.yosys}, ${fl}, mapping option ${i+1}`,'width:17px;height:22px;font:600 10px var(--sans);color:#0c0f13;text-align:center;line-height:22px',true)}
   return h+'</div></div>'};
  return strip(2,'stem',T('one flipped wire = 1 flip','stem rule (unit cost)'))+strip(3,'fanout_pins',T('counted once per gate input it feeds','fan-out pins rule'))+`<div style="display:flex;gap:26px;margin-top:8px"><div><span class="big">${v.stem['3']||0}</span><span style="color:var(--mut)"> of ${v.n}</span><div style="font-size:11px;color:var(--mut)">need 3 flips under the first rule (recorded)</div></div><div><span class="big">${v.fanout['3']||0}</span><span style="color:var(--mut)"> of ${v.n}</span><div style="font-size:11px;color:var(--mut)">need 3 under the second rule (recorded)</div></div></div>`};
 const width=()=>{const d=F.width,mk={};d.masks.forEach(m=>mk[m[0]]=m);const SM=[1,3,7,15,31,63,127,255];
  const bars=d.stair.map((v,i)=>{const c=cellOf('width|'+SM[i],v),lv=c.kind==='live'||c.kind==='cached',val=lv?(c.none?null:c.v):v,bad=c.kind==='unknown'||c.kind==='error'||c.kind==='cancelled';
   return `<div style="text-align:center" data-tip="${esc(cellTip(c,'If only the lowest '+(i+1)+' result bit(s) are read'))}"><div style="height:66px;display:flex;align-items:flex-end;justify-content:center"><div class="${bad?'':'t'+Math.min(4,val??0)}" style="width:26px;height:${6+(val??0)*20}px;border-radius:2px 2px 0 0${lv?';box-shadow:0 0 0 1.5px var(--txt)':''}${c.cmp==='mismatch'?';box-shadow:0 0 0 2px var(--hot)':''}${bad?';border:1px dashed var(--warn)':''}"></div></div><div style="font-weight:700">${bad?'?':lv&&c.none?'>'+c.K:val}</div><div style="font-size:10px;color:var(--mut)">${i+1} bit${i?'s':''}</div><div class="lv">${lv?(c.cmp==='match'?'<span class="m">live ✓</span>':c.cmp==='mismatch'?`<span class="x">rec ${v}</span>`:'live'):bad?'unknown':'rec'}</div></div>`}).join('');
  let grid='<div style="display:grid;grid-template-columns:repeat(16,11px);gap:1px">';for(let i=0;i<256;i++){const m=mk[i];grid+=m?tileCell('width|'+i,m[1],m[2]?'This selection already reads as Accept in a normal state, so it needs 0 flips':'Reading these bits: '+[7,6,5,4,3,2,1,0].filter(b=>(i>>b)&1).join(', ')+' (touches '+m[3]+' of 3 copies)','width:11px;height:11px;border-radius:1px'):'<span style="width:11px;height:11px"></span>'}grid+='</div>';
  return `<div style="display:flex;gap:24px;flex-wrap:wrap"><div><div style="font-size:11px;color:var(--mut);margin-bottom:2px">${T('lowest n result bits read','consumer mask width n')}</div><div style="display:flex;gap:7px">${bars}</div></div>
  <div><div style="font-size:11px;color:var(--mut);margin-bottom:4px">${T('every possible selection of bits ('+d.total+')','all '+d.total+' consumer masks')}</div>${grid}</div>
  <div style="font-size:12px;color:var(--mut);min-width:150px"><div style="font-size:11px;margin-bottom:3px">recorded</div><div><b style="color:var(--f1)">${d.split[1]}</b> selections: 1 flip</div><div><b style="color:var(--f2)">${d.split[2]}</b> selections: 2 flips</div><div><b style="color:var(--f3)">${d.split[3]}</b> selections: 3 flips</div><div>${d.colliding} already read Accept (0)</div><div style="margin-top:6px">4-bit selections (${d.four.n}): ${d.four.split[1]} / ${d.four.split[2]} / ${d.four.split[3]}</div></div></div>`};
 const enc=()=>{const d=F.enc,ysl=[...new Set(d.sets.map(s=>s.yosys))];const mine=ysl.findIndex(y=>L.yosys&&y.startsWith('Yosys '+L.yosys+' '));const localOnly=stz.enc&&stz.enc.available&&mine<0;
  if(S.encSet==null)S.encSet=mine>=0?mine:0;const opts=ysl.map(y=>y.replace(/\s*\(git.*$/,'')).concat(localOnly?['this computer, Yosys '+L.yosys]:[]);const isLocal=S.encSet>=ysl.length,cur=ysl[Math.min(S.encSet,ysl.length-1)],sets=d.sets.filter(s=>s.yosys===(isLocal?ysl[0]:cur)),liveRow=isLocal||S.encSet===mine;
  const FL={plain:'as written',plain_opt_merge:'+ merge step',flatten_before_abc:'copies mapped together',abc_fast:'fast mapping',abc_no_mux:'no selector gates',opt_flow:'simplified first',plain_keep_off:'keep marks removed',opt_flow_keep_off:'simplified, keep marks removed'};
  let g=`<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><span style="font-size:11.5px;color:var(--mut)" data-tip="The same eight build styles were run with two Yosys versions">built with</span><div class="seg" id="encseg">${opts.map((y,i)=>`<button data-i="${i}" class="${i===S.encSet?'on':''}">${esc(y)}${i===mine?' (this computer)':''}</button>`).join('')}</div></div><div style="display:grid;grid-template-columns:auto repeat(8,1fr);gap:4px;align-items:center"><div></div>`;
  sets[0].flows.forEach(f=>g+=`<div style="font-size:10px;color:var(--mut);text-align:center;line-height:1.15" data-tip="Build style: ${esc(FL[f[0]]||f[0])}" data-tipm="${esc(f[0])}">${esc(FL[f[0]]||f[0])}</div>`);
  sets.forEach(s=>{g+=`<div style="font-size:11.5px;text-align:right;padding-right:6px"><b>${s.design==='v2'?'V2':'V2e'}</b><div style="font-size:10.5px;color:var(--mut)">${T('Armed code touches '+s.copies+' of 3 copies','Armed 0x'+s.armed+' · XOR 0x'+s.xor+' · '+s.copies+' copies')}</div></div>`;
   s.flows.forEach(f=>g+=liveRow?numCell(['enc',s.design,f[0]].join('|'),isLocal?null:f[2],isLocal?'':f[1]+' gates when recorded'):`<div class="cellnum" style="--cc:var(--f${f[2]})" data-tip="${f[1]} gates: fewest flips ${f[2]} (recorded; needs ${esc(cur.replace(/\s*\(git.*$/,''))}, not the Yosys on this computer)" data-tipm="${esc(f[0])}">${f[2]}<span class="lv">recorded</span></div>`)});
  return g+'</div>'};
 const DL={design:{v2:'V2',v1:'V1',v0:'V0'},build:{stored:['saved gate list','stored netlist'],plain:['rebuilt','rebuilt, plain'],merge:['rebuilt, copies merged','rebuilt, opt_merge'],v2e:['Armed code changed (V2e)','V2e (armed 0xA5)']},
  inputs:{no:['no','no'],yes:['yes','yes']},power:{known:['Idle, as designed','known'],nonopen:['anything except Accept','free, non-goal'],any:['anything','free']}};
 const DT={design:['Design','Design'],reader:['Result bits that are read','Consumer'],build:['Circuit version','Netlist'],inputs:['A flip can also hit the key wires','Input nets are fault sites'],power:['State when power comes on','Init state']};
 const dial=()=>{const d=F.dial,sel=S.dial,key=o=>d.order.map(k=>o[k]).join('|'),cell=d.cells[key(sel)],cid='dial|'+key(sel);
  const lab=(k,o)=>k==='reader'?(o.id==='word'?T('all 8','boot_word'):o.id==='flag'?T('1-bit flag','boot_ok'):(tech()?esc(o.mask):maskDots(parseInt(o.mask,16)))):esc(k==='design'?DL.design[o.id]:(DL[k][o.id]||[o.label,o.label])[tech()?1:0]);
  let rows=d.order.map(k=>`<div style="font-size:11.5px;color:var(--mut);text-align:right">${T(DT[k][0],DT[k][1])}</div><div class="seg dialseg" data-k="${k}" style="flex-wrap:wrap;justify-self:start">${d.controls[k].map(o=>{const kk=key({...sel,[k]:o.id}),m=d.cells[kk]||S.live['dial|'+kk];return `<button data-v="${o.id}" class="${sel[k]===o.id?'on':''}" style="${m?'':'opacity:.45'}" data-tip="${esc(k==='reader'&&o.mask?'Only the 4 filled bits of the 8-bit result are read (bit 7 on the left)':(o.sub||o.label))}${m?'':'. Faded: this combination was not measured in the study'}" data-tipm="${esc(o.mask||o.id)}">${lab(k,o)}</button>`}).join('')}</div>`).join('');
  const out=numCell(cid,cell?cell.v:null,cell&&cell.w.length?'Recorded attack: '+cell.w.map(w=>w[0]+' at'+(w[1].split(' @')[1]||'')).join('; '):'',true);
  return `<div style="display:grid;grid-template-columns:minmax(0,1.6fr) minmax(220px,1fr);gap:18px;align-items:center"><div style="display:grid;grid-template-columns:auto 1fr;gap:7px 10px;align-items:center">${rows}</div><div>${out}<div style="font-size:11.5px;color:var(--mut);margin-top:6px">${cell?'Fewest flips found'+(cell.b&&cell.b.kmax?`, limit ${cell.b.kmax} flips, ${cell.b.ticks} ticks.`:'.'):'The study did not run this combination.'}</div><div class="mono tech-only" style="color:var(--dim);margin-top:4px;word-break:break-all;font-size:11px">${cell?esc(cell.src)+(cell.yosys?' · '+esc(cell.yosys):''):''}</div></div></div>`};
 const valid=()=>F.valid.facts.map(f=>{const mm=f.text.match(/(\d[\d,]*) of ([\d,]+)/),c=S.live['valid|'+f.id],fmt=n=>Number(n).toLocaleString('en-US');
  const livetxt=c?(c.state==='ok'?`${hon('live',null,true)} <span class="${c.cmp==='mismatch'?'badc':c.cmp==='match'?'okc':'hint'}" style="font-size:12px" data-tip="${esc(c.src==='cached'?'Computed on this computer earlier (local cache'+(c.when?', '+c.when:'')+')':'Computed on this computer just now in '+c.secs+' s')}, by the project’s solver-free simulator">${c.src==='cached'?'computed here earlier':'just now'}: ${fmt(c.v[0])} of ${fmt(c.v[1])} ${c.cmp==='match'?'= recorded ✓':c.cmp==='mismatch'?'≠ recorded':''}</span>`:ntag(`live run: ${c.state==='unknown'||c.state==='cancelled'?'unknown, did not finish':'failed'}`,c.note||'')):'';
  return `<div class="fact"><div class="n">${esc(mm?mm[1]:f.n)}<small>${mm?' / '+mm[2]:''}</small></div><div>${esc(f.text)} ${hon('recorded',null,true)} ${livetxt}${!c&&(f.id==='replay'||f.id==='tot')?'<span style="font-size:11px;color:var(--dim)"> not part of the live run</span>':''}${f.confirmed?'':' '+ntag('not confirmed in file','This sentence was not found word for word in the source file; check the file.')}<div class="mono tech-only" style="color:var(--dim)">“${esc(f.quote)}”</div></div></div>`}).join('');
 const av=Object.entries(stz).filter(([k,s])=>s.available&&s.run&&s.run.cells),tot=av.reduce((a,[k,s])=>a+s.run.est_s,0),anyRun=Object.values(S.jobs).some(j=>j.status==='running');
 const extra=VIEWS.filter(v=>v.card).map(v=>{try{return `<div class="panel ${v.wide?'wide':''}"><div class="ph"><h4 class="fq">${esc(v.title)}</h4></div>${v.study?studyBar(v.study):''}<div class="pb">${v.render(F,S.live)}</div></div>`}catch(e){return ''}}).join('');
 el.innerHTML=`${tech()?'':orient('The project’s bigger experiments: the same question asked under many different settings, for example many ways of building the same lock.','Each coloured square or number is the fewest glitches for one setting. The same design can need 1, 2 or 3 depending on how it was built and what is assumed.','Hover any square for its meaning. Where a card has a <b>Run live</b> button, this computer can redo it; elsewhere the saved results are shown.')}${studiesHead(F)}<div class="banner"><span style="flex:1">Every card first shows the <b style="color:var(--txt)">recorded</b> results of the full study, read from the project files. <b style="color:var(--txt)">Run live</b> computes the same cells on this computer and puts each live value next to its recorded one, marked ✓ if equal and ≠ if not. All of it concerns modelled one-tick flips on toy circuits (under 100 gates in their baseline builds).</span>
  ${av.length?(anyRun?'<button class="btn" id="f-stop">Cancel all</button>':`<button class="btn" id="f-all" data-tip="Runs every study that this computer can compute, one after another, in the background. Estimate from recorded runtimes with ${L.workers} worker process(es).">Run all studies · ~${secs(tot)}</button>`):''}<button class="btn" id="f-clear" data-tip="Forget every live value kept in the local cache${tech()?' ('+esc((S.status||{}).cache_dir||'')+')':''}; recorded values are not affected">Clear local cache</button></div>
 ${fwrap([fcard('wide','Turn the assumptions yourself','dial',dial,()=>`Pick a setting and read the fewest flips for it. Faded choices lead to combinations the study did not measure (${F.dial.measured} of ${F.dial.total} were). For V2 the count goes from 3 down to 0 as the assumptions are relaxed, one at a time.`,F.dial),
 fcard('wide',`Same design, ${F.synth.designs?F.synth.designs.v2.rows:''} build settings (${F.synth.designs?F.synth.designs.v2.solved:''} analysed, ${F.synth.distinct?F.synth.distinct.n:''} distinct circuits): does the count survive rebuilding?`,'synth',synth,()=>'Each square is V2 turned into gates with one particular setting of the build tool (Yosys version and options). Several settings produce the same circuit: there are '+F.synth.distinct.n+' distinct circuits, of which '+F.synth.distinct.min[1]+' / '+F.synth.distinct.min[2]+' / '+F.synth.distinct.min[3]+' need 1 / 2 / 3 flips. The design text is identical in all of them, yet the fewest flips needed is 1 for most and 3 for only a minority. When the build tool merges identical logic, the three copies collapse and the count is never 3. Earlier published work (SYNFI, a tool that injects faults into synthesised circuits) already showed that synthesis can remove such redundancy; this is a measurement on this toy design, not a new effect. Run live rebuilds the rows that match the Yosys on this computer.',F.synth),
 fcard('','What if the assumptions change?','scope',scope,()=>'The "3" of V2 holds for one setting only: the attacker must fake the full result, a flip cannot hit the key wires, and the lock starts in its normal Idle state. Change any one of these and the count is 1 or 0. Limits: saved V2 gate list, 6 ticks, up to 3 flips.',F.scope),
 fcard('','Does it matter how a flip is counted?','count',count,()=>'Rebuilt versions of V2, counted two ways. If a flipped wire counts as one flip no matter how many gates read it, only a few builds need 3. If it is counted once per gate input it feeds, all of them do. Neither rule has been shown to match a physical glitch; this only shows how much the number depends on the rule.',F.count),
 fcard('','How many result bits does the reader check?','width',width,()=>'The fewer result bits the rest of the chip actually reads, the fewer flips are needed. Reading all 8 gives 3; reading only some of them gives 2, 1 or even 0. Measured on the saved V2 gate list.',F.width),
 fcard('','Changing one constant: the re-encoding experiment','enc',enc,()=>'V2e differs from V2 in one constant, the Armed code (0xCC became 0xA5), so that reaching Accept needs changes owned by all three copies instead of two. On most build styles the count rises from 2 to 3. On the two build styles that merge the copies it stays at 1 for both: re-encoding does not help there.',F.enc),
 fcard('wide','Was the solver checked by an independent method?','valid',valid,()=>'A separate, simple gate simulator (no solver) tried flips exhaustively and compared with the solver’s answers. Run live repeats these counts on this computer; it needs no solver, only time. '+esc(F.valid.limits||''),F.valid)],extra)}
 ${F.pages&&F.pages.length?`<div class="banner"><span>Stand-alone explainer pages from the project (they open in their own style, and show recorded data only):</span>${F.pages.map(p=>`<a class="btn" href="/pages/${esc(p.file)}" target="_blank" rel="noopener">${esc(p.title)}</a>`).join('')}</div>`:''}`;
 $$('.dialseg').forEach(sg=>sg.onclick=e=>{const b=e.target.closest('button');if(b){S.dial[sg.dataset.k]=b.dataset.v;const sc=el.scrollTop;drawFindings();el.scrollTop=sc}});
 const fm=$('#f-more');if(fm)fm.ontoggle=()=>{S.fMore=fm.open};
 const es=$('#encseg');if(es)es.onclick=e=>{const b=e.target.closest('button');if(b){S.encSet=+b.dataset.i;const sc=el.scrollTop;drawFindings();el.scrollTop=sc}};
 $$('[data-run]').forEach(b=>b.onclick=()=>{b.disabled=true;startStudy(b.dataset.run,JSON.parse(b.dataset.params||'{}'))});$$('[data-cancel]').forEach(b=>b.onclick=()=>cancelStudy(b.dataset.cancel));
 if($('#f-all'))$('#f-all').onclick=()=>{S.runAll=av.map(([k])=>[k,{}]);const nx=S.runAll.shift();startStudy(nx[0],nx[1])};
 if($('#f-stop'))$('#f-stop').onclick=()=>{S.runAll=[];Object.keys(S.jobs).forEach(cancelStudy)};
 $('#f-clear').onclick=async()=>{await api.post('/api/cache/clear',{}).catch(()=>{});Object.keys(S.live).forEach(k=>delete S.live[k]);S.jobs={};logLine('cache','local cache cleared','p');loadFindings(true)}}

/* ---------------- about */
function drawAbout(){const s=S.status||{};$('#v-about').innerHTML=`<div class="about" style="max-width:980px;margin:0 auto">${foundHTML()}<div class="panel"><div class="ph"><h4>What this tool does</h4></div><div class="pb">
 <p>A chip checks a ${term('key')} before it starts. An attacker can disturb the chip for an instant (a glitch) to make it accept a wrong key. GlitchSAT takes a small key-check ${term('circuit')}, imagines that any ${term('wire')} or ${term('memory bit')} may give the wrong answer for one clock ${term('tick')}, and asks a ${term('solver')} for the <b>fewest such ${term('flip','flips')}</b> that make the lock accept a wrong key. It shows that attack tick by tick, or reports that none was found inside the stated ${term('limit','limits')}.</p>
 <p>The four example locks are the ${term('V0')}, the ${term('V1')}, the ${term('V2')} and the ${term('V2e')}. A lock moves through the states ${term('Idle')}, ${term('Armed')}, then ${term('Accept')} or ${term('Reject')}.</p>
 <p class="tech-only">Method: the netlist (Yosys JSON) is unrolled for N cycles, a fault variable is placed on every gate output and flop Q in every cycle, an at-most-k constraint bounds the faults, and z3 is asked for a model in which a non-key input reaches the goal value; the count is then minimised.</p></div></div>
 <div class="panel"><div class="ph"><h4>Limits: what a result does and does not say</h4></div><div class="pb"><ul>
 <li>Glitches are <b>modelled</b> as one-tick flips of a gate output or a memory bit. No hardware was glitched, and real glitches may behave differently.</li>
 <li>Every result is <b>bounded</b> by a number of flips and ticks. "No attack found within the limits" does not mean the design is safe.</li>
 <li><b>Proved</b> results cover any waiting time, and nothing else: ${esc(PROVED_ASSUME)}</li>
 <li>A search that is stopped (time limit or Stop) is <b>unknown</b>. It is never shown or counted as "no attack".</li>
 <li>A result belongs to <b>one circuit file</b>. Making it again from the same written design can change it (see Studies).</li>
 <li>The example locks are <b>toy</b> 8-bit key checks. Their baseline circuits have under 100 gates (18 to 89); some rebuilt variants in the study are larger. The real-chip page uses a few blocks of one open-source chip.</li>
 <li class="tech-only">Nothing here is claimed as new. Solver-based fault analysis exists, and SYNFI (arXiv 2205.04775) showed earlier that synthesis can optimise redundancy away.</li>
 <li>The tick-by-tick view is a <b>replay</b> of the result by a small simulator inside this app; the circuit map is drawn automatically and is not a chip layout.</li></ul></div></div>
 <div class="panel"><div class="ph"><h4>The six labels</h4></div><div class="pb"><p style="margin-top:0">Everything here is computed; nothing is measured on a chip. Every result carries one of six labels: recorded and live say <i>when</i> it was computed; simulated, bounded, proved and estimate say <i>how</i>.</p><ul>
 <li>${hon('live')}.<span class="tech-only"> Each analysis runs in its own process, without a solver timeout, and is stopped from outside at the time limit, so a finished run is exact.</span></li>
 <li>${hon('recorded')}. A recorded value stays on screen next to a live one; a live value never replaces a record silently.</li>
 <li>${hon('simulated')}. For example clock timing, a laser spot of a given size, or a program on a simulated processor.</li>
 <li>${hon('bounded')}. Used for the whole chips on “Explore a real chip”: the exact smallest number within the stated number of clock steps, not for longer runs.</li>
 <li>${hon('proved')}. It also assumes a wrong key that is held steady. It is not a claim about a real chip.</li>
 <li>${hon('estimate')}. Worked out from published scoring tables and stated assumptions.</li></ul>
 <p>Everything else is said in a plain sentence: “no result yet” (nothing is guessed), “computed on this computer earlier” (kept in a local cache<span class="tech-only keep">, ${esc(s.cache_dir||'')}, under the circuit fingerprint, the engine and solver versions and the settings</span>), and “unknown” (a search that was stopped).</p></div></div>
 ${Studio.aboutExtra?Studio.aboutExtra():''}
 <div class="panel" id="about-live"><div class="ph"><h4>Run it live on this computer</h4></div><div class="pb">${howLive()}</div></div>
 <div class="panel plain-only"><div class="ph"><h4>This installation</h4></div><div class="pb">GlitchSAT ${esc(s.version||'?')} · ${s.live?'attacks are computed live on this computer':'shows saved results (nothing is missing; see “Run it live” above)'} · runs only on this computer, with no network access. Switch to Technical view for tool versions and folders.</div></div>
 <div class="panel tech-only"><div class="ph"><h4>This installation</h4></div><div class="pb mono keep" style="line-height:1.7">GlitchSAT ${esc(s.version||'?')} · Studio interface ${esc(s.studio||'')}<br>engine: ${esc(s.engine||'')} ${s.live?'· z3 '+esc(s.z3):'· z3 not installed: showing recorded results'}<br>Yosys: ${esc(s.yosys||'not installed')}<br>Python ${esc(s.python||'')} · ${s.workers||1} worker process(es) for studies<br>project folder: ${esc(s.root||'')}<br>${s.browser?'window: '+esc(s.browser)+'<br>':''}add-ons loaded: “Why protect chips?”${(s.plugins||[]).map(p=>', “'+esc(p)+'”').join('')}${(s.plugin_notes||[]).map(n=>'<br>'+esc(n)).join('')}<br>runs only on this computer (127.0.0.1), no network access</div></div>
 <div class="panel"><div class="ph"><h4>Author</h4></div><div class="pb"><p style="margin:0">Kavin.K.K · <span class="mono keep">github.com/Kavin-Re/GlitchSAT-Redundancy</span><br>${T('Built on free tools: a checking program and a chip build tool.','Built on z3 (solver) and Yosys (synthesis).')}</p></div></div></div>`}

/* ---------------- help / walkthrough */
function openHelp(tab,ci){if(!tab||tab==='tour'){openStory(0);return}S.help={tab:tab,ci:ci||0,opener:(S.help&&S.help.opener)||document.activeElement};drawHelp()}
function closeHelp(){const o=S.help&&S.help.opener;S.help=null;$('#modal').innerHTML='';LS.set('gs_seen',1);if(o&&document.contains(o)&&o!==document.body)o.focus()}
function drawHelp(){const hs=S.help;if(!hs)return;let body='',foot='';
 if(hs.tab==='gloss'){const src=tech()?GLOSS:PG,keys=Object.keys(src);
  body=`<p class="hint" style="margin-top:0">Words used in this app. Dotted underlined words show the same explanation when you point at them.</p><dl class="gl keep">${keys.map(k=>`<dt>${esc(k)}</dt><dd>${esc(src[k])}</dd>`).join('')}</dl>`;foot='<span style="flex:1"></span>'}
 else{body=`<div class="kb">${[['Enter','run with the current settings, when “Change the experiment yourself” is open (Ctrl+Enter works from anywhere)'],['Esc','stop a running search; close this window'],['← →','previous / next step of the path; in the story, previous / next card; in the lesson “Why protect chips?”, previous / next screen; move the step cursor when the step-by-step view is selected'],['V','switch Plain / Technical view'],['S','the story (How it works)'],['1 … '+VIEWS.filter(v=>!v.card).length,VIEWS.filter(v=>!v.card).map(v=>v.title).join(', ')+' (the number is also shown when you point at a tab)'],['F','what we found, in one minute'],['L','how to run it live on this computer'],['Tab','move between buttons; Enter or Space presses them'],['`','open or close the run log (Technical view)'],['T','dark / light theme'],['?','this help']].map(k=>`<div><kbd>${k[0]}</kbd></div><div style="color:var(--mut)">${k[1]}</div>`).join('')}</div>`;foot='<span style="flex:1"></span>'}
 $('#modal').innerHTML=`<div class="modal" id="mbg"><div class="dlg" role="dialog" aria-modal="true" aria-label="Help"><div class="dh">${[['gloss','Glossary'],['keys','Keyboard keys']].map(t=>`<button class="tab${hs.tab===t[0]?' on':''}" data-t="${t[0]}">${t[1]}</button>`).join('')}<span style="flex:1"></span><button class="btn ico" id="hx" aria-label="close">✕</button></div><div class="db">${body}</div><div class="df">${foot}<button class="btn" id="hclose">Close</button></div></div></div>`;
 $$('#modal .dh .tab').forEach(b=>b.onclick=()=>{hs.tab=b.dataset.t;drawHelp()});$('#hx').onclick=$('#hclose').onclick=closeHelp;$('#mbg').onclick=e=>{if(e.target.id==='mbg')closeHelp()};
 if($('#hb'))$('#hb').onclick=()=>{hs.ci--;drawHelp()};if($('#hn'))$('#hn').onclick=()=>{hs.ci++;drawHelp()};
 const f=$('#hn')||$('#hstart')||$('#hclose');f&&f.focus()}
$('#b-help').onclick=()=>openHelp('gloss');

/* ---------------- built-in views */
/* ================= 3.0: plain words, story, start page, path, Explore views ================= */
/* ---- plain words: in Plain view the same numbers are shown with everyday words (text only; Technical view is untouched) */
const capAt=(off,str,w)=>(off===0||/[.:!?]\s+$/.test(str.slice(0,off)))?w[0].toUpperCase()+w.slice(1):w;
const PW=[[/\b(?:[Tt]he )?V2e\b/g,(m,off,str)=>capAt(off,str,'the three-copy lock with one pattern changed')],[/\b(?:[Tt]he )?V2\b/g,(m,off,str)=>capAt(off,str,'the three-copy lock')],[/\b(?:[Tt]he )?V1\b/g,(m,off,str)=>capAt(off,str,'the two-check lock')],[/\b(?:[Tt]he )?V0\b/g,(m,off,str)=>capAt(off,str,'the one-check lock')],
 [/\bthe 1-bit accept flag\b/g,'the "open" signal'],[/\bthe 1-bit flag\b/g,'the single "open" signal'],[/\baccept flag\b/g,'"open" signal'],[/\bthe flag itself\b/g,'the "open" signal itself'],[/\bthe flag wire\b/g,'the "open" signal'],
 [/\bnext state bit\b/g,'next memory'],[/\block-state bit\b/g,'lock memory cell'],[/\bstate bit\b/g,'memory'],[/\bconsumer\b/g,'the rest of the chip'],[/\bArmed code\b/g,'pattern for Checking'],
 [/\bFlipped\b/g,'Glitched'],[/\bflipped\b/g,'glitched'],[/\bFlipping\b/g,'Glitching'],[/\bflipping\b/g,'glitching'],[/\bFlips\b/g,'Glitches'],[/\bflips\b/g,'glitches'],[/\bFlip\b/g,'Glitch'],[/\bflip\b/g,'glitch'],
 [/\btick by tick\b/g,'step by step'],[/\bTicks\b/g,'Steps'],[/\bticks\b/g,'steps'],[/\bTick\b/g,'Step'],[/\btick\b/g,'step'],[/\bresult bits\b/g,'answer signals'],[/\bresult bit\b/g,'answer signal'],[/\bResult bits\b/g,'Answer signals'],
 [/\bmemory bits\b/g,'memory cells'],[/\bmemory bit\b/g,'memory cell'],[/\b8-bit result\b/g,'8-signal answer'],[/\bfull 8-bit\b/g,'full 8-signal'],[/\b1-bit flag\b/g,'single "open" signal'],[/\bsaved gate list\b/g,'saved chip plan'],[/\bSaved gate list\b/g,'Saved chip plan'],
 [/\s*\([^()]*0x[0-9A-Fa-f]+[^()]*\)/g,''],[/\b0x[0-9A-Fa-f]+\b/g,'a set value'],[/\b(chip )?build tool,? Yosys\b/g,(m,c)=>(c||'')+'build tool'],[/\bbuild tool \(Yosys\)/g,'build tool'],[/\bthe cell netlists?\b/g,'the list of factory cells'],[/\bcell netlists?\b/g,'list of factory cells'],[/\bthe Yosys\b/g,'the build tool'],[/\ba Yosys\b/g,'a build tool'],[/\bYosys (\d[\w.+]*)/g,'build tool $1'],[/\bYosys\b/g,'the build tool'],[/\s*\(z3\)/g,''],[/\bz3\b/g,'the checking program'],
 [/\bnetlists\b/g,'chip plans'],[/\bnetlist\b/g,'chip plan'],[/\bNetlist\b/g,'Chip plan'],[/\bsynthesis\b/g,'the build tool'],[/\bSynthesis\b/g,'The build tool'],[/\bsynthesised\b/g,'built'],[/\bre-synthesis\b/g,'rebuilding'],
 [/\bflops\b/g,'memory cells'],[/\bflop\b/g,'memory cell'],[/\bfaults\b/g,'glitches'],[/\bfault\b/g,'glitch'],[/\bFaults\b/g,'Glitches'],[/\bFault\b/g,'Glitch'],[/\bcomparators\b/g,'checks'],[/\bcomparator\b/g,'check'],
 [/\bd_single\b/g,'the one-check version'],[/\bd_dup\b/g,'the two-check version'],[/\bd_trip\b/g,'the three-copy version'],[/\bd_compl\b/g,'the true-and-inverted version'],[/\bh_single\b/g,'the one-check version with fingerprint'],[/\bh_trip\b/g,'the three-copy version with fingerprint'],
 [/\bthe 1-bit accept flag\b/g,'the "open" signal'],[/\bThe single accept bit\b/g,'The "open" signal'],[/\bthe single accept bit\b/g,'the "open" signal'],[/\baccept bit\b/g,'"open" signal'],[/\bthat bit is all\b/g,'that signal is all'],
 [/\bkey bits\b/g,'parts of the key'],[/\bthe PC\b/g,'the next-instruction address'],[/\bIbex fetch stage\b/g,'Processor (Ibex) instruction fetch'],[/\bkey bit\b/g,'part of the key'],
 [/\bAccept\b/g,'Open'],[/\bReject\b/g,'Shut'],[/\bArmed\b/g,'Checking'],[/\bIdle\b/g,'Waiting'],[/\bcircuit file\b/g,'chip plan'],[/\bcircuit fingerprint\b/g,'plan fingerprint']];
const PROT=[/\bflip-flops?\b/gi,/\bbit flips?\b/gi];
const plainText=t=>{const keep=[];for(const rx of PROT)t=t.replace(rx,m=>{keep.push(m);return '\u0001'+(keep.length-1)+'\u0002'});for(const [a,b] of PW)t=t.replace(a,b);return t.replace(/\u0001(\d+)\u0002/g,(_,i)=>keep[+i])};
/* Technical view: one word for a clock step (cycle) and one for a modelled glitch (fault); "bit flip" and "flip-flop" stay */
const TW=[[/\btick by tick\b/g,'cycle by cycle'],[/\bTicks\b/g,'Cycles'],[/\bticks\b/g,'cycles'],[/\bTick\b/g,'Cycle'],[/\btick\b/g,'cycle'],[/\bFLIPPED\b/g,'FAULTED'],[/\bFlipped\b/g,'Faulted'],[/\bflipped\b/g,'faulted'],[/\bFlipping\b/g,'Faulting'],[/\bflipping\b/g,'faulting'],[/\bFlips\b/g,'Faults'],[/\bflips\b/g,'faults'],[/\bFlip\b/g,'Fault'],[/\bflip\b/g,'fault']];
const techText=t=>{const keep=[];for(const rx of PROT)t=t.replace(rx,m=>{keep.push(m);return '\u0001'+(keep.length-1)+'\u0002'});for(const [a,b] of TW)t=t.replace(a,b);return t.replace(/\u0001(\d+)\u0002/g,(_,i)=>keep[+i])};
function techify(root){if(!tech()||!root)return;const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{const p=n.parentElement;if(PDONE.has(n)||!p||p.closest('.keep,script,style,textarea,code,pre,iframe,.logbody,.fsrc,details.more .kv,select,input'))return NodeFilter.FILTER_REJECT;return NodeFilter.FILTER_ACCEPT}});
 const nodes=[];while(w.nextNode())nodes.push(w.currentNode);nodes.forEach(n=>{const o=n.nodeValue,t=techText(o);PDONE.add(n);if(t!==o)n.nodeValue=t})}
/* glossary words: only the first one of each kind in a card is a keyboard stop */
function tabTerms(root){if(!root)return;const seen=new Map();root.querySelectorAll('.term:not(.auto)').forEach(s=>{const host=s.closest('.view,.dlg,aside')||root,k=s.textContent.trim().toLowerCase().replace(/s$/,'');let set=seen.get(host);if(!set){set=new Set();seen.set(host,set)}
  if(set.has(k)){if(s.hasAttribute('tabindex'))s.removeAttribute('tabindex')}else{set.add(k);if(s.getAttribute('tabindex')!=='0')s.setAttribute('tabindex','0')}})}
const PDONE=new WeakSet();
const AUTO_TERMS=[['Verilog','Verilog'],['cell library','cell library'],['build tool','build tool'],['chip plans','chip plan'],['chip plan','chip plan'],['answer signals','answer signal'],['answer signal','answer signal'],['written design','written design'],['garbled','garbled'],['checking program','checking program'],['fingerprint','fingerprint'],['gates','gate'],['gate','gate'],['solver','checking program'],['wires','wire'],['wire','wire'],['memory cells','memory cell'],['memory cell','memory cell'],['µm','µm'],['firmware','firmware'],['instruction','instruction']];
const TERM_RX=new RegExp('\\b('+AUTO_TERMS.map(t=>t[0].replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')\\b');
function plainify(root){if(tech()||!root)return;const seen=new Set(),todo=[];
 const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{const p=n.parentElement;if(PDONE.has(n)||!p||p.closest('.tech-only,.keep,script,style,textarea,code,pre,.term,iframe'))return NodeFilter.FILTER_REJECT;return NodeFilter.FILTER_ACCEPT}});
 const nodes=[];while(w.nextNode())nodes.push(w.currentNode);
 nodes.forEach(n=>{const o=n.nodeValue,t=plainText(o);PDONE.add(n);if(t!==o)n.nodeValue=t;
  const p=n.parentElement;if(p.closest('svg,button,label,th,.seg,.nav,.xnav,h1,h2,h3,h4,.chip,.vnum,.ladder,.mono,option'))return;const host=p.closest('.panel,.home,.card,.orient')||root;
  const m=n.nodeValue.match(TERM_RX);if(!m)return;const key=(AUTO_TERMS.find(x=>x[0]===m[1])||[])[1];if(!key||!PG[key])return;const tag=host.__terms||(host.__terms=new Set());if(tag.has(key))return;tag.add(key);todo.push([n,m,key])});
 todo.forEach(([n,m,key])=>{const i=m.index,txt=n.nodeValue;if(n.nodeValue.slice(i,i+m[1].length)!==m[1])return;const a=document.createTextNode(txt.slice(0,i)),b=document.createTextNode(txt.slice(i+m[1].length));PDONE.add(a);PDONE.add(b);
  const s=document.createElement('span');s.className='term auto';s.setAttribute('data-tipk','1');s.setAttribute('data-tip',PG[key]);s.textContent=m[1];n.replaceWith(a,s,b)})}
let plainQ=false;const plainObs=new MutationObserver(()=>{if(plainQ)return;plainQ=true;requestAnimationFrame(()=>{plainObs.disconnect();try{fillFix($('#views'));['#views','#steps','#modal','#foot','aside'].forEach(s=>{plainify($(s));techify($(s));tabTerms($(s))})}finally{plainQ=false;observePlain()}})});
function observePlain(){['#views','#steps','#modal','#foot','aside'].forEach(s=>{const e=$(s);if(e)plainObs.observe(e,{childList:true,subtree:true,characterData:true})})}
Object.assign(GLOSS,{lock:'The part of a chip that checks a key before the chip starts. Right key: it opens. Wrong key: it stays shut.',
 glitch:'A split-second disturbance (a dip in power, a pulse of light) that makes one tiny part of the chip give the wrong answer for one step. Engineers call it a fault or a bit flip.',
 check:'The part of the lock that compares the key with the secret.',chip:'A small electronic circuit, like the one in a bank card or a car key.',
 step:'One beat of the chip’s clock. The chip moves forward one step per beat (engineers say clock cycle).',
 'build tool':'Yosys, a free program that turns a written design into a netlist of gates and wires.',
 proved:'Checked by a method that covers every possibility, for any number of steps. Still only for this chip plan and this kind of glitch.',
 simulated:'Computed by a software model of how glitches behave physically (timing, laser spot size). Not a measurement on a real chip.',
 'memory bit':'A cell that remembers a 0 or 1 from one step to the next (a flip-flop).',
 'µm':'Micrometre: a thousandth of a millimetre. A human hair is about 70 µm wide.',
 firmware:'The small program built into a chip that runs first when it powers up.',instruction:'One small command of a program, like "compare these two numbers".',
 estimate:'A rough score worked out from published scoring tables and stated assumptions; not a rating by a test lab.'});

const PROVED_ASSUME='Holds only for this one chip plan, for glitches that hit one wire for one step, for a wrong key that is held steady, and for a chip that starts normally. It is not a claim about a real chip.';
const PG={lock:'The part of a chip that checks a key before the chip starts. Right key: it opens. Wrong key: it stays shut.',
 key:'The secret the lock checks. Only one value (the right key) should be accepted.',
 chip:'A small electronic circuit, like the one in a bank card or a car key.',
 check:'The part of the lock that compares the key with the secret.',
 copy:'A repeated check of the key. The idea: a thief must fool every copy, not just one.',
 glitch:'A split-second disturbance (a dip in power, a pulse of light) that makes one tiny part of the chip give the wrong answer for one step. Engineers call it a fault or a bit flip.',
 step:'One beat of the chip’s clock. The chip moves forward one step per beat (engineers say clock cycle).',
 wire:'A connection that carries a single 0 or 1 between gates.',
 gate:'A tiny building block that combines 0s and 1s, for example AND, OR, NOT.',
 'memory cell':'A cell that remembers a 0 or 1 from one step to the next (engineers call it a flip-flop).',
 pattern:'Inside the chip, each state of the lock (Waiting, Checking, Open, Shut) is stored as a pattern of eight 0s and 1s.',
 garbled:'A pattern in the lock’s memory that is none of the four valid ones (Waiting, Checking, Open, Shut).',
 'answer signal':'The lock’s answer is 8 separate yes/no signals; the rest of the chip is meant to read all 8.',
 '“open” signal':'One extra yes/no signal that says “the lock is open”. If the rest of the chip reads only this signal, the copies do not protect it.',
 'written design':'The text an engineer writes to describe a chip, before any tool turns it into gates.',
 'chip plan':'The design as a list of gates and wires, ready to be made into a chip. Every result here belongs to one chip plan.',
 'build tool':'A free program that turns a written design into a chip plan of gates and wires. Different settings give different chip plans.',
 'checking program':'A program (a solver) that reasons about every combination exactly instead of trying samples.',
 limit:'The search only covers up to a stated number of glitches and steps. Nothing is claimed beyond that.',
 unknown:'The search was stopped or gave no answer. Nothing can be concluded; it does not mean “no way in”.',
 'weak spot':'A part of the chip that many of the cheapest ways in make use of.',
 live:'Computed now, on this computer.',
 recorded:'Computed earlier and stored with the project; shown from the saved file, not re-run here.',
 simulated:'Computed by a software model of how a glitch behaves physically (timing, laser spot size). Not a measurement on a real chip.',
 proved:'Checked by a method that covers every possibility for any waiting time. '+PROVED_ASSUME,
 estimate:'A rough score worked out from published scoring tables and stated assumptions; not a rating by a test lab.',
 points:'Test labs score an attack in points: more points means more time, skill and equipment are needed. A security level says up to how many points an attack still counts as realistic.',
 fingerprint:'A short number computed from a program or a file; if anything changes, the fingerprint changes too.',
 'µm':'Micrometre: a thousandth of a millimetre. A human hair is about 70 µm wide.',
 firmware:'The small program built into a chip that runs first when it powers up.',
 instruction:'One small command of a program, like “compare these two numbers”.',
 'computer model':'Everything in this app is computed; nothing is measured on a chip. The labels recorded and live say when a result was computed; simulated, proved and estimate say how.',
 Verilog:'A language engineers use to write a chip design as text.',
 'cell library':'The catalogue of ready-made gates that a chip factory offers. A chip plan for that factory uses only these.',
 'one-check lock':'The simplest example lock: the key is checked once.','two-check lock':'Two copies of the check that report through one shared wire.',
 'three-copy lock':'Three copies of the check; each copy controls its own part of the 8-signal answer.','three-copy lock, one pattern changed':'The three-copy lock with the pattern for Checking changed.',
 Waiting:'The lock has not started checking yet.',Checking:'The lock is checking the key (one step).',Open:'The lock is open: the key was accepted.',Shut:'The lock is shut: the key was rejected.'};
/* ---- small helpers shared by the new screens.  Five labels, each with a short gloss; everything else is a plain sentence. */
const HON={live:['live','computed now, on this computer','Computed on this computer in this session.'],
 recorded:['recorded','saved earlier, not re-run here','Computed earlier and stored in the project files; shown from the file, not re-run.'],
 simulated:['simulated','the physics modelled in software (laser spot, clock timing)','The physics of a glitch (a laser spot, clock timing, a program on a processor) modelled in software; nothing was measured on a real chip.'],
 proved:['proved','for any waiting time, but only for this one chip plan, one-wire glitches and a normal start','Covers every possibility for any number of steps. '+PROVED_ASSUME],
 bounded:['bounded','exact, but only within the stated number of steps','The smallest number, found and checked, within the stated number of clock steps after a normal start. It says nothing about longer runs, so it is not called proved.'],
 estimate:['estimate','a rough score, not a lab rating','A rough score from published tables and stated assumptions, not a lab rating.'],
 cached:['live','computed on this computer earlier','Computed on this computer earlier and kept in its local cache.']};
const hon=(k,extra,bare)=>k==='notrun'?`<span class="hint">no result yet</span>`:`<span class="tg"><span class="chip h-${k==='cached'?'live':k}" data-tipk="1" data-tip="${esc(HON[k][2]+(extra?' '+extra:''))}">${HON[k][0]}</span>${bare?'':`<span class="gloss">${HON[k][1]}</span>`}</span>`;
const ntag=(txt,tip,cls)=>`<span class="ntag ${cls||''}" data-tip="${esc(tip||'')}">${txt}</span>`;
const orient=(look,means,next)=>`<div class="orient" role="note"><div><h5>What you are looking at</h5><p>${look}</p></div><div><h5>What it means</h5><p>${means}</p></div><div><h5>What you can do</h5><p>${next}</p></div></div>`;
const learn=(sum,html)=>`<details class="more learn"><summary>${esc(sum||'Learn more (technical details)')}</summary><div class="pb">${html}</div></details>`;
const G=n=>n===1?'glitch':'glitches';
const gl=n=>n+' '+G(n);
const words=n=>['no','one','two','three','four','five','six'][n]??String(n);
function modProblem(d,what){if(!d)return `<div class="empty"><b>Loading…</b></div>`;
 if(d.missing)return `<div class="empty"><b>${esc(what)} is not installed in this project folder</b>Nothing can be shown, and nothing is guessed. <span class="plain-only">Switch to Technical view to see where it was looked for.</span><span class="tech-only">To add it, copy the module into <span class="keep mono">${esc(d.looked[0])}</span> and reload this window.<br>Also looked in: ${esc(d.looked.slice(1).join(', '))}</span></div>`;
 if(d.broken)return `<div class="err"><b>${esc(what)} could not be read</b><p>The files are there, but one of them could not be read. Try reloading; if it stays like this, the module may be from a different version.</p><details class="raw"><summary>Details</summary><pre>${esc(d.where+': '+d.detail)}</pre></details></div>`;
 if(d.error)return `<div class="err"><b>The Studio could not answer</b><p>Start GlitchSAT Studio again, then reload this window.</p></div>`;return ''}
const srcLine=(d,extra)=>`<div class="fsrc tech-only">${d.in_repo?'project':'module'} folder: <span class="keep">${esc(d.where||'')}</span>${extra?' · '+esc(extra):''}</div>`;
S.mods={};
async function getMod(name,q){const key=name+(q||'');if(S.mods[key])return S.mods[key];try{S.mods[key]=await api.get('/api/mod?name='+name+(q||''))}catch(e){S.mods[key]={error:'offline'}}return S.mods[key]}

/* ---- onboarding story (first launch; skippable; re-open with "How it works") */
const svgLock=(x,y,open,col)=>`<g transform="translate(${x},${y})"><path d="${open?'M-14,-6V-20a14,14 0 0 1 28,0V-14':'M-14,-6V-20a14,14 0 0 1 28,0V-6'}" fill="none" stroke="${col}" stroke-width="5" ${open?'transform="translate(10,-6)"':''}/><rect x="-22" y="-8" width="44" height="36" rx="6" fill="${col}"/><circle cx="0" cy="6" r="5" fill="var(--panel)"/><rect x="-2" y="8" width="4" height="10" fill="var(--panel)"/></g>`;
const svgKey=(x,y,col,rot)=>`<g transform="translate(${x},${y}) rotate(${rot||0})"><circle cx="0" cy="0" r="11" fill="none" stroke="${col}" stroke-width="5"/><path d="M11,0H46M34,0V9M42,0V7" stroke="${col}" stroke-width="5" fill="none"/></g>`;
const svgChip=(x,y,w,h)=>{let p='';for(let i=0;i<5;i++){const xx=x+12+i*(w-24)/4;p+=`<rect x="${xx-3}" y="${y-9}" width="6" height="9" fill="var(--mut)"/><rect x="${xx-3}" y="${y+h}" width="6" height="9" fill="var(--mut)"/>`}return p+`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="var(--raised)" stroke="var(--line2)" stroke-width="2"/>`};
const svgThief=(x,y)=>`<g transform="translate(${x},${y})"><circle cx="0" cy="-34" r="15" fill="var(--mut)"/><rect x="-16" y="-38" width="32" height="8" rx="3" fill="var(--txt)"/><circle cx="-6" cy="-34" r="2.2" fill="var(--panel)"/><circle cx="6" cy="-34" r="2.2" fill="var(--panel)"/><path d="M-22,22V-6a10,10 0 0 1 10,-10h24a10,10 0 0 1 10,10V22z" fill="var(--mut)"/></g>`;
const bolt=(x,y,s,col)=>`<path transform="translate(${x},${y}) scale(${s||1})" d="M4,-14L-8,3H0L-4,16L10,-3H2z" fill="${col||'var(--warn)'}" stroke="var(--panel)" stroke-width="1.2"/>`;
const STORY=[
 {h:'A chip has a lock',p:'Many chips (in a bank card, a car key, a phone) check a secret <b>key</b> before they start working. <b>Right key: the lock opens. Wrong key: it stays shut.</b>',
  svg:()=>`<svg viewBox="0 0 560 170" width="560" height="170" role="img" aria-label="A chip with a lock: the right key opens it, a wrong key does not">${svgChip(200,30,160,110)}${svgLock(280,95,false,'var(--acc)')}
  ${svgKey(40,55,'var(--ok)')}<text x="40" y="95" font-size="13" fill="var(--ok)">right key</text><path d="M100,55H170" stroke="var(--ok)" stroke-width="2" marker-end="url(#sa)"/>
  ${svgKey(400,120,'var(--hot)')}<text x="400" y="158" font-size="13" fill="var(--hot)">wrong key</text><text x="470" y="58" font-size="14" fill="var(--txt)">✓ opens</text><text x="470" y="80" font-size="14" fill="var(--txt)">✕ stays shut</text>
  <defs><marker id="sa" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="var(--ok)"/></marker></defs></svg>`},
 {h:'A thief without the key',p:'A thief wants in, but does not have the key. Guessing will not work, so the thief tries something sneakier than guessing.',
  svg:()=>`<svg viewBox="0 0 560 170" width="560" height="170" role="img" aria-label="A thief holding a wrong key in front of a shut lock">${svgThief(120,120)}${svgKey(150,92,'var(--hot)',-10)}<text x="168" y="70" font-size="26" fill="var(--warn)">?</text>
  ${svgChip(300,30,160,110)}${svgLock(380,95,false,'var(--acc)')}<text x="380" y="164" font-size="13" text-anchor="middle" class="m">shut</text></svg>`},
 {h:'The glitch',p:'At exactly the right moment, the thief disturbs the chip for a split second: a dip in its power, or a pulse of light. For that one instant, a tiny part of the chip gives the wrong answer, and the check says "yes" to a wrong key. That is a <b>glitch</b>. A chip works in <b>steps</b>, like the ticks of a clock, so the timing has to be perfect.',
  svg:()=>{let s='';for(let i=0;i<6;i++){const x=40+i*82;s+=`<rect x="${x}" y="40" width="74" height="54" rx="6" fill="${i===2?'color-mix(in srgb,var(--warn) 22%,transparent)':'var(--raised)'}" stroke="${i===2?'var(--warn)':'var(--line2)'}" stroke-width="${i===2?2:1}"/><text x="${x+37}" y="112" font-size="12.5" text-anchor="middle" class="m">step ${i+1}</text><text x="${x+37}" y="72" font-size="13" text-anchor="middle">${i===2?'"yes"?!':i<2?'checking':i===3?'open':'…'}</text>`}
   return `<svg viewBox="0 0 560 170" width="560" height="170" role="img" aria-label="Six steps of the chip's clock; a glitch at step 3 makes the check say yes">${s}${bolt(239,28,1.6)}<text x="239" y="150" font-size="13" text-anchor="middle" fill="var(--warn)">one glitch, perfectly timed</text></svg>`}},
 {h:'Why engineers add copies',p:'To make this harder, engineers check the key with several <b>copies</b> of the check. Now the thief has to glitch <b>every copy</b>, each at exactly the right moment. But copies only help if they stay apart: if they all report through <b>one shared wire</b>, one glitch on that wire is still enough.',
  svg:()=>{const c=i=>`<rect x="20" y="${18+i*44}" width="92" height="32" rx="5" fill="none" stroke="var(--c${i})" stroke-width="2"/><text x="66" y="${39+i*44}" font-size="13" text-anchor="middle">copy ${i+1}</text>`;
   const c2=i=>`<rect x="300" y="${18+i*44}" width="92" height="32" rx="5" fill="none" stroke="var(--c${i})" stroke-width="2"/><text x="346" y="${39+i*44}" font-size="13" text-anchor="middle">copy ${i+1}</text><path d="M392,${34+i*44}H440" stroke="var(--c${i})" stroke-width="2"/>${bolt(370,10+i*44,.9)}`;
   return `<svg viewBox="0 0 560 170" width="560" height="170" role="img" aria-label="Left: three copies joined into one shared wire, one glitch is enough. Right: three separate copies, one glitch each.">${[0,1,2].map(c).join('')}<path d="M112,34H150V78M112,78H150M112,122H150V78" stroke="var(--mut)" stroke-width="2" fill="none"/><path d="M150,78H230" stroke="var(--hot)" stroke-width="3"/>${bolt(190,66,1.2)}${svgLock(255,92,true,'var(--acc)')}<text x="140" y="164" font-size="13" text-anchor="middle" fill="var(--hot)">one shared wire: 1 glitch is enough</text>
   ${[0,1,2].map(c2).join('')}${svgLock(500,92,false,'var(--acc)')}${[0,1,2].map(i=>`<path d="M440,${34+i*44}C462,${34+i*44} 462,${84+i*6} 476,${84+i*6}" stroke="var(--c${i})" stroke-width="2" fill="none"/>`).join('')}<text x="420" y="164" font-size="13" text-anchor="middle" fill="var(--ok)">kept apart: 1 glitch per copy</text></svg>`}},
 {h:'What this app does',p:'GlitchSAT takes small example lock designs, imagines <b>every possible glitch at every step</b>, and finds the <b>fewest perfectly-timed glitches</b> that let a wrong key in. More glitches needed means a harder job for the thief. It is a computer model: no real chip is zapped.',
  svg:()=>{let g='';for(let r=0;r<4;r++)for(let c=0;c<9;c++){const hit=(r===1&&c===2)||(r===2&&c===5)||(r===0&&c===7);g+=`<rect x="${24+c*24}" y="${30+r*26}" width="18" height="18" rx="3" fill="${hit?'var(--warn)':'var(--raised)'}" stroke="var(--line2)"/>`}
   return `<svg viewBox="0 0 560 170" width="560" height="170" role="img" aria-label="Every possible glitch is tried; the answer is the smallest number that opens the lock">${g}<text x="130" y="152" font-size="13" text-anchor="middle" class="m">every glitch, every step, every wrong key</text><path d="M260,80H320" stroke="var(--mut)" stroke-width="2" marker-end="url(#sb)"/>
   <rect x="340" y="34" width="190" height="92" rx="10" fill="color-mix(in srgb,var(--f3) 14%,transparent)" stroke="var(--f3)" stroke-width="2"/><text x="435" y="86" font-size="40" font-weight="700" text-anchor="middle" fill="var(--f3)">3</text><text x="435" y="112" font-size="13" text-anchor="middle">glitches needed</text>
   <defs><marker id="sb" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="var(--mut)"/></marker></defs></svg>`}},
 {h:'Ready? Watch the first attack',p:'Start with the simplest lock and watch a thief get in. Then follow the path: each step adds one idea, and every result is explained in a sentence first. You can always come back to this story with <b>How it works</b> at the top.',
  svg:()=>`<svg viewBox="0 0 560 150" width="560" height="150" role="img" aria-label="A path of six steps">${[0,1,2,3,4,5].map(i=>`<circle cx="${60+i*88}" cy="70" r="22" fill="${i===0?'var(--acc)':'var(--raised)'}" stroke="var(--line2)" stroke-width="2"/><text x="${60+i*88}" y="76" font-size="16" font-weight="700" text-anchor="middle" fill="${i===0?'var(--acc-t)':'var(--txt)'}">${i+1}</text>${i<5?`<path d="M${82+i*88},70H${126+i*88}" stroke="var(--line2)" stroke-width="2" stroke-dasharray="4 4"/>`:''}`).join('')}<text x="60" y="118" font-size="13" text-anchor="middle">start here</text></svg>`}];
function openStory(i){S.story=i||0;drawStoryCard()}
function closeStory(nofocus){S.story=null;$('#modal').innerHTML='';LS.set('gs_seen3',1);if(nofocus)return;const b=(S.tab==='start'&&$('#h-try'))||$('#tabs .tab.on')||$('#b-story');if(b)b.focus()}
function drawStoryCard(){const i=S.story;if(i==null)return;const c=STORY[i],last=i===STORY.length-1;
 $('#modal').innerHTML=`<div class="modal" id="mbg"><div class="dlg story-dlg" role="dialog" aria-modal="true" aria-labelledby="sth"><div class="db"><div class="card"><div class="kick">The story · ${i+1} of ${STORY.length}</div><h2 id="sth">${esc(c.h)}</h2>${c.svg()}<p>${c.p}</p></div></div>
 <div class="df"><div class="dots" aria-hidden="true">${STORY.map((_,j)=>`<i class="${j===i?'on':''}"></i>`).join('')}</div><button class="btn" id="sk">${last?'Look around first':'Skip the story'}</button><button class="btn" id="sbk" ${i?'':'disabled'}>Back</button>${last?'<button class="btn primary" id="sgo">▶ Watch the first attack</button>':'<button class="btn primary" id="snx">Next</button>'}</div></div></div>`;
 $('#sk').onclick=()=>{closeStory(true);show('start');const b=$('#h-try');if(b)b.focus()};$('#sbk').onclick=()=>{S.story--;drawStoryCard()};if($('#snx'))$('#snx').onclick=()=>{S.story++;drawStoryCard()};if($('#sgo'))$('#sgo').onclick=()=>{closeStory(true);tryAttack()};
 $('#mbg').onclick=e=>{if(e.target.id==='mbg')closeStory()};const f=$('#snx')||$('#sgo');f&&f.focus()}
function trapFocus(e){const m=$('#modal .dlg');if(!m||e.key!=='Tab')return;const f=[...m.querySelectorAll('button:not([disabled]),a,[tabindex="0"],input,select')];if(!f.length)return;const a=f[0],b=f[f.length-1];
 if(e.shiftKey&&document.activeElement===a){e.preventDefault();b.focus()}else if(!e.shiftKey&&document.activeElement===b){e.preventDefault();a.focus()}}
document.addEventListener('keydown',trapFocus);

/* ---- the path: TOUR steps with a plain goal each */
const PATH=[
 {p:'A lock with one check',goal:'See how one glitch can open a simple lock.',look:'The simplest lock: the key is checked once.',next:'Press <b>Next step</b> to add a second copy of the check.'},
 {p:'Check it twice',goal:'Find out whether a second copy of the check stops the thief.',look:'Two copies of the check. Both have to agree before the lock opens.',next:'Press <b>Next step</b>: three copies, with no shared wire.'},
 {p:'Three copies, kept apart',goal:'See the thief need one glitch per copy.',look:'Three copies, and each one controls its own part of the lock’s answer. No single wire decides.',next:'Press <b>Next step</b> to see the same written design turned into a second chip plan.'},
 {p:'Same design, a second chip plan',goal:'Learn that the build tool can quietly weaken the protection.',look:'Exactly the same written design as step 3. The build tool, the program that turns a written design into a chip plan, made a second chip plan from it.',next:'Press <b>Next step</b>: change one stored pattern and make the chip plan again.'},
 {p:'Change one pattern',goal:'See a one-pattern change bring the protection back on this chip plan.',look:'Inside the chip, Waiting, Checking, Open and Shut are each stored as a pattern of eight 0s and 1s. We changed the pattern for Checking and made the chip plan again, the same way as in step 4.',next:'Press <b>Next step</b>: what if the rest of the chip reads only one signal?'},
 {p:'Only one signal is read',goal:'See why the rest of the chip must read the whole answer.',look:'The three-copy lock again, but the rest of the chip only looks at one "open" signal instead of the whole answer.',next:'You finished the path. <b>Explore</b> (at the top) has more: weak spots, fixes, proofs and laser shots on a real chip layout. In a hurry? <button class="linkb" data-go="found">What we found, in one minute</button>.'}];
function tryAttack(){show('analyze');const d=Object.keys(S.tourRes).length;let i=0;if(d>0&&d<PATH.length){while(S.tourRes[i]!==undefined&&i<PATH.length-1)i++}loadStep(i)}

/* ---- result sentence (Plain view): the answer first, as one sentence */
function resultSentence(r){const n=r.min_faults,k=r._k,N=r._cycles;
 if(r._stop)return `We do not know yet: the search was stopped before it finished, so nothing can be said either way.`;
 if(r.verdict==='ATTACK_FOUND'){if(n===0)return `This lock opens for a wrong key even without any glitch (within ${N} steps).`;
  if(r._goal==='flag')return `A thief would need ${n} perfectly-timed ${G(n)} to make the chip start with a wrong key: the ${G(n)} ${n===1?'fakes':'fake'} the lock’s “open” signal, while the lock itself stays shut. ${n===1?'With no glitch at all':`With ${n-1} or fewer`} this never worked (we checked every possibility within ${N} steps).`;
  return `A thief would need ${n} perfectly-timed ${G(n)} to get in with a wrong key. ${n===1?'With no glitch at all':`With ${n-1} or fewer`} they never got in (we checked every possibility within ${N} steps).`}
 return `Even with ${k} ${G(k)}, a thief never got in with a wrong key (we checked every possibility within ${N} steps). More glitches or more time were not tried.`}

/* ---- 3.1: saved-results banner, "how to run it live", "what we found" */
const fmtN=n=>Number(n).toLocaleString('en-US');
function noProjectBanner(){const s=S.status||{};return s.studio&&s.project_found===false?`<div class="err" role="alert"><b>This is not a GlitchSAT project folder.</b><p>The Studio was started in <span class="keep mono">${esc(s.root||'')}</span>, which has no saved results and no engine, so the path and Explore have nothing to show. Start it from the repository (<code class="keep">python3 tools/studio/studio.py</code>), or set <code class="keep">GLITCHSAT_ROOT</code> to the repository folder, then reload this window.</p></div>`:''}
function savedBanner(){if(noProjectBanner())return noProjectBanner();return `<div class="banner"><span class="bt">${T(`<b style="color:var(--txt)">You are seeing saved results. Nothing is missing:</b> every number was computed earlier and stored with the project. Pages that can recompute on this computer say so next to their button.`,`<b style="color:var(--txt)">Recorded mode.</b> The solver is not installed here, so results are read from the project files and labelled recorded.`)} <button class="linkb" data-go="live">How to run it live</button></span></div>`}
function howLive(){const s=S.status||{},rt=s.recorded_tools||{};
 return `<div class="howlive keep"><ol>
 <li>${s.live?'<b>Done:</b> the solver (z3 '+esc(s.z3||'')+') is installed, so attacks are computed live.':'Install the solver, z3, inside a Python virtual environment:<br><code>python3 -m venv .venv &amp;&amp; . .venv/bin/activate</code> then <code>pip install z3-solver</code>'}</li>
 <li>${s.yosys?'<b>Done:</b> the build tool (Yosys '+esc(s.yosys_short||'')+') is installed.':'Optional, only for chip plans that are made again and for the build studies: install the build tool, Yosys:<br><code>sudo apt-get install -y yosys</code>'+(rt.yosys?' (the saved results were made with Yosys '+esc(rt.yosys)+'; another version can give different chip plans)':'')}</li>
 <li>${s.live?'Nothing else to do.':'Close this window and start GlitchSAT Studio again from that same terminal. The line at the bottom then says <b>Live</b>, and every new result is labelled live.'}</li></ol>
 <p><b>Runs here already, with nothing to install:</b> Weak spots (Recount, Check now), “Holds for any waiting time?” (Prove again) and the independent check in Studies.</p>
 ${s.live?'':`<p>Right now ${s.why?'Python reports “'+esc(s.why)+'”':'the solver was not found'}, so every number on screen is a saved result from the project files, labelled recorded.</p>`}</div>`}
function openDlg(title,html){S.dlg={opener:document.activeElement};$('#modal').innerHTML=`<div class="modal" id="mbg"><div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlt" style="width:min(900px,94vw)"><div class="dh" style="padding:10px 12px"><b id="dlt" style="font-size:15px">${esc(title)}</b><span style="flex:1"></span><button class="btn ico" id="dx" aria-label="close">✕</button></div><div class="db" style="min-height:0">${html}</div><div class="df"><span style="flex:1"></span><button class="btn primary" id="dclose">Close</button></div></div></div>`;
 $('#dx').onclick=$('#dclose').onclick=closeDlg;$('#mbg').onclick=e=>{if(e.target.id==='mbg')closeDlg()};$('#dclose').focus()}
function closeDlg(){const o=S.dlg&&S.dlg.opener;S.dlg=null;$('#modal').innerHTML='';if(o&&document.contains(o)&&o!==document.body)o.focus()}
const openLive=()=>openDlg('How to run it live on this computer',howLive());
const openFound=()=>openDlg('What we found, in one minute',foundHTML(true));
function go(g){if(S.dlg){S.dlg.opener=null;closeDlg()}if(g==='live')openLive();else if(g==='found')openFound();else if(g==='studies')show('findings');else if(g==='about')show('about');else if(/^p\d$/.test(g)){show('analyze');loadStep(+g[1])}else if(Studio.onGo&&Studio.onGo(g)){/* LEARN-VIEW hook: links handled by an extension (learn_view.py) */}else openExplore(g)}
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-go]');if(b){e.preventDefault();e.stopPropagation();go(b.dataset.go)}});
function foundHTML(inDlg){const F=S.find,v=F&&F.synth&&F.synth.designs&&F.synth.designs.v2,R=S.real&&S.real.agree,ui=S.real&&S.real.under_investigation;
 const sm=(g,t)=>` <button class="linkb" data-go="${g}">${t||'show me'}</button>`;
 const items=[
  ['One check is not enough.',`A lock that checks the key once lets a wrong key in after <b>1 glitch</b>. A second check that reports through the same wire does not help: still 1.`+sm('p0')],
  ['Copies that are kept apart do help.',`With three copies that each control their own part of the answer, a thief needs <b>3 glitches</b>, one per copy, all at the same step.`+sm('p2')],
  ['The build tool can quietly undo the protection.',(v&&v.min?`The same written design was turned into a chip plan with ${v.solved} build settings${(S.find&&S.find.synth&&S.find.synth.distinct&&S.find.synth.distinct.n)?` (${S.find.synth.distinct.n} distinct chip plans)`:''}: <b>${v.min[1]} of them need only 1 glitch</b>, ${v.min[2]} need 2 and only ${v.min[3]} need 3.`:'The same written design, turned into a chip plan with other settings of the build tool, often needs only 1 or 2 glitches instead of 3.')+sm('studies')],
  ['The rest of the chip must read the whole answer.',`If it looks at a single “open” signal, <b>1 glitch</b> on that signal is enough, and the copies no longer matter.`+sm('p5')],
  R?['On real designs it agrees with an existing tool.',`On blocks of a real open-source security chip, GlitchSAT and ${T('an existing published tool','SYNFI, an existing published tool,')} gave the same answer on <b>${R[0]===R[1]?'all '+fmtN(R[1]):fmtN(R[0])+' of '+fmtN(R[1])}</b> glitch attempts compared.${ui?' One published figure is not matched exactly; that row is marked under investigation.':S.real.reconciled&&(S.real.experiments||[]).some(e=>e.status==='differs')?' One published figure differs slightly; that difference has been checked and is explained on the page.':''}`+sm('x-real')]:null].filter(Boolean);
 return `<div class="found${inDlg?' indlg':''}" id="${inDlg?'found-d':'found'}">${inDlg?'':'<h2>What we found, in one minute</h2>'}<p class="sub">${items.length} findings in plain words. All of them are saved results of a computer model; no real chip was glitched.</p>
 <div class="fcols"><ol>${items.map(i=>`<li><b class="h">${i[0]}</b> ${i[1]}</li>`).join('')}</ol>
 <div><h5>What to do next</h5><ol class="next">
 <li><b>If your product relies on repeated checks,</b> ask the chip team two questions. Are the copies still separate in the final chip plan, after the build tool has run? Does the rest of the chip read the whole answer, not one signal?</li>
 <li><b>To check your own design,</b> ask an engineer to run GlitchSAT on its chip plan. The tool reads chip plans made by the free build tool used here; other formats have to be converted first.</li>
 <li><b>Treat the numbers as an early design check,</b> not a certificate. A test lab still has to attack the real chip.</li></ol>
 <p class="scope"><b>Scope.</b> Small example locks and a few blocks of one real open-source chip. One kind of glitch: one wire gives the wrong answer for one step. Results marked “proved” hold for any waiting time, but only for one chip plan, that kind of glitch and a chip that starts normally.</p></div></div></div>`}

/* ---- Start page */
function xlist(){return EXPLORE.filter(v=>(tech()||!v.hidePlain||!v.hidePlain())&&!(v.hide&&v.hide()))}
function drawStart(el){el=el||$('#v-start');const st=S.status||{};const done=Object.keys(S.tourRes).length;let nxt=0;while(S.tourRes[nxt]!==undefined&&nxt<PATH.length-1)nxt++;
 const cta=done===0?['▶ Watch the first attack','Recommended first example: <b>a lock with one check</b>. Takes about a second, then the path continues step by step.']:done<PATH.length?[`▶ Continue: step ${nxt+1} of ${PATH.length}`,`Next on your path: <b>${esc(PATH[nxt].p)}</b>. Your progress is kept on this computer.`]:['▶ Walk the path again',`You finished all ${PATH.length} steps. There is more under <b>Explore</b> below.`];
 const stepCard=(p,i)=>{const r=S.tourRes[i],has=r!==undefined;return `<button class="pcard${has?' done':''}" data-i="${i}" aria-label="Step ${i+1}: ${esc(p.p)}"><span class="n">${i+1}</span><b>${esc(p.p)}</b><span class="g">${esc(p.goal)}</span>${has?`<span class="res">${r==='unknown'?'not finished':r==null?'no way in found':gl(r)+' needed'}</span>`:''}</button>`};
 const ex=xlist().map(v=>`<button class="xcard" data-x="${v.id}"><span class="xi" aria-hidden="true">${v.icon||''}</span><b>${esc(v.title)}</b><span>${esc(v.blurb)}</span><span class="xl">${(v.labels||[]).slice(0,1).map(l=>hon(l)).join(' ')}</span></button>`).join('');
 el.innerHTML=`<div class="home"><div class="hero"><div class="hx"><h1>Can a thief glitch their way past a lock?</h1>
  <p>Chips check a secret key before they start. A thief without the key can try to disturb the chip for a split second, a <b>glitch</b>, so that a wrong key is accepted. This app counts <b>how many perfectly-timed glitches</b> that takes, and shows which designs make it harder.</p>
  <div class="cta"><button class="btn primary big" id="h-try">${cta[0]}</button><div class="ctah">${cta[1]}</div></div>
  <p class="small"><b style="color:var(--txt)">In a hurry?</b> <button class="linkb" id="h-found">What we found, in one minute</button> · <button class="linkb" id="h-story">Watch the short story again</button> · <button class="linkb" id="h-help">Glossary and keyboard keys</button></p>${Studio.startExtra?Studio.startExtra():''/* LEARN-VIEW hook: Start-page link from an extension */}</div>
  <div class="hart" aria-hidden="true">${(STORY.find(c=>c.h==='Why engineers add copies')||STORY[3]).svg()/* LEARN-VIEW: found by title, extensions may add story cards */}</div></div>
  ${st.studio&&!st.live?savedBanner():''}
  <h3 class="sec">Your path <span class="m">· ${done} of ${PATH.length} done</span></h3><div class="pgrid">${PATH.map(stepCard).join('')}</div>
  <details class="more startmore" id="start-more"${S.startMore?' open':''}><summary>More on this page: what we found, and all ${xlist().length} Explore pages</summary>
  ${foundHTML()}
  <h3 class="sec">Explore more <span class="m">· each page starts with what you are looking at</span></h3><div class="xgrid">${ex}</div>
  ${!tech()&&S.hw&&S.hw.total&&!S.hw.run?`<p class="hint" style="margin:8px 2px 0">Coming: our own boot-check circuit (${S.hw.total} versions designed, not analysed yet).</p>`:''}</details>
  <div class="foot-note" style="display:block">Everything here is computed; nothing is measured on a chip. Each result carries one of six labels. <b>Recorded</b> and <b>live</b> say <i>when</i> it was computed; <b>simulated</b>, <b>bounded</b>, <b>proved</b> and <b>estimate</b> say <i>how</i>.<div class="legend5">${['live','recorded','simulated','bounded','proved','estimate'].map(k=>hon(k)).join('')}</div></div></div>`;
 $('#h-try').onclick=tryAttack;$('#h-story').onclick=()=>openStory(0);$('#h-help').onclick=()=>openHelp('gloss');$('#h-found').onclick=()=>{const m=$('#start-more');if(m){m.open=true;S.startMore=true}const f=$('#found');f.scrollIntoView({behavior:'smooth',block:'start'});f.setAttribute('tabindex','-1');f.focus({preventScroll:true})};
 {const m=$('#start-more');if(m)m.addEventListener('toggle',()=>{S.startMore=m.open})}
 el.querySelectorAll('.pcard').forEach(b=>b.onclick=()=>{show('analyze');loadStep(+b.dataset.i)});el.querySelectorAll('.xcard').forEach(b=>b.onclick=()=>openExplore(b.dataset.x))}

/* ---- Explore: one tab, a list of pages on the left (EXTENSION POINT: Studio.registerView({group:'explore', ...})) */
const EXPLORE=[];
function openExplore(id){S.xv=id||S.xv||(EXPLORE[0]&&EXPLORE[0].id);show('explore')}
function drawExplore(el){el=el||$('#v-explore');const XL=xlist();if(!S.xv||!XL.find(x=>x.id===S.xv))S.xv=XL[0].id;
 if(!$('#xnav')){el.innerHTML=`<div class="xwrap"><nav class="xnav" id="xnav" aria-label="Explore pages"></nav><div class="xbody" id="xbody"></div></div>`}
 $('#xnav').innerHTML=`<div class="xh">Explore</div>`+XL.map(v=>`<button class="xn${v.id===S.xv?' on':''}" data-x="${v.id}" aria-current="${v.id===S.xv?'page':'false'}"><span class="xi" aria-hidden="true">${v.icon||''}</span><span><b>${esc(T(v.title,v.ttitle||v.title))}</b><span>${esc(v.blurb)}</span></span></button>`).join('');
 $$('#xnav .xn').forEach(b=>b.onclick=()=>{S.xv=b.dataset.x;drawExplore()});
 const v=EXPLORE.find(x=>x.id===S.xv),body=$('#xbody');body.innerHTML=`<h2 class="xt">${esc(T(v.title,v.ttitle||v.title))} ${(v.labels||[]).map(l=>hon(l)).join(' ')}</h2><div id="xc"></div>${XFIX[v.id]?fixHost(XFIX[v.id]):''}`;
 const xc=$('#xc');xc.innerHTML=modProblem(null);Promise.resolve(v.render(xc)).then(()=>{const L=v.findings&&v.findings();if(L&&L.length&&!xc.querySelector('.findings')){const o=xc.querySelector('.orient');(o||xc).insertAdjacentHTML(o?'afterend':'afterbegin',findingsHTML(L));(plainify||(()=>{}))(xc)}}).catch(e=>{xc.innerHTML=`<div class="err"><b>This page could not be drawn</b><p>Try reloading the window.</p><details class="raw"><summary>Details</summary><pre>${esc(String(e&&e.stack||e))}</pre></details></div>`})}

/* small chart helpers (SVG, labelled; colour is never the only carrier of meaning) */
const COPYC=c=>/^c\d/.test(c||'')?`var(--c${c[1]})`:c==='shared'||c==='merge'?'var(--hot)':'var(--shared)';
const COPYP=c=>({c0:'inside copy 1',c1:'inside copy 2',c2:'inside copy 3','c0:path':'on copy 1’s way to the answer','c1:path':'on copy 2’s way to the answer','c2:path':'on copy 3’s way to the answer',shared:'shared by several copies',merge:'where the copies are joined',outside:'outside the copies (lock memory and wiring)',g0:'in the one check'}[c]||c||'unknown');
const pct=x=>Math.round(x*100)+'%';
function segBtns(id,opts,cur){return `<div class="seg wrap" id="${id}" role="group">${opts.map(o=>`<button data-v="${esc(o[0])}" class="${o[0]===cur?'on':''}" aria-pressed="${o[0]===cur}">${esc(o[1])}</button>`).join('')}</div>`}
function onSeg(id,fn){const s=$('#'+id);if(s)s.onclick=e=>{const b=e.target.closest('button');if(b&&!b.disabled)fn(b.dataset.v)}}
function liveBtn(sid,label,tip){const st=(S.find&&S.find.studies||{})[sid],j=S.jobs[sid];
 if(!st)return '';if(!st.available)return `<span class="hint">Cannot be re-run here: ${esc(st.reason)}. <button class="linkb" data-go="live">How to run it live</button></span>`;
 if(j&&j.status==='running')return `${hon('live',null,true)} <span class="hint">running: ${j.done} of ${j.total} done</span> <button class="btn" data-cancel="${sid}">Cancel</button>`;
 return `<span class="hint">runs on this computer, nothing to install</span> <button class="btn" data-run="${sid}" data-tip="${esc(tip||'')}">${esc(label)}${st.run?` · about ${secs(st.run.est_s)}`:''}</button>`}
function wireLive(el,redraw){el.querySelectorAll('[data-run]').forEach(b=>b.onclick=async()=>{await startStudy(b.dataset.run,{});S.redraw=redraw;redraw()});el.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>cancelStudy(b.dataset.cancel))}
const liveOf=id=>{const x=S.live[id];return x&&x.state==='ok'?x:null};

/* 1. Weak spots: every cheapest attack + are the copies kept apart */
async function viewSurface(el){const d=await getMod('surface');const p=modProblem(d,'The weak-spots module');if(p){el.innerHTML=p;return}
 if(!S.find)await loadFindings();const D=d.designs.filter(x=>!x.id.endsWith('_k2'));if(!S.sv||!D.find(x=>x.id===S.sv))S.sv='surface_v2_T6';const x=D.find(z=>z.id===S.sv)||D[0];
 const m=x.min_faults,c=x.count,lv=liveOf('surface|'+x.id),ll=liveOf('lint|'+x.id);
 const lintRec=(d.lint&&d.lint.rows||[]).find(r=>r.netlist===x.netlist),lintV=ll?ll.v:lintRec&&lintRec.verdict;
 const LV={separate:['Kept apart','No wire is shared by two copies, and no single point joins them before the answer.'],merged:['Merged','Some wires are shared by several copies, so one glitch there acts on all of them at once.'],partially_shared:['Partly shared','Some wires are shared by two copies.'],single_group:['Only one check','There is only one check, so there are no copies to keep apart.'],no_copies:['No copies found','No copies of the check could be found.']};
 const sent=x.verdict==='ATTACK_FOUND'?`On this lock there ${c===1?'is':'are'} <b>${c}</b> different cheapest ${c===1?'way':'ways'} in, each using <b>${gl(m)}</b>. We listed every one: every possible set of up to ${m} glitches within ${x.cycles} steps was tried.`:`No way in with up to ${gl(x.max_faults)} within ${x.cycles} steps: every combination was tried.`;
 const nm0=(x.nets||[]).slice(0,12).map(n=>(n.gate==='DFF'?'a memory cell ':'a gate ')+COPYP(n.copy)),ncnt={},nix={};nm0.forEach(s=>ncnt[s]=(ncnt[s]||0)+1);
 const nm1=nm0.map(s=>{if(ncnt[s]<2)return s;nix[s]=(nix[s]||0)+1;return s.replace(/^a (gate|memory cell)/,'$1 '+String.fromCharCode(64+nix[s]))});
 const tot=x.count||1,bars=(x.nets||[]).slice(0,12).map((n,bi)=>`<div class="hbar" data-tip="${esc(COPYP(n.copy))}: used in ${n.count} of ${tot} cheapest ways in" data-tipm="${esc(n.net)} (${n.gate||n.kind})"><span class="hl"><span class="sw" style="background:${COPYC(n.copy)}"></span>${T(esc(nm1[bi]),`<span class="mono">${esc(n.net)}</span>`)}</span><span class="hb"><i style="width:${100*n.count/tot}%;background:${COPYC(n.copy)}"></i></span><span class="hv">${n.count} <span class="m">(${pct(n.count/tot)})</span></span></div>`).join('');
 const cps=Object.entries(x.copies||{}),share=cps.map(([k,v])=>`<div style="flex:${v.share};box-shadow:inset 0 -4px 0 ${COPYC(k.split(':')[0])}" class="sseg" data-tip="${esc(COPYP(k))}: ${pct(v.share)} of all glitches in the cheapest ways in">${v.share>=.12?`<span>${esc(T(COPYP(k).replace(/^inside /,''),k))} ${pct(v.share)}</span>`:''}</div>`).join('');
 const touched=Object.entries(x.touched||{}).map(([k,v])=>`${v} touch ${words(+k)} ${+k===1?'copy':'copies'}`).join(', ');
 el.innerHTML=orient(`Every cheapest way a thief can get in, for one lock, and which parts of the chip those ways use.`,`A part used by many ways in is a weak spot. If every way in has to touch all copies, the copies are doing their job.`,`Pick another lock below. Press <b>Recount</b> to list every way in again on this computer.`)+
  `<div class="panel"><div class="pb"><div class="lbl">Lock</div>${segBtns('sfsel',D.map(z=>[z.id,T(z.plain,z.tech)]),x.id)}</div></div>
  <div class="panel"><div class="sentence">${sent}</div><div class="pb rowflex">${lv?hon(lv.src==='cached'?'cached':'live')+` <span class="hint">recounted here: ${lv.v[1]} ways with ${gl(lv.v[0])} ${lv.v[1]===c&&lv.v[0]===m?'<b class="okc">✓ same as recorded</b>':'<b class="badc">≠ differs from the recorded '+c+'</b>'}</span>`:hon('recorded')} <span class="sp"></span>${liveBtn('surface','Recount every way in','Lists every cheapest attack again on this computer by trying every combination (no solver needed).')}</div></div>
  <div class="cols"><div class="panel"><div class="ph"><h4>Weak spots: the parts used most</h4></div><div class="pb">${bars||'<div class="note">No ways in, so no weak spots to show.</div>'}</div>
   <div class="cap"><b class="w">How to read this.</b> Each bar is one part of the chip; its length is how many of the ${tot} cheapest ways in use it. The colour and the words both say which copy it belongs to; letters (gate A, gate B) tell apart different parts of the same copy.</div></div>
   <div><div class="panel"><div class="ph"><h4>Which copies the glitches land in</h4></div><div class="pb">${cps.length?`<div class="sbar2">${share}</div><p class="hint" style="margin-top:8px">${touched?'Of the ways in: '+esc(touched)+'.':''}</p>`:'<div class="note">Nothing to show.</div>'}</div></div>
   <div class="panel"><div class="ph"><h4>Are the copies kept apart?</h4><span class="sp"></span>${ll?hon(ll.src==='cached'?'cached':'live'):lintRec?hon('recorded'):''}</div><div class="pb">${lintV?`<div class="big2">${esc((LV[lintV]||[lintV])[0])}</div><p>${esc((LV[lintV]||['',''])[1])}</p>`:'<p class="hint">Not checked yet for this lock.</p>'}
    <div class="rowflex">${liveBtn('lint','Check now','Reads the chip plan and checks whether the copies share any wire. Takes well under a second per lock.')}</div></div>
    <div class="cap"><b class="w">What this means.</b> ${d.lint&&d.lint.confusion?`Across ${Object.values(d.lint.confusion).reduce((a,b)=>a+b,0)} saved chip plans: whenever the copies were merged, one glitch was enough (${d.lint.confusion['lint merged, min 1']} of ${d.lint.confusion['lint merged, min 1']+d.lint.confusion['lint merged, min > 1']}). Kept-apart copies usually needed more, but not always (${d.lint.confusion['lint not merged, min 1']} of ${d.lint.confusion['lint not merged, min 1']+d.lint.confusion['lint not merged, min > 1']} still fell to one glitch, because of a code choice). So "kept apart" is necessary, not sufficient.`:''}</div></div></div></div>
  ${learn('Learn more (technical details)',`<div class="kv2"><div>chip plan</div><div class="mono">${esc(x.netlist)} · sha256 ${esc(x.sha)}…</div><div>bound</div><div class="mono">k ≤ ${x.max_faults}, T = ${x.cycles}, goal boot_word == 0x96, single-cycle bit flips of gate outputs and flop Q</div><div>method</div><div>exhaustive simulation, ${(x.sets||0).toLocaleString('en-US')} fault sets over ${x.sites} sites, ${x.runtime_s} s; complete: ${x.complete}</div><div>example attacks</div><div class="mono">${(x.examples||[]).map(a=>a.faults.map(f=>f[0]+'@'+f[1]).join(' + ')).join('<br>')}</div><div>lint</div><div>${esc(lintRec?lintRec.mode+' mode, '+lintRec.single+' single points'+(lintRec.first&&lintRec.first.length?', first: '+lintRec.first.join(', '):''):'n/a')}</div><div>source</div><div class="mono">${esc(x.file)} (${esc(x.when||'')})</div><div>limits</div><div>${esc(x.note||'')}</div></div>`)}${srcLine(d)}`;
 onSeg('sfsel',v=>{S.sv=v;viewSurface(el)});wireLive(el,()=>viewSurface(el))}

/* 2. Suggest a fix */
const FIXT={'State encoding':'Change a stored pattern','More compare copies':'Add copies of the check','Voter placement':'Move the point where the copies are combined','Sparse state word as output':'Use the stored pattern itself as the answer','Invalid state goes to reject':'Shut the lock when its memory is garbled','Check copy with infection / alarm latch':'Add an alarm for when the copies disagree'};
const fixTitle=t=>t.split(' + ').map(x=>FIXT[x]||x).join(' + ');
const FIXN={'V2 synthesised flatten-first (copies merged by abc)':'Three copies, in a chip plan where the copies got merged','V2 with a shared input buffer stage':'Three copies that share their key-input wires','stored V2, consumer checks only bits 0x8D':'Three copies, but the rest of the chip reads only 4 of the 8 answer signals','stored V2, consumer checks only the low nibble':'Three copies, but the rest of the chip reads only the lower half of the answer','apt 0.33 V2: no shared copy logic, nothing to remove':'Three copies, chip plan made by an older build tool (the copies are already apart)'};
const fixStep=s=>/Consumer checks/.test(s.title)?'Make the rest of the chip read the whole answer':s.skipped?'Nothing to separate: no part is shared':/Remove single points/.test(s.title)?'Give each copy its own parts instead of shared ones':s.title;
const FIXW={'accept code word':'the pattern for Open','reject code word':'the pattern for Shut','state width (bits)':'how many memory cells hold the lock’s state','boot_word source':'where the answer comes from','voter placement':'where the copies are combined','armed code word':'the pattern the lock holds while checking','idle code word':'the pattern the lock holds while waiting','compare copies that own bits':'number of copies of the check','bit ownership (bit 7..0 -> copy)':'which copy controls which part of the answer',
 'invalid state':'what happens when the lock’s memory is garbled','voter':'the single point that combines the copies','state word':'the lock’s memory','alarm':'an alarm that rejects when copies disagree','consumer checks':'how much of the answer the rest of the chip reads'};
const DESN={v0:'Lock with one check',v1:'Lock with two checks joined by one wire',v2:'Lock with three copies',v2e:'Three copies, one pattern changed'};
async function viewFix(el){const d=await getMod('harden');const p=modProblem(d,'The fix-finder module');if(p){el.innerHTML=p;return}
 const des=[...new Set(d.cards.map(c=>c.design))];if(!S.fd||!des.includes(S.fd))S.fd=des.includes('v2')?'v2':des[0];const cards=d.cards.filter(c=>c.design===S.fd);
 const best=cards.find(c=>c.reached)||cards[0],sg=best&&best.suggestions&&best.suggestions[0];
 const chg=s=>tech()?(s.changes||[]).map(c=>`${esc(c.what)}: <span class="mono">${esc(c.before)} → ${esc(c.after)}</span>`).join('; '):'What changes: '+esc([...new Set((s.changes||[]).map(c=>FIXW[c.what]||'a design detail'))].join('; '))+'.';
 const cost=c=>{if(!c)return '';const g=c.gates,parts=tech()?`${g>0?'+':''}${g} gates`:g<0?`none (${g===-1?'one part':(-g)+' parts'} fewer)`:g===0?'no extra parts':`${g} extra parts`;return `${parts}${c.flops?`, ${c.flops>0?'+':''}${c.flops} memory cells`:''}${c.latency_cycles?`, ${c.latency_cycles} extra steps`:', no extra steps'}`};
 const own2=S.fd==='v2'&&best&&+best.before_min_flips!==3;
 const today=best?`${T(own2?'In the fix-finder’s own arrangement of this lock, a thief needs':'Today a thief needs','Baseline minimum:')} <b>${gl(+best.before_min_flips)}</b>.`:'';
 const sent=best?(best.reached&&sg?`${today} The cheapest change we found raises that to <b>${sg.after_min_flips}</b>: ${T(esc(fixTitle(sg.title).toLowerCase()),esc(sg.title))}${sg.cost?`. Cost: ${cost(sg.cost)}`:''}.`
   :`${today} No change in the list reached ${best.goal_min_flips} glitches.`):'No suggestions for this lock.';
 const goals=cards.map(c=>`<div class="panel"><div class="ph"><h4>Goal: at least ${gl(c.goal_min_flips)}</h4><span class="sp"></span>${c.reached?'<span class="okc" style="font-weight:600;font-size:12px">✓ reached</span>':'<span class="warnc" style="font-size:12px">not reached</span>'}</div>
  ${(c.suggestions||[]).slice(0,3).map((s,i)=>`<div class="sug"><div class="ba"><span class="bn">${esc(c.before_min_flips)}</span><span class="arr">→</span><span class="bn hi">${esc(s.after_min_flips)}</span></div><div><b>${i===0?'Best: ':''}${esc(T(fixTitle(s.title),s.title))}</b><div class="hint">${chg(s)}</div>
   <div class="hint">Cost: ${cost(s.cost)}. ${s.if_copies_merged?`<span class="warnc">If the build tool merges the copies again, this drops back to ${gl(+s.if_copies_merged)}.</span>`:''}</div>
   <div class="tech-only hint">${esc((s.plain||[]).join(' '))} · per mapping: ${esc(Object.entries(s.per_mapping||{}).map(e=>e.join(' ')).join(', '))} · Yosys: ${esc(s.yosys||'')}</div></div><div style="text-align:right">${hon('recorded','Checked by trying every combination of glitches on three gate arrangements of the changed design.',true)}${s.yosys==='UNTESTED-HERE'?'<br>'+ntag(T('not yet made into a chip plan','not yet synthesised'),'The changed design was checked on gate arrangements written by the fix-finder, not yet on a plan made by the build tool.'):''}</div></div>`).join('')||'<div class="note">No suggestion for this goal.</div>'}</div>`).join('');
 const nf=(d.netlist_fixes||[]).map(f=>`<tr><td>${T(esc(FIXN[f.note]||'Another chip plan of the three-copy lock'),`<span class="mono">${esc(f.netlist)}</span><br>${esc(f.note||'')}`)}</td><td>${esc(f.before_min_flips)} → <b>${esc(f.after_min_flips)}</b>${f.reached===false||f.reached==='False'?' <span class="hint">(goal not reached)</span>':''}</td><td>${esc((f.steps||[]).map(s=>tech()?s.title:fixStep(s)).join('; '))}</td></tr>`).join('');
 el.innerHTML=orient(`For one lock, the cheapest design changes that make a thief need more glitches, and what each change costs.`,`The before → after numbers come from trying every combination of glitches on the changed design. A fix is only real if the copies stay apart when the chip is built.`,`Pick a lock. Open <b>Learn more</b> for the exact changes and files.`)+
  `<div class="panel"><div class="pb"><div class="lbl">Lock</div>${segBtns('fxsel',des.map(z=>[z,T(DESN[z]||z,z.toUpperCase())]),S.fd)}</div><div class="sentence">${sent}</div><div class="cap">${T('These are computer models of small example locks. The “after” numbers were checked on gate arrangements written by the fix-finder; a fix still has to be made into a chip plan by the build tool and checked again. Not a security proof.'+(own2?' The starting number is for the fix-finder’s own arrangement of the three-copy lock, which is why it says 2 here while the first chip plan on the path needs 3.':''),esc(d.banner||''))}</div></div>
  <div class="fgrid">${goals}</div>
  <div class="panel"><div class="ph"><h4>Fixes for chip plans that already exist</h4></div><table><thead><tr><th>Chip plan</th><th>Glitches needed</th><th>Change</th></tr></thead><tbody>${nf}</tbody></table>
   <div class="cap"><b class="w">What this means.</b> When the build tool has merged the copies, giving each copy its own parts again brings the protection back. When the rest of the chip reads only part of the answer, making it read all of it does.</div></div>
  ${learn('Learn more (technical details)',`<p class="hint">Labels in the source file: ${esc(Object.entries(d.labels||{}).map(e=>e.join(' = ')).join(' · '))}</p><div class="kv2">${(best&&best.suggestions||[]).map(s=>`<div>${esc(s.title)}</div><div class="mono">${esc(JSON.stringify(s.changes))} · files: ${esc(Object.values(s.files||{}).join(', ')||'none')}</div>`).join('')}<div>source</div><div class="mono">${esc(d.file)} (${esc(d.when||'')})</div></div>`)}${srcLine(d)}`;
 onSeg('fxsel',v=>{S.fd=v;viewFix(el)})}

/* 3. Forever check */
async function viewForever(el){const d=await getMod('unbounded');const p=modProblem(d,'The forever-proof module');if(p){el.innerHTML=p;return}
 if(!S.find)await loadFindings();const all=!!S.ubAll,D=d.designs.filter(x=>all||x.main),K=[0,1,2,3];
 const v2=d.designs.find(x=>x.id==='v2_stored');
 const cell=(x,k)=>{const v=x.verdicts[String(k)],lv=liveOf(`forever|${x.id}|${k}`);const pr=v==='PROVED_UNBOUNDED',at=v==='ATTACK_FOUND';
  const live=lv?` <span class="lvm">re-checked here ${lv.v===v?'✓':'≠'}</span>`:'';
  return `<td class="fcell ${pr?'pr':at?'at':'un'}" data-tip="${esc(pr?`Proved: no thief with ${k} or fewer glitches ever gets in, however many steps they wait.`:at?`A thief with ${gl(k)} gets in.`:'No result.')}${lv?' Re-checked on this computer: '+(lv.v===v?'same answer.':'DIFFERENT answer.'):''}">${pr?'✓ never':at?'⚡ gets in':'?'}${live}</td>`};
 const sent=v2?`For the lock with three copies, we <b>proved</b> that no thief with ${max0(v2.proved)} or fewer glitches can ever get in, <b>however long they wait</b>, as long as the chip starts normally and each glitch hits one wire for one step. With ${gl(v2.attack)} they can.`:'';
 el.innerHTML=orient(`For each lock, whether a thief with a given number of glitches can <b>ever</b> get in, not just within a few steps.`,`✓ never means proved for any waiting time, but only for this one chip plan, this kind of glitch and a normal start. It does not mean “safe for good”. ⚡ means a way in exists. The other pages only look a few steps ahead.`,`Press <b>Prove again</b> to redo the proofs on this computer, or show every chip plan.`)+
  `<div class="panel"><div class="sentence">${sent}</div><div class="pb rowflex">${hon('proved')}${(()=>{const L=Object.entries(S.live).filter(([k,v])=>k.startsWith('forever|')&&v.state==='ok');if(!L.length)return '';const same=L.filter(([k,v])=>v.cmp==='match').length,src=L.some(([k,v])=>v.src==='live')?'live':'cached';
  return ` ${hon(src,null,true)} <span class="hint">re-proved on this computer: <b class="${same===L.length?'okc':'badc'}">${same} of ${L.length} give the same answer${same===L.length?' ✓':''}</b></span>`})()} <span class="sp"></span>${liveBtn('forever','Prove again on this computer','Re-runs the proofs for the locks shown with a small built-in solver; each takes about a second.')}<label class="chk"><input type="checkbox" id="uball" ${all?'checked':''}> show every chip plan (${d.designs.length})</label></div></div>
  <div class="panel"><table class="ftab"><thead><tr><th>Lock</th>${K.map(k=>`<th>with ${gl(k)}</th>`).join('')}<th>Fewest glitches to get in</th></tr></thead><tbody>${D.map(x=>`<tr><td>${T(esc(x.plain),`<span class="mono">${esc(x.id)}</span><br><span class="m mono">${esc(x.netlist||'')}</span>`)}</td>${K.map(k=>cell(x,k)).join('')}<td><b>${x.attack??'more than '+max0(x.proved)}</b></td></tr>`).join('')}</tbody></table>
  <div class="cap"><b class="w">What this means.</b> For every lock here, waiting longer never helps the thief: the fewest glitches for all time equal the fewest within 6 steps. <b class="w">What “proved” assumes.</b> ${esc(PROVED_ASSUME)} If a thief could also scramble the start state, one glitch would be enough for every lock.</div></div>
  ${learn('Learn more (technical details)',`<div class="kv2"><div>tool</div><div class="mono">${esc(d.tool)} · backend ${esc(d.backend)}</div><div>methods</div><div>explicit reachability, k-induction with simple-path constraints, IC3; a verdict is given only when all three agree; every proof certificate and attack is re-checked</div><div>scope</div><div>${esc((v2&&v2.note)||'')}</div><div>consistency</div><div>${esc(JSON.stringify(d.consistency||'').slice(0,300))}</div><div>source</div><div class="mono">${esc(d.file)} (${esc(d.when||'')})</div></div>`)}${srcLine(d)}`;
 $('#uball').onchange=e=>{S.ubAll=e.target.checked;viewForever(el)};wireLive(el,()=>viewForever(el))}
const max0=a=>a&&a.length?Math.max(...a):0;

/* 4. Glitch shots on the chip layout */
const r2=v=>Math.round(v*100)/100;
function shotsAt(steps,r){let v=null;for(const s of steps||[]){if(s.r_from<=r+1e-9)v=s;}return v}
async function viewShots(el){const d=await getMod('shots');const p=modProblem(d,'The glitch-shots module');if(p){el.innerHTML=p;return}
 if(!S.shd)S.shd='v2';const x=d.designs.find(z=>z.id===S.shd)||d.designs[0];const grid=(x.steps||{})['centre/grid']||{steps:[]},cellSt=(x.steps||{})['centre/cell']||{steps:[]};
 const atks=(x.attacks||[]).filter(a=>a.rule==='centre');if(S.sha==null||S.sha>=atks.length)S.sha=Math.max(0,atks.findIndex(a=>a.n_shots===1));
 const a=atks[S.sha]||null,at05=shotsAt(grid.steps,0.5),one=(grid.steps.find(s=>s.min_shots===1)||{}).r_from;
 const sent=at05&&one!=null?`With a very small laser spot (0.5 µm radius) a thief needs <b>${at05.min_shots} shot${at05.min_shots===1?'':'s'}</b>. From a ${one} µm radius, <b>one shot</b> is enough${x.id==='v2'?', because the three copies sit right next to each other on the chip':''}.`:'No shot data for this layout.';
 const lg=x.cells.filter(c=>c.r!=='physical'),bx0=Math.min(...lg.map(c=>c.x))-1.5,by0=Math.min(...lg.map(c=>c.y))-1.5,bx1=Math.max(...lg.map(c=>c.x+c.w))+1.5,by1=Math.max(...lg.map(c=>c.y+c.h))+1.5;
 const x0=bx0,y0=by0,x1=bx1,y1=by1,W=560,sc=Math.min(W/(x1-x0),290/(y1-y0)),H=(y1-y0)*sc,Y=v=>H-(v-y0)*sc;
 const role=c=>{const m=c.n.match(/^c(\d)\//);return m?'c'+m[1]:c.r};
 const cells=x.cells.map(c=>{const g=role(c),fill=/^c\d$/.test(g)?`color-mix(in srgb,var(--${g}) 45%,transparent)`:c.r==='flop'?'color-mix(in srgb,var(--warn) 35%,transparent)':c.r==='physical'?'transparent':'color-mix(in srgb,var(--shared) 25%,transparent)';
  const hit=a&&a.shots.some(s=>s.cells.includes(c.n));return `<rect x="${(c.x-x0)*sc}" y="${Y(c.y+c.h)}" width="${c.w*sc}" height="${c.h*sc}" fill="${fill}" stroke="${hit?'var(--hot)':'var(--line)'}" stroke-width="${hit?2.5:.6}" data-tip="${esc((/^c\d$/.test(g)?'part of copy '+(+g[1]+1):c.r==='flop'?'a memory cell of the lock':c.r==='physical'?'filler (no logic)':'shared logic')+(hit?': hit by a shot':''))}" data-tipm="${esc(c.n+' '+(c.m||''))}"/>${/^c\d$/.test(g)&&c.w*sc>9?`<text x="${(c.x-x0+c.w/2)*sc}" y="${Y(c.y+c.h/2)+4}" font-size="11" font-weight="700" text-anchor="middle" pointer-events="none">${+g[1]+1}</text>`:''}`}).join('');
 const discs=a?a.shots.map((s,i)=>`<circle cx="${(s.x-x0)*sc}" cy="${Y(s.y)}" r="${Math.max(4,s.r*sc)}" fill="color-mix(in srgb,var(--hot) 22%,transparent)" stroke="var(--hot)" stroke-width="2" stroke-dasharray="${s.r?'':'3 2'}"/><text x="${(s.x-x0)*sc}" y="${Math.max(12,Y(s.y)-Math.max(4,s.r*sc)-4)}" font-size="12" text-anchor="middle" fill="var(--hot)" font-weight="700" stroke="var(--inset)" stroke-width="3" paint-order="stroke">shot ${i+1}</text>`).join(''):'';
 const svg=`<svg viewBox="0 0 ${(x1-x0)*sc} ${H}" width="100%" style="max-width:${(x1-x0)*sc}px;display:block;margin:auto;background:var(--inset);border-radius:6px;overflow:visible" role="img" aria-label="Chip layout with the cells of each copy and the shot positions">${(x.rows||[]).map(r=>`<line x1="0" x2="${W}" y1="${Y(r.y)}" y2="${Y(r.y)}" stroke="var(--line)" stroke-dasharray="2 4"/>`).join('')}${cells}${discs}</svg>`;
 const rs=[...new Set(grid.steps.flatMap(s=>[s.r_from]))];const maxR=Math.min(10,Math.max(...grid.steps.map(s=>s.r_from))+2);
 const CW=520,CH=150,cx=r=>40+r/maxR*(CW-60),cy=n=>CH-24-(n||0)*30;
 const path=(st,col,dash)=>{let dd='',prev=null;const pts=[];for(let r=0;r<=maxR+1e-9;r+=0.05){const s=shotsAt(st,r);if(!s||s.min_shots==null)continue;pts.push([r,s.min_shots])}pts.forEach(([r,n],i)=>{dd+=(i?`H${cx(r)}V${cy(n)}`:`M${cx(r)},${cy(n)}`)});return `<path d="${dd}" fill="none" stroke="${col}" stroke-width="2.5" ${dash?'stroke-dasharray="5 4"':''}/>`};
 const chart=`<svg viewBox="0 0 ${CW} ${CH}" width="100%" style="max-width:${CW}px" role="img" aria-label="Fewest shots needed against spot radius">${[1,2,3].map(n=>`<line x1="40" x2="${CW-20}" y1="${cy(n)}" y2="${cy(n)}" stroke="var(--line)"/><text x="30" y="${cy(n)+4}" font-size="12" text-anchor="end" class="m">${n}</text>`).join('')}
  ${[0,1,2,4,6,8,10].filter(r=>r<=maxR).map(r=>`<text x="${cx(r)}" y="${CH-6}" font-size="12" text-anchor="middle" class="m">${r}</text>`).join('')}<text x="${CW-20}" y="${CH-6}" font-size="12" text-anchor="end" class="m">spot radius (µm)</text>
  ${path(grid.steps,'var(--acc)')}<line x1="${cx(.5)}" x2="${cx(.5)}" y1="10" y2="${CH-24}" stroke="var(--warn)" stroke-dasharray="3 3"/><text x="${cx(.5)+4}" y="18" font-size="11.5" fill="var(--warn)">small published laser spot</text><text x="8" y="14" font-size="12" class="m">shots</text></svg>`;
 const vt=d.designs.map(z=>{const g=(z.steps||{})['centre/grid'];const o=g&&(g.steps.find(s=>s.min_shots===1)||{}).r_from;return `<tr><td>${T(esc(z.plain),`<span class="mono">${esc(z.id)}</span>`)}</td><td>${o===0?'<b>any size</b> (one part is enough)':o==null?'–':`<b>${r2(o)}</b> µm`}</td><td>${g&&shotsAt(g.steps,0.5)?shotsAt(g.steps,0.5).min_shots:'–'}</td></tr>`}).join('');
 el.innerHTML=orient(`The real placed layout of a lock on a chip (seen from above), and where a laser or electromagnetic pulse would have to hit to open it.`,`A real pulse disturbs everything inside a small spot. If the copies sit close together, one bigger spot hits all of them at once, and the extra copies stop helping.`,`Pick a layout, then step through the example attacks. The chart shows how the number of shots drops as the spot gets bigger.`)+
 `<div class="panel"><div class="pb"><div class="lbl">Layout</div>${segBtns('shsel',d.designs.map(z=>[z.id,T(z.plain,z.id)]),x.id)}</div><div class="sentence">${sent}</div><div class="pb rowflex">${hon('simulated','The positions come from the real placed layout; the shot model (a disc that upsets every cell whose centre is inside it) is an assumption.')}</div></div>
 <div class="cols"><div class="panel"><div class="ph"><h4>The chip layout, seen from above</h4><span class="sp"></span>${atks.length?`<button class="btn" id="shp" ${S.sha?'':'disabled'} aria-label="previous example attack">←</button><span class="hint">example ${S.sha+1} of ${atks.length}</span><button class="btn" id="shn" ${S.sha<atks.length-1?'':'disabled'} aria-label="next example attack">→</button>`:''}</div><div class="pb">${svg}
  <div class="legend" style="margin-top:8px">${[0,1,2].map(i=>`<span><i class="sq" style="background:color-mix(in srgb,var(--c${i}) 45%,transparent);border:1px solid var(--line2)"></i>copy ${i+1}</span>`).join('')}<span><i class="sq" style="background:color-mix(in srgb,var(--warn) 35%,transparent)"></i>memory cell</span><span><i class="sq" style="background:color-mix(in srgb,var(--shared) 25%,transparent)"></i>shared logic</span><span><i class="sq" style="border:2px solid var(--hot)"></i>hit by a shot (red outline)</span></div></div>
  <div class="cap">${a?`<b class="w">This example:</b> ${a.n_shots} shot${a.n_shots===1?'':'s'} with a spot radius of ${r2(a.shots[0].r)} µm${a.r_last_um>a.r_from_um?` (works from ${r2(a.r_from_um)} to ${r2(a.r_last_um)} µm)`:''}, all at step ${[...new Set(a.shots.map(s=>s.cycle))].join(' and ')}. The lock then shows "open" for a wrong key${a.flop_only_replay_ok?' (re-checked)':''}.`:'No example attack stored for this layout.'}</div></div>
  <div><div class="panel"><div class="ph"><h4>Fewest shots needed, by spot size</h4></div><div class="pb">${chart}</div><div class="cap">The thief may aim anywhere. A larger spot reaches more of the chip at once, so fewer shots are needed.</div></div>
  <div class="panel"><div class="ph"><h4>Does placing the copies apart help?</h4></div><table class="notx"><thead><tr><th>Layout</th><th>One shot works from</th><th>Shots with a 0.5 µm spot</th></tr></thead><tbody>${vt}</tbody></table><div class="cap">Pinning the copies apart pushes the one-shot spot size up several times.${(()=>{const os=id=>{const z=d.designs.find(q=>q.id===id),g=z&&(z.steps||{})['centre/grid'];return g&&(g.steps.find(s=>s.min_shots===1)||{}).r_from};const a8=os('v2_v8'),a15=os('v2_v15');return a8!=null&&a15!=null&&a15<a8?` Further apart is not automatically better: the layout pinned 15 µm apart gives way to one shot from ${r2(a15)} µm, earlier than the one pinned 8 µm apart (${r2(a8)} µm). We have not analysed why.`:''})()}</div></div></div></div>
 ${learn('Learn more (technical details)',`<div class="kv2"><div>model</div><div>${jt(d.model)}</div><div>labels</div><div>${jt(d.labels)}</div><div>one-shot radius (µm)</div><div class="mono">${jt(x.one_shot)}</div><div>input files</div><div class="mono keep">${jt(x.files)}</div><div>spot sizes</div><div>${(x.sources||[]).map(s=>esc(s.id+' ('+s.label+')')).join(', ')}</div><div>not placed</div><div>${esc((d.unplaced||[]).join(', '))}</div><div>source</div><div class="mono">${esc(x.file)} · ${esc(d.generated||'')}</div></div>`)}${srcLine(d)}`;
 onSeg('shsel',v=>{S.shd=v;S.sha=null;viewShots(el)});if($('#shp'))$('#shp').onclick=()=>{S.sha--;viewShots(el)};if($('#shn'))$('#shn').onclick=()=>{S.sha++;viewShots(el)}}

/* 5. Virtual glitch lab */
async function viewVlab(el){const d=await getMod('vlab');const p=modProblem(d,'The virtual glitch lab');if(p){el.innerHTML=p;return}
 if(!S.vd)S.vd='v2';const x=d.designs.find(z=>z.id===S.vd)||d.designs[0];const tot=x.cells.reduce((s,c)=>[s[0]+c[2],s[1]+c[3],s[2]+c[4]],[0,0,0]),all=tot[0]+tot[1]+tot[2];
 const P=x.periods,O=x.offsets,cw=Math.max(4,Math.min(7,560/P.length)),ch=22,W=60+P.length*cw,H=O.length*ch+40;
 let g='';x.cells.forEach(c=>{const i=P.indexOf(c[1]),j=O.indexOf(c[0]);const n=c[2]+c[3]+c[4];const s=c[2],cr=c[3];const fill=s?'var(--hot)':cr===n?'url(#hatch)':cr?'color-mix(in srgb,var(--mut) 45%,transparent)':'var(--raised)';
  g+=`<rect x="${60+i*cw}" y="${10+j*ch}" width="${cw-.5}" height="${ch-2}" fill="${fill}" data-tip="${esc(`glitch at step ${c[0]}, clock step shortened to ${Math.round(c[1])} ps: ${s} wrong keys accepted, ${cr} crashes, ${c[4]} no effect (of ${n} keys)`)}"/>`});
 O.forEach((o,j)=>g+=`<text x="54" y="${10+j*ch+15}" font-size="12" text-anchor="end" class="m">step ${o}</text>`);
 const svg=`<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="Grid of glitch timings and outcomes"><defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="color-mix(in srgb,var(--mut) 30%,transparent)"/><line x1="0" y1="0" x2="0" y2="6" stroke="var(--mut)" stroke-width="2"/></pattern></defs>${g}
  <text x="60" y="${H-8}" font-size="12" class="m">very short clock step</text><text x="${W}" y="${H-8}" font-size="12" text-anchor="end" class="m">normal length →</text></svg>`;
 const sent=`We shortened one clock step by ${P.length} different amounts, at ${O.length} different moments, for all 256 keys. A wrong key was accepted <b>${tot[0]===0?'not once':tot[0]+' times'}</b>${tot[1]?`; cutting the step too short made the chip crash instead (${tot[1].toLocaleString('en-US')} of ${all.toLocaleString('en-US')} tries)`:''}.`;
 el.innerHTML=orient(`A software lab that glitches the real layout of a lock by making one tick of its clock too short, the way a real clock-glitch attack does.`,`Each square is one timing tried on all 256 keys. Red would mean a wrong key got in; hatched means the chip crashed; plain means nothing happened. This is a different kind of glitch from the one-wire glitch on the other pages, so the numbers can differ.`,`Switch between the two locks. Open <b>Learn more</b> for the timing model.`)+
 `<div class="panel"><div class="pb"><div class="lbl">Lock</div>${segBtns('vlsel',d.designs.map(z=>[z.id,T(z.id==='v1'?'Lock with two checks':'Lock with three copies',z.id.toUpperCase())]),x.id)}</div><div class="sentence">${sent}</div><div class="pb rowflex">${hon('simulated','Timing delays are an assumed model, not measured.')}</div></div>
 <div class="panel"><div class="ph"><h4>Every glitch timing tried</h4></div><div class="pb" style="overflow:auto">${svg}<div class="legend" style="margin-top:6px"><span><i class="sq" style="background:var(--hot)"></i>wrong key accepted (${tot[0]})</span><span><i class="sq" style="background:url(#hatch);border:1px solid var(--mut);background:repeating-linear-gradient(45deg,var(--mut),var(--mut) 2px,transparent 2px,transparent 5px)"></i>chip crashed (all keys)</span><span><i class="sq" style="background:color-mix(in srgb,var(--mut) 45%,transparent)"></i>some keys crashed</span><span><i class="sq" style="background:var(--raised);border:1px solid var(--line2)"></i>no effect</span></div></div>
 <div class="cap"><b class="w">What this means.</b> ${x.engine_min!=null?`In the one-wire glitch model this lock falls to ${gl(x.engine_min)}; with clock glitches on this layout, ${x.glitch&&x.glitch.glitch_realizable_wrong_key_accept?'a way in was found':'no way in was found in this sweep'}. That is a result of this sweep and its assumed delays, not a proof for a real chip.`:''}</div></div>
 ${learn('Learn more (technical details)',`<div class="kv2"><div>delay model</div><div>${esc(JSON.stringify(x.delay_model))}</div><div>flop arrival (ps)</div><div class="mono">${esc(JSON.stringify(x.sta))}</div><div>supply droop</div><div>${(x.derate||[]).map(r=>`derate ${r.derate}: ${esc(JSON.stringify(r.counts))}`).join('<br>')}</div><div>flop-only minimum</div><div>${esc(x.flop_min)} flops in one cycle (abstract model)</div><div>honesty</div><div>${esc(x.honesty)}</div><div>source</div><div class="mono">${esc(x.file)} · ${esc(x.when||'')} · ${x.runtime_s} s</div></div>`)}${srcLine(d)}`;
 onSeg('vlsel',v=>{S.vd=v;viewVlab(el)})}

/* 6. Firmware secure boot */
const FWN={rom_naive:'Simple: one check each',rom_double:'Every check done twice',rom_triple:'Every check done three times',rom_compl:'Checks kept with their opposite',rom_ctres:'Careful compare plus a second count',rom_cfi:'Counts its own steps',rom_delay:'Random pauses',rom_infective:'Wrong result scrambles the jump',rom_hardened:'All protections combined'};
async function viewFirmware(el){const q=S.fw||(S.fw={variant:'rom_naive',opt:'O0',mode:'plain'});const d=await getMod('firmware',`&variant=${q.variant}&opt=${q.opt}&mode=${q.mode}`);const p=modProblem(d,'The firmware module');if(p){el.innerHTML=p;return}
 const cell=d.cells.find(c=>c.variant===q.variant&&c.opt===q.opt&&c.mode===q.mode)||{},per=cell.tampered_per_model||{},src=d.source||{};
 const MP={skip:'skip one instruction',brinv:'make a decision go the wrong way',rdflip:'flip one bit in a working register',pcoff:'make the program jump a few bytes',iwflip:'corrupt one instruction as it is read'};
 const num=v=>v==null?null:/^\d+$/.test(v)?+v:null;const best=Object.entries(per).map(([k,v])=>[k,num(v),v]).filter(e=>e[1]!=null).sort((a,b)=>a[1]-b[1])[0];
 const sent=best?`This boot program can be fooled into running a tampered program with <b>${gl(best[1])}</b>${best[1]===1?`: ${MP[best[0]]} is enough`:` (the cheapest kind: ${MP[best[0]]})`}.`:`No attack with the glitches searched (${esc(Object.values(per).join(', '))}).`;
 const marks=src.marks||{};const code=(src.lines||[]).map((l,i)=>{const m=marks[String(i+1)];const mk=m?Object.keys(m).map(k=>`<span class="fm" data-tip="${esc((m[k].multi?'Part of a cheapest multi-glitch attack: ':'One glitch here works: ')+(MP[k]||k)+(m[k].effect?' ('+m[k].effect+')':''))}" data-tipm="${esc((m[k].asm||[]).join(' ; '))}">⚡${k==='skip'?'S':k==='brinv'?'B':k==='rdflip'?'R':k==='pcoff'?'J':'I'}</span>`):[];
  return `<div class="cl${m?' mk':''}"><span class="ln">${i+1}</span><span class="mk2">${mk.length>2?`<span class="fmx" tabindex="0" aria-label="${mk.length} kinds of glitch work on this line">⚡×${mk.length}<span class="fmall">${mk.join('')}</span></span>`:mk.join('')}</span><code>${esc(l)||' '}</code></div>`}).join('');
 el.innerHTML=orient(`The small program that runs first when a chip powers up and decides whether the main program is genuine, with the lines where a glitch lets a tampered program through.`,`A glitch can also hit software: it can skip one instruction or make a decision go the wrong way. Lines marked ⚡ are where it works. Protected versions need more glitches.`,`Pick a version of the program. Hover a ⚡ to see what the glitch does there.`)+
 `<div class="panel"><div class="pb"><div class="lbl">Program version</div>${segBtns('fwsel',d.variants.map(v=>[v.id,T(FWN[v.id]||v.id,v.id)]),q.variant)}<div class="tech-only" style="margin-top:8px;display:flex;gap:12px"><span class="lbl">compiler</span>${segBtns('fwopt',d.opts.map(o=>[o,o]),q.opt)}<span class="lbl">mode</span>${segBtns('fwmode',d.modes.map(o=>[o,o]),q.mode)}</div></div>
  <div class="sentence">${sent}</div><div class="pb rowflex">${hon('simulated','Run on an instruction simulator of a small processor, not on a chip.')}<span class="hint">${esc((d.variants.find(v=>v.id===q.variant)||{}).description||'')}</span></div></div>
 <div class="cols"><div class="panel"><div class="ph"><h4>The program, with glitch spots</h4><span class="sp"></span><span class="hint keep mono">${esc(src.variant||'')}.c</span></div><div class="code keep">${code||'<div class="note">The source file was not found in the module.</div>'}</div>
  <div class="cap"><b class="w">How to read this.</b> ⚡S skip an instruction · ⚡B decision goes the wrong way · ⚡R one bit of a register changed · ⚡J small jump · ⚡I instruction corrupted. ⚡×3 means three kinds work on that line: point at it (or Tab to it) to see which. Letters and words carry the meaning, not only colour. The word <span class="keep mono">SRC</span> in the listing is part of the program as written (a macro that stands for <span class="keep mono">const</span>, or <span class="keep mono">const volatile</span> in the volatile build); nothing was replaced.</div></div>
  <div><div class="panel"><div class="ph"><h4>Fewest glitches, by kind of glitch</h4></div><table><tbody>${Object.entries(per).map(([k,v])=>`<tr><td>${esc(T(MP[k]||k,(d.model_text||{})[k]||k))}</td><td><b>${esc(v)}</b></td></tr>`).join('')}</tbody></table><div class="cap">“&gt;3” means no attack with 3 or fewer glitches of that kind. Each kind was searched on its own.</div></div>
  <div class="panel"><div class="ph"><h4>Same idea in hardware</h4></div><table><thead><tr><th>Hardware lock</th><th>Glitches</th><th>Program version</th></tr></thead><tbody>${((d.hardware_compare||{}).rows||[]).map(r=>`<tr><td>${esc(T(DESN[r.design.toLowerCase()]||r.what,r.design+' · '+r.what))}</td><td>${esc(tech()?r.min_flips:r.min_flips.split(' ')[0])}</td><td>${esc(T(FWN[r.firmware_counterpart]||r.firmware_counterpart,r.firmware_counterpart))}</td></tr>`).join('')}</tbody></table><div class="cap">The units differ (one wire versus one instruction), so compare the pattern, not the numbers.</div></div></div></div>
 ${learn('Learn more (technical details)',`<div class="kv2"><div>build</div><div class="mono">${esc(src.build)} · ${src.searches} searches read</div><div>platform</div><div>${esc(d.platform)}</div><div>caption</div><div>${esc(d.caption)}</div><div>witness</div><div class="mono">${esc(JSON.stringify(cell.witness||[]))}</div><div>notes</div><div>${esc((d.notes||[]).join(' '))}</div><div>source</div><div class="mono">${esc(d.file)} · ${esc(src.file)}</div></div>`)}${srcLine(d)}`;
 onSeg('fwsel',v=>{q.variant=v;viewFirmware(el)});onSeg('fwopt',v=>{q.opt=v;viewFirmware(el)});onSeg('fwmode',v=>{q.mode=v;viewFirmware(el)})}

/* 7. Our secure-boot hardware */
const SBP={sparse:'unusual codes for its states',single:'one check of the fingerprint',separate:'copies kept apart',dup:'two checks joined by one part',inline:'copies the build tool may merge',trip:'three checks, each controls part of the answer',
 compl:'one normal and one inverted check',mubi:'4-signal yes/no codes',alarm:'an alarm for impossible states',cfi:'a step counter that notices skipped steps',otp1:'the expected fingerprint kept in one place',otp2:'the expected fingerprint kept once per check',
 infect:'a wrong fingerprint scrambles the release token',hash:'computes the program’s fingerprint in hardware',hash2:'two separate fingerprint engines'};
async function viewSecboot(el){const d=await getMod('secboot_hw');const p=modProblem(d,'The secure-boot hardware module');if(p){el.innerHTML=p;return}
 const run=d.cards.filter(c=>c.status!=='NOT_RUN'),nr=d.cards.length-run.length;
 const res=c=>{const r=(c.results||{}).plain||{},b=(r.by_k||[]).find(x=>x.verdict==='ATTACK_FOUND');return c.status==='NOT_RUN'?'<span class="hint">no result yet</span>':c.status==='FAILED'?'<span class="badc">failed</span>':b?`<b>${gl(b.min_faults)}</b>`:`<b>more than ${d.kmax}</b>`};
 const sent=run.length?`${run.length} of ${d.cards.length} protected versions have results so far.`:`Our own boot-check hardware is ready in ${d.cards.length} protected versions, but <b>none has been checked yet</b>: the check needs a longer run on a computer with the build tool and solver. Until then no numbers are shown, and nothing is guessed.`;
 el.innerHTML=orient(`A real boot-check circuit built for this project: it reads a program, computes its fingerprint, compares it, and says open or shut. Each protection can be switched on or off.`,`Each card is one protected version and what its protection is meant to do. The glitch count appears here once the run has been done.`,run.length?`Read the cards; each says how many glitches it needs.`:`Nothing to do here yet. ${d.cloud_script?`<span class="tech-only">The run is started with <span class="keep mono">${esc(d.cloud_script)}</span>.</span>`:''}`)+
 `<div class="panel"><div class="sentence">${sent}</div><div class="pb rowflex">${run.length?hon('recorded'):''}<span class="hint tech-only">${esc(d.banner||'')}</span></div>${(()=>{const g=S.gal&&(S.gal.examples||[]).find(x=>x.id==='secure_boot');if(!g||!g.runs.length)return '';
   return `<div class="cap"><b class="w">Already analysed elsewhere.</b> Two small configurations of this same circuit have saved results in the example gallery: ${g.runs.map(r=>`${esc(galLabel(r.label))}: <b>${r.verdict==='ATTACK_FOUND'?gl(r.min_faults):'no way in with up to '+r.max_faults}</b>`).join('; ')}. They were computed by the own-design tool, not by the long run this page waits for. <button class="linkb" data-go="x-gal">Example gallery</button></div>`})()}</div>
 <div class="sbgrid">${d.cards.map((c,i)=>`<div class="panel sbc"><div class="ph"><h4>${T('Version '+(i+1)+(c.slow?' (long run)':''),`<span class="mono">${esc(c.name)}</span>`)}</h4><span class="sp"></span>${res(c)}</div><div class="pb"><div class="tags">${(c.countermeasures||[]).map(m=>`<span class="tag">${esc(tech()?m.text:SBP[m.id]||plainText(m.text))}</span>`).join('')}</div>${c.design_intent?`<p class="hint"><b>Meant to:</b> ${esc(tech()?c.design_intent:plainText(c.design_intent))}</p>`:''}<p class="hint tech-only mono">${esc(c.experiment.top)} · goal ${esc(c.experiment.goal)} · ${c.experiment.cycles} cycles${c.slow?' · slow':''}</p></div></div>`).join('')}</div>${srcLine(d,d.when?'file from '+d.when:'')}`}

/* 8. Evidence report and margin */
async function viewEvidence(el){const d=await getMod('product');const p=modProblem(d,'The evidence-report module');if(p){el.innerHTML=p;return}
 if(!S.evd)S.evd='v2';const x=d.designs.find(z=>z.id===S.evd)||d.designs[0];if(!x){el.innerHTML='<div class="empty"><b>No example reports found</b>Generate them with the evidence-example command of the product, then reload.</div>';return}
 const rows=x.rows||[];if(S.evr==null||S.evr>=rows.length)S.evr=rows.findIndex(r=>/spike|given|stored/i.test(r.name||''));if(S.evr<0)S.evr=0;const r=rows[S.evr]||{};const lv=(r.psa_levels||{})[String(r.target)]||{};
 const sent=r.psa_total!=null?`Rough estimate: the cheapest attack on this lock would score about <b>${r.psa_total} points</b> on the scale test labs use (more points = a harder attack). For a level ${r.target} product, any attack scoring ${lv.ceiling} points or less counts as realistic, so ${lv.in_scope?`<b>this lock would need more protection</b> to reach level ${r.target}`:`this attack is <b>too hard to count</b> at level ${r.target}: on this estimate it does not stand in the way of that level`}.`:'No rating for this chip plan.';
 el.innerHTML=orient(`A ready-made report that turns “how many glitches” into the points that security test labs use, with every assumption written down. The scale is the one of PSA Certified, a security-certification scheme for chips.`,`More points means a harder attack. Each level says up to how many points an attack still counts as realistic; a product must stop every attack at or below that number. The score is an <b>estimate</b> from published tables, not a lab rating.`,`Pick a lock, read the sentence, then open the full report.`)+
 `<div class="panel"><div class="pb"><div class="lbl">Lock</div>${segBtns('evsel',d.designs.map(z=>[z.id,T(DESN[z.id]||z.id,z.id.toUpperCase())]),x.id)}${rows.length>1?`<div class="lbl" style="margin-top:8px">Chip plan</div>${segBtns('evrow',rows.map((z,i)=>[String(i),T(/opt/.test(z.name)?'made again, tidied first':/plain/.test(z.name)?'made again, as written':'first (saved)',z.name)]),String(S.evr))}`:''}</div>
  <div class="sentence">${sent}</div><div class="pb rowflex">${hon('estimate')}<span class="hint">The glitch count behind it is a recorded result. ${esc(r.disclaimer||'')}</span></div></div>
 <div class="cols"><div class="panel"><div class="ph"><h4>How the estimate changes with one assumption</h4></div><table><thead><tr><th>Assumption</th><th>Pulses needed</th><th>Points</th></tr></thead><tbody>${(r.sensitivity||[]).map(s=>`<tr><td>${tech()?esc(s.assumption):/=any/.test(s.assumption)?'One pulse can cause all the glitches of one step':/=1\b/.test(s.assumption)?'Every glitch needs its own pulse':esc(s.assumption.replace(/\s*\(.*\)$/,''))}</td><td>${s.events}</td><td><b>${s.psa}</b></td></tr>`).join('')}</tbody></table><div class="cap">Glitches needed: ${r.min_faults??'none found'}. ${tech()?esc(r.headline||''):''}</div></div>
  <div class="panel"><div class="ph"><h4>Levels: does this attack count?</h4></div><table><thead><tr><th>Level</th><th>Attacks count up to</th><th>This attack (${r.psa_total??'?'} points)</th></tr></thead><tbody>${Object.entries(r.psa_levels||{}).map(([k,v])=>`<tr><td>level ${k}</td><td>${v.ceiling} points</td><td>${v.in_scope?'<b class="warnc">counts: must be prevented</b>':'<span class="okc">too hard to count (fine)</span>'}</td></tr>`).join('')}</tbody></table><div class="cap">A higher level counts harder attacks as realistic, so the same attack can be fine at a low level and a problem at a high one.</div></div></div>
 <div class="panel"><div class="ph"><h4>The full report</h4><span class="sp"></span>${x.html?`<a class="btn" href="${esc(x.html)}" target="_blank" rel="noopener">Open in a new window</a>`:''}</div>${x.html?`<iframe class="evf" src="${esc(x.html)}" title="Evidence report for ${esc(x.id)}" loading="lazy"></iframe>`:'<div class="note">The HTML report was not found next to the margin file.</div>'}</div>${srcLine(d,x.file)}`;
 onSeg('evsel',v=>{S.evd=v;S.evr=null;viewEvidence(el)});onSeg('evrow',v=>{S.evr=+v;viewEvidence(el)})}

/* 9. Real designs (OpenTitan blocks): GlitchSAT next to an existing published tool (SYNFI) on the same chip plans */
async function viewReal(el){const d=await getMod('real');if(d&&d.missing){el.innerHTML=orient('The same checks on a real, open-source security chip design (OpenTitan).','Nothing yet: the module is not in this project folder.','Nothing to do here yet.')+modProblem(d,'The real-designs module');return}
 const p=modProblem(d,'The real-designs module');if(p){el.innerHTML=p;return}
 const E=d.experiments||[],F=d.fsm||[];
 const A=d.adapter_all,grd=A?`<p class="hint" style="margin:0 2px 10px"><b>Groundwork.</b> Before any of this, the translation of the chip’s standard parts into GlitchSAT’s own parts was checked against their definitions (${fmtN(A.truth_table_rows)} rows for ${A.cell_pins} part outputs) and against a second simulator (${fmtN(A.cosim_comparisons||0)} comparisons): <b>${(A.cosim_mismatches||0)+(A.engine_sim_mismatches||0)} mismatches</b>.</p>`:'';
 if(!E.length&&!F.length){el.innerHTML=orient(`The place where results on a real, open-source security chip design (OpenTitan) will appear.`,`No results exist yet. Nothing is shown until they do, and nothing is estimated in the meantime.`,`Nothing to do here yet.`)+
  `<div class="empty coming"><b>Coming: real chip designs</b>The same questions (how many glitches, where, and whether the copies survive the build tool) asked of blocks from a real open-source security chip.</div>${grd}${srcLine(d,(d.files||[]).length?'files so far: '+d.files.join(', '):'no files yet')}`;return}
 const RN={E1:'Encryption engine, round counter without protection: make it count wrong',E2:'Encryption engine, round counter without protection: force one exact value',E3:'Encryption engine, round counter with three protected copies: make it count wrong without setting off the alarm',E4:'Small processor: change which instruction runs next',E5:'Small processor: force one exact next instruction'};
 const AG=d.agree,ui=d.under_investigation,e1=E.find(e=>e.id==='E1'),e3=E.find(e=>e.id==='E3');
 const sent=AG?`On blocks of a real open-source security chip, GlitchSAT gave <b>the same answer as an existing published tool on ${AG[0]===AG[1]?'all '+fmtN(AG[1]):fmtN(AG[0])+' of '+fmtN(AG[1])} glitch attempts compared</b>.${e1&&e1.flip!=null?` A counter without protection fell to <b>${gl(e1.flip)}</b>`+(e3&&e3.flip!=null?`; the version with three protected copies needed <b>${e3.flip}</b>.`:'.'):''}${ui?' One published figure is not matched exactly; that row is marked <span class="uinv">under investigation</span>.':E.some(e=>e.status==='differs')?' One published figure differs slightly; the existing tool’s own program gives our number on the public chip plan (see the last row).':''}`:'Results on real chip blocks are in; no comparison with the published tool was stored.';
 const pubCell=e=>{const pb=e.pub||{},h=e.here||{},kw=pb.faults===2?'two-glitch':'single-glitch';
  if(e.status==='reproduced')return `<b class="okc">✓ same as published</b><br><span class="hint">${h.percent}% of ${fmtN(h.injected)} ${kw} attempts work, here and in the paper</span>`;
  if(e.status==='different_plan')return T(`<span class="hint">not comparable: the published number was made from a different chip plan (another build tool)</span>`,`<span class="hint">not comparable: paper used ${esc(pb.flow||'another flow')}; paper ${pb.percent}% of ${esc(pb.total)} at ${pb.faults} fault(s)</span>`);
  if(e.status==='differs'){const rc=d.recon&&d.recon.id===e.id?d.recon:null,nums=`here ${fmtN(h.effective)} of ${fmtN(h.injected)} ${kw} attempts work; the paper reports ${pb.eff!=null?(pb.eff_approx?'about ':'')+fmtN(pb.eff)+' of ':''}${esc(pb.total)}${pb.eff==null?' attempts, '+pb.percent+'%':''}.`;
   if(!d.reconciled)return `<span class="uinv">under investigation</span><br><span class="hint">${nums} Close, not equal; the cause is not known yet.</span>`;
   return `<b class="okc">reconciled</b>: close, not equal, and checked<br><span class="hint">${nums}${rc?` The existing tool counts every pair of glitches twice; counted once, that is ${fmtN(rc.here.effective)} of ${fmtN(rc.here.sets)} pairs here and ${fmtN(rc.paper.effective)} of ${fmtN(rc.paper.sets)} in the paper. The existing tool’s own program, run on this public chip plan, builds the same ${fmtN(rc.here.sets)} pairs${rc.confirmed&&rc.confirmed[0]===rc.confirmed[1]?` and confirms all ${rc.confirmed[0]} that work`:''}. The paper’s figure cannot be reproduced from the public files.`:' The module’s notes give the details.'}</span>`}
  return '<span class="hint">no published figure to compare</span>'};
 const agCell=e=>e.agree?`<b class="n ${e.agree[0]===e.agree[1]?'okc':'badc'}">${fmtN(e.agree[0])} of ${fmtN(e.agree[1])}</b>${e.agree[0]===e.agree[1]?' ✓':''}`:'–';
 const W=d.whole,LN=d.lint,prot=F.find(f=>f.rails>1);
 el.innerHTML=orient(`The same glitch checks, run on blocks of a real open-source security chip (OpenTitan), next to an existing published tool (${T('called SYNFI','SYNFI, lowRISC')}) that was given the same blocks.`,`Both tools were asked the same yes-or-no question about every glitch attempt: does it work? They gave the same answer every time. So GlitchSAT is not only right on its own small example locks. It is still a computer model: no real chip was glitched.`,ui?`Read the table. One row is marked <b>under investigation</b>: there a published figure is close to ours, not equal.`:`Read the table. In the last row a published figure is close to ours, not equal; the row says what was checked. <b>Learn more</b> has the sources.`)+
 `<div class="panel"><div class="sentence">${sent}</div><div class="pb rowflex">${hon('recorded')}<span class="hint">· results as of ${esc((d.experiments_when||'').slice(0,10))}</span></div></div>
 ${E.length?`<div class="panel"><div class="ph"><h4>Same blocks, two tools</h4></div><table class="rtab"><thead><tr><th>${T('Block, and what the thief wants','Experiment')}</th><th>${T('Fewest glitches (GlitchSAT)','Min faults: bit flip / gate replacement')}</th><th>${T('Ways in with that many','Minimum attacks (bit flip)')}</th><th data-tip="The existing tool was run here unchanged on its own examples. Every glitch attempt it made was also given to GlitchSAT.">${T('Attempts where both tools agree','Per-injection agreement with SYNFI')}</th><th>${T('Published figure','SYNFI paper figure')}</th></tr></thead><tbody>${E.map(e=>`<tr><td>${T(esc(RN[e.id]||plainText(e.title.replace(/\s*\([A-Z]{2}\)\s*$/,''))),`<b>${esc(e.id)}</b> ${esc(e.title)}`)}</td><td><b class="n">${e.flip??'–'}</b>${tech()?' / '+(e.synfi??'–'):''}</td><td>${e.surface?fmtN(e.surface.attacks)+(e.surface.complete?'':' or more'):'–'}</td><td>${agCell(e)}</td><td>${pubCell(e)}</td></tr>`).join('')}</tbody></table>
  <div class="cap"><b class="w">What this means.</b> As with the small example locks, the counter without protection falls to a single glitch and the protected counter needs two. In the small processor, changing the next instruction in some way takes one glitch; forcing one exact instruction takes two. “Attempts where both tools agree” counts the glitch attempts (single glitches and pairs) that the existing tool made on its own examples and that GlitchSAT judged too. The published figures come from that tool’s paper; three of them were made from a different chip plan and cannot be compared. Each number holds for one chip plan, one goal and a short time window.</div></div>`:''}
 <div class="cols"><div class="panel"><div class="ph"><h4>What GlitchSAT adds</h4></div><div class="pb"><ul style="margin:0;padding-left:18px;color:var(--mut);line-height:1.55">
  <li>The existing tool tries a fixed number of glitches and reports how many attempts work. GlitchSAT gives the <b style="color:var(--txt)">fewest glitches</b> directly and lists every way in of that size.</li>
  ${W?`<li>For the small processor, the question was also asked of the <b style="color:var(--txt)">whole block over ${W.cycles} steps</b>, not just a cut-out region: still <b style="color:var(--txt)">${gl(W.min_faults)}</b>${W.attacks?` (${fmtN(W.attacks)} ways in${W.complete?', all listed':''})`:''}.</li>`:''}
  ${LN&&LN.cross===0?`<li>The three protected copies <b style="color:var(--txt)">stayed apart</b> when the chip plan was made: no part of one copy feeds another. What they share is shared by design.</li>`:''}</ul></div>
  <div class="cap"><b class="w">Limits.</b> Modelled glitches on chip plans, not a measured chip. Solver-based glitch analysis is not new; the existing tool does it too. This is a reproduction on real blocks, plus the fewest-glitches number.</div></div>
 ${F.length?`<div class="panel"><div class="ph"><h4>${T('Making the encryption engine jump between its states','AES control FSM: forbidden state transitions')}</h4></div><table><thead><tr><th>Version</th><th>Time window</th><th>${T('Jumps tried','State pairs')}</th><th>Fewest glitches (any part)</th><th>${T('Fewest glitches (memory cells only)','Min faults (state flops only)')}</th></tr></thead><tbody>${F.map(f=>`<tr><td>${T(f.rails>1?'three protected copies':'one copy',`<span class="mono">${esc(f.experiment)}</span>`)}${f.second_solver?'<br><span class="hint" data-tip="The same run was repeated with a second, independent solver and gave the same numbers.">checked with a second program ✓</span>':''}</td><td>${f.cycles} steps</td><td>${f.summary?f.summary.pairs:'–'}</td><td><b>${f.summary&&f.summary.min_all!=null?f.summary.min_all:'none found'}</b></td><td>${f.summary&&f.summary.min_state_flops!=null?f.summary.min_state_flops:'none found up to '+f.kmax}</td></tr>`).join('')}</tbody></table>
  <div class="cap">The engine stores its state so that a thief must change at least 3 memory cells to reach another valid state. That holds, but one glitch in the logic around the memory can be enough. “None found up to N” is the limit of the search, not a guarantee.</div></div>`:''}</div>
 ${grd}${learn('Learn more (technical details)',`<div class="kv2">${E.map(e=>`<div>${esc(e.id)}</div><div class="mono">${esc(e.title)}<br>${esc(e.netlist)} · k1 ${e.k1}% · k2 ${e.k2??'–'}% (distinct injections)${e.published?'<br>'+esc(e.published.citation||'')+' '+esc(e.published.where||'')+': '+esc(e.published.setting)+', '+e.published.effective_percent+'% of '+esc((e.pub||{}).total||'?')+' at '+e.published.simultaneous_faults+' fault(s); flow: '+esc((e.pub||{}).flow||''):''}${e.rerun?`<br>SYNFI re-run here (1 fault): ${e.rerun.effective_percent}% effective`:''}</div>`).join('')}${F.map(f=>`<div>${esc(f.file)}</div><div>${esc(f.model)} · ${esc(JSON.stringify(f.summary))}</div>`).join('')}<div>about</div><div>${esc(d.about||'')}</div><div>unmatched figure</div><div>${d.reconciled?'reconciled in the module README (“E5 reconciliation”) and results/e5_reconciliation.json: SYNFI counts 2 per fault set; SYNFI’s own enumeration on the public netlist gives the same number of sets as here; the paper’s figure is not reproducible from the public files':'not reconciled in the module README; shown as under investigation'}</div><div>schema</div><div class="mono">${esc(d.schema||'')}</div></div>`)}${srcLine(d,'files: '+(d.files||[]).join(', '))}`}

const ICON={spots:'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="9" cy="10" r="2.5" fill="var(--hot)"/><circle cx="15" cy="15" r="1.6" fill="var(--warn)"/></svg>',
 fix:'<svg viewBox="0 0 24 24"><path d="M14 4l6 6-9 9H5v-6z" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',forever:'<svg viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8.5 12.5l2.5 2.5 4.5-5" fill="none" stroke="var(--ok)" stroke-width="1.8"/></svg>',
 shots:'<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="5" fill="none" stroke="var(--hot)" stroke-width="1.8"/><circle cx="12" cy="12" r="1.5" fill="var(--hot)"/></svg>',
 lab:'<svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 3 12 2-6h7" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',fw:'<svg viewBox="0 0 24 24"><path d="M8 7l-5 5 5 5M16 7l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
 hw:'<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3" stroke="currentColor" stroke-width="1.4"/></svg>',
 rep:'<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9 12h7M9 16h7" stroke="currentColor" stroke-width="1.4"/></svg>',real:'<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-dasharray="3 3"/><path d="M12 8v4l3 2" stroke="currentColor" stroke-width="1.6" fill="none"/></svg>'};
/* ================= UT2: "How would you fix it?" (for chip designers) =================
   One closed line in Plain view, open in Technical view. Plain sentences first; the exact tool words sit in a .keep block
   so the Plain view never rewrites them. Evidence lines are read from data the app already has; nothing is invented. */
const FIX_LEAD={one:'This lock has one check, so one glitch decides. The first fix is a change to the design: more than one copy of the check, and no single wire that decides. “Suggest a fix” lists changes that were checked on this lock. After that, four things keep a protection alive:',
 shared:'Both copies report into one wire that the designer drew, and that wire alone decides. No build setting repairs this. Change the design so that each copy controls its own part of the answer and the rest of the chip reads all of it (path step 3). Then keep it that way:',
 sep:'Nothing to fix on this chip plan: the copies are apart and each one needs its own glitch. The work now is to keep it that way through the build and on the chip:',
 merge:'The written design is the same as in step 3. The build tool rearranged the logic, so fewer glitches are enough. Fix the build, not the idea:',
 enc:'Changing one stored pattern brought this chip plan back up. That is the second remedy below. It helps only while the copies are still apart, so the other three still matter:',
 flag:'The copies are intact, but the rest of the chip reads one signal, and that signal is a single point. Make the reader use every copy’s output (the whole answer). No build setting repairs a single point. For the copies themselves:',
 held:'No way in was found within the limits, so there is nothing to fix here. To keep the protection through the build and on the chip:',
 spots:'A part that most of the cheapest ways in use is a single point. If several copies share it, give each copy its own. If the build tool created it, stop the merge:',
 fix:'The changes on this page are changes to the design. In your own project they last only if the build keeps them. Four things to set in your flow:',
 place:'On this page the weakness is physical: copies that sit side by side fall to one spot. The third remedy below is the one that answers it; the other three make sure the copies are still there to be placed.',
 fw:'In a boot program the compiler plays the part of the build tool: it can see three identical checks and keep one. The fourth remedy below is the one for software.',
 real:'These blocks come from a chip whose designers already use the four remedies below; its public source is a good place to see them written out.',
 gal:'The gallery shows the pattern in small: a protection that is in the written design can be missing after the build. Four ways to keep it:'};
const FIX_HI={merge:[0,3],sep:[0],held:[0],enc:[1],place:[2],fw:[3],spots:[0],fix:[0,1],gal:[0],one:[],shared:[],flag:[],real:[]};
const numOf=v=>typeof v==='number'?v:null;
function fixEvidence(){const ev=['','','',''],G0=S.gal&&S.gal.examples||[];
 const hl=G0.find(x=>x.id==='hello_lock'),hr=hl&&hl.runs.find(r=>r.survival&&'synth-keep' in r.survival);
 if(hr){const sv=hr.survival,say=v=>numOf(v)!=null?`needs <b>${gl(v)}</b>`:`holds against ${gl(hr.max_faults)}`;
  ev[0]=`<b>Seen here</b> ${hon('recorded',null,true)}: the protected hello lock ${say(sv.plain)} when built as written, ${say(sv.synth)} when the build tool tidies across the copies, and ${say(sv['synth-keep'])} again when each copy is kept as its own block. <button class="linkb" data-go="x-gal">Example gallery</button>`}
 else{const v=S.find&&S.find.synth&&S.find.synth.designs&&S.find.synth.designs.v2;if(v&&v.min)ev[0]=`<b>Seen here</b> ${hon('recorded',null,true)}: of ${v.solved} ways of building the three-copy lock, ${v.min[1]} need only 1 glitch. <button class="linkb" data-go="studies">Studies</button>`}
 const a=S.tourRes[3],b=S.tourRes[4];ev[1]=typeof a==='number'&&typeof b==='number'&&b>a?`<b>Seen here</b>: on the path, step 4 needs ${a} and step 5, with one pattern changed, needs ${b}, on that one chip plan. Not a general fix. <button class="linkb" data-go="p4">path step 5</button>`:`<b>Seen here</b>: path step 5 changes one stored pattern and builds again. <button class="linkb" data-go="p4">path step 5</button>`;
 const sh=S.mods&&S.mods.shots,os=id=>{const z=sh&&sh.designs&&sh.designs.find(q=>q.id===id),g=z&&(z.steps||{})['centre/grid'];return g&&(g.steps.find(s=>s.min_shots===1)||{}).r_from};
 const o0=os('v2'),o8=os('v2_v8'),o15=os('v2_v15');
 ev[2]=o0!=null&&o8!=null?`<b>Seen here</b> ${hon('simulated',null,true)}: with the copies side by side, one shot is enough from a ${r2(o0)} µm spot; pinned 8 µm apart, from ${r2(o8)} µm.${o15!=null&&o15<o8?` Further apart was not automatically better (15 µm apart: ${r2(o15)} µm), so check the result, do not assume it.`:''} <button class="linkb" data-go="x-shots">Laser shots on the chip</button>`:`<b>Seen here</b>: the laser page compares layouts with the copies side by side and pinned apart. <button class="linkb" data-go="x-shots">Laser shots on the chip</button>`;
 const fw=S.mods&&Object.keys(S.mods).filter(k=>k.startsWith('firmware')).map(k=>S.mods[k]).find(d=>d&&d.cells),cell=m=>fw&&fw.cells.find(c=>c.variant==='rom_triple'&&c.opt==='O2'&&c.mode===m),sk=c=>c&&c.tampered_per_model&&/^\d+$/.test(c.tampered_per_model.skip||'')?+c.tampered_per_model.skip:null;
 const p=sk(cell('plain')),vv=sk(cell('vol')),bb=sk(cell('barrier'));
 ev[3]=p!=null&&vv!=null&&p<vv?`<b>Seen here</b> ${hon('simulated',null,true)}: the boot program with every check done three times, compiled with strong optimisation, falls to ${p} skipped instruction${p===1?'':'s'}; with volatile reads it needs ${vv}${bb!=null?`, with barriers ${bb}`:''}. <button class="linkb" data-go="x-fw">Boot program</button>`:`<b>Seen here</b>: the boot-program page has the same checks compiled plain, with volatile reads and with barriers (Technical view). <button class="linkb" data-go="x-fw">Boot program</button>`;
 return ev}
function fixHTML(kind,open){const ev=fixEvidence(),hi=FIX_HI[kind]||[];
 const C=[['Keep the copies','keep / dont_touch','Tell the build tool not to merge or tidy the copies: build each copy as its own block and mark it “keep”.',
   'Yosys: one module per copy with <code>(* keep_hierarchy *)</code>, or <code>synth</code> without <code>-flatten</code> and flatten only after optimisation; <code>(* keep *)</code> on each copy’s output wires. Commercial flows: <code>set_dont_touch</code> on the copy instances and their output nets.'],
  ['Choose the encoding','state codes','Store each state as a pattern that differs from the others in several places, and stop the tool from choosing new patterns.',
   'Write the state codes yourself, so that any two valid codes differ in at least one more bit than the number of faults you want to resist (OpenTitan calls this sparse FSM encoding and asks for a large distance). Yosys: <code>synth -nofsm</code> or <code>(* fsm_encoding = "none" *)</code> on the state register; commercial flows: switch FSM re-encoding off for that register. Measure the distance in the netlist, not in the RTL.'],
  ['Place the copies apart','placement','On the chip, put the copies in separate areas, so one laser spot or one local dip in power cannot reach all of them.',
   'Floorplan: one placement region per copy (DEF <code>REGIONS</code> / <code>GROUPS</code>; commercial flows: placement bounds) with other logic in between. Carry the dont_touch through placement and timing optimisation, which can also merge or clone cells.'],
  ['Barriers the optimiser cannot see through','hardware and compiler','Put a marked part between each copy and the place where the copies are combined, so the optimiser cannot work out that two copies are equal and join them.',
   'Hardware: a hand-instantiated buffer or flip-flop marked keep / <code>size_only</code> between each copy and the combine point (OpenTitan: <code>prim_buf</code>, <code>prim_flop</code>, <code>prim_sec_anchor_buf</code>). Boot program in C: <code>volatile</code> reads, or pass the value through an empty <code>asm</code> statement (OpenTitan: <code>launder32()</code>, <code>barrier32()</code>, <code>HARDENED_CHECK_EQ()</code>).']];
 return `<details class="more learn fixit" ${open?'open':''}><summary>How would you fix it? <span class="hint">for chip designers: what to change in the design and in the build</span></summary><div class="pb">
 <p class="fxlead">${FIX_LEAD[kind]||FIX_LEAD.gal}</p>
 <div class="fxgrid">${C.map((c,i)=>`<div class="fxc${hi.includes(i)?' hi':''}"><h5>${i+1}. ${c[0]}${hi.includes(i)?ntag('most relevant here','Of the four remedies, this one answers what this page shows.','mut'):''}</h5><p>${c[2]}</p><div class="tt keep"><b>In tool words (${c[1]}):</b> ${c[3]}</div>${ev[i]?`<div class="ev">${ev[i]}</div>`:''}</div>`).join('')}</div>
 <p class="hint" style="margin:8px 0 0"><b style="color:var(--txt)">Then check again.</b> A remedy in the written design is not evidence. It counts once the final chip plan, after the build and after placement, has been analysed again. These four are standard practice, named so you can look them up; the tool words are examples, not a full recipe, and this app has not tested them on your flow.
 <button class="linkb" data-go="x-fix">Suggest a fix</button> lists the design changes that were checked on the example locks${typeof Studio!=='undefined'&&Studio.projectLink?' · '+Studio.projectLink():''}.</p></div></details>`}
const fixHost=kind=>`<div class="fxhost" data-fx="${kind}"></div>`;
function fixKindOf(r){const fam=((S.lastQ&&S.lastQ.design)||'').replace(/_rtl$/,'');if(r.verdict!=='ATTACK_FOUND')return 'held';if(r._goal==='flag')return 'flag';if(fam==='v0')return 'one';if(fam==='v1')return 'shared';
 if(fam==='v2e')return r.min_faults>=3?'enc':'merge';return r.min_faults<3?'merge':'sep'}
let fixAsked=false;
function fillFix(root,again){(root||document).querySelectorAll('.fxhost').forEach(h=>{if(h.dataset.done&&!again)return;const d=h.querySelector('details'),open=d?d.open:tech();h.dataset.done='1';h.innerHTML=fixHTML(h.dataset.fx,open);
  h.querySelector('details').addEventListener('toggle',e=>{if(e.target.open&&!fixAsked){fixAsked=true;Promise.all([getMod('shots'),getMod('firmware','&variant=rom_triple&opt=O2&mode=plain')]).then(()=>fillFix(document,true))}})})
 if(tech()&&!fixAsked&&(root||document).querySelector('.fxhost')){fixAsked=true;Promise.all([getMod('shots'),getMod('firmware','&variant=rom_triple&opt=O2&mode=plain')]).then(()=>fillFix(document,true))}}
Studio.fixHost=fixHost;
const XFIX={'x-spots':'spots','x-fix':'fix','x-shots':'place','x-fw':'fw','x-real':'real','x-gal':'gal'};

/* small readable table instead of raw JSON in “Learn more” */
function jt(o,depth){if(o==null)return '<span class="hint">n/a</span>';if(typeof o!=='object')return esc(String(o));depth=depth||0;
 if(Array.isArray(o))return o.every(x=>x==null||typeof x!=='object')?esc(o.join(', ')):depth>2?esc(JSON.stringify(o)):o.map(x=>jt(x,depth+1)).join('');
 return depth>3?esc(JSON.stringify(o)):`<table class="jt">${Object.entries(o).map(([k,v])=>`<tr><td>${esc(k.replace(/_/g,' '))}</td><td>${jt(v,depth+1)}</td></tr>`).join('')}</table>`}

/* ---- Plain-words findings (shared explainer, findings module): severity first, then what it means, why, where, how sure,
   what to do and how to check, then "How we found it" and "Show technical details" one click away. Used by the path,
   the whole-chip page, the boot program page, the example gallery and the "Open my design" plug-in (Studio.findings). */
const SEVORD=['Critical','High','Medium','Low','Info'];
function sevBadge(s){return `<span class="sev sev-${esc(s.css)}" role="img" aria-label="Severity: ${esc(s.words||s.level)}"><b aria-hidden="true">${esc(s.icon)}</b> ${esc(s.words||s.level)}</span>`}
function findSummary(L){const c={};L.forEach(f=>{c[f.severity.level]=(c[f.severity.level]||0)+1});const parts=SEVORD.filter(k=>c[k]).map(k=>c[k]+' '+k.toLowerCase());
 const top=[...L].sort((a,b)=>b.severity.rank-a.severity.rank)[0];
 return top.severity.level==='Info'?parts.join(', ')+': nothing to fix within the limits that were checked.':`${parts.join(', ')}. Start with the ${top.severity.level.toLowerCase()} one: ${top.statement}`}
function findTimeline(w){if(w.cycle==null)return '';const end=Math.max(w.hit_cycle??w.cycle,w.cycle)+1,N=Math.min(Math.max(end,4),24),x=i=>14+i*(260/(N-1||1));
 let g='';for(let i=0;i<N;i++){const hit=i===w.cycle,goal=i===w.hit_cycle;g+=`<circle cx="${x(i)}" cy="16" r="${hit||goal?6:3}" fill="${hit?'var(--hot)':goal?'var(--warn)':'var(--line2)'}"/>`}
 return `<svg class="ftl" viewBox="0 0 290 40" width="290" height="40" role="img" aria-label="Timeline: the glitch at step ${w.cycle}${w.hit_cycle!=null?', the bad outcome at step '+w.hit_cycle:''}">${g}<text x="${x(w.cycle)}" y="36" font-size="10" text-anchor="middle">glitch, step ${w.cycle}</text>${w.hit_cycle!=null&&w.hit_cycle!==w.cycle?`<text x="${x(w.hit_cycle)}" y="36" font-size="10" text-anchor="middle">outcome</text>`:''}</svg>`}
function findingCard(f,i){const s=f.severity,w=f.where,h=f.how,ti=h.replay||{};
 const tr=(h.trace||[]).length?`<table class="ftrace keep"><thead><tr><th>value</th><th>normal run</th><th>glitched run</th></tr></thead><tbody>${h.trace.map(t=>`<tr><td>${esc(t.name)}</td><td>${esc(t.normal)}</td><td><b>${esc(t.glitched)}</b></td></tr>`).join('')}</tbody></table>`:`<p class="hint">${esc(h.trace_note||'No value trace is stored for this result.')}</p>`;
 const tryit=ti.studio?`<button class="btn" data-ftry="${i}">Replay this step</button> <span class="hint">${esc(h.predict||'')}</span>`:ti.cmd?`<code class="keep">${esc(ti.cmd)}</code>${ti.replayed?' <span class="hint">(the attack was replayed on a simulator and gave the same outcome)</span>':''}`:'<span class="hint">no replay for this result</span>';
 return `<div class="fcard sevb-${esc(s.css)}" data-fid="${esc(f.id)}">
 <div class="fhead">${sevBadge(s)}<b class="fstat">${esc(f.statement)}</b></div>
 ${s.real_life?`<p class="freal"><b>In real life:</b> ${esc(s.real_life)}</p>`:''}<p class="furg"><b>How urgent:</b> ${esc(s.urgency)}</p>
 <details class="more fwhy"><summary>Why it is rated ${esc(s.level)}, and what to do</summary><div class="pb">
  <ul>${s.rationale.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${s.comparison?`<p><b>Real-world comparison:</b> ${esc(s.comparison.text)} <button class="linkb" data-go="learn:${s.comparison.lesson}">Read the story</button></p>`:''}
  <p><b>Why it happened:</b> ${esc(f.why.tag)} ${esc(f.why.title)}. ${esc(f.why.text)}</p><p><b>How sure we are:</b> ${esc(f.sure.plain)}</p>
  <p style="margin-bottom:2px"><b>What to do:</b></p><ul>${f.next.fixes.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p><b>How to check the fix:</b> <code class="keep">${esc(f.next.check_cmd)}</code></p>
  <p class="hint">${esc(s.estimate_note)} <button class="linkb" data-sevrules="1">How we decide severity</button></p></div></details>
 <details class="more fhow"><summary>How we found it</summary><div class="pb">
  <p><b>Where:</b> <span class="keep">${esc(w.text)}</span>${w.missing_note?` <span class="hint">${esc(w.missing_note)}</span>`:''}</p>${(w.context||[]).length?`<pre class="keep fctx">${w.context.map(l=>`<span class="${l.hit?'fhit':''}">${String(l.line).padStart(4)}${l.hit?' ▶ ':'   '}${esc(l.text)}</span>`).join('\n')}</pre>`:''}${findTimeline(w)}
  <ol class="fsteps">${h.steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol>${tr}
  <p><b>Try it yourself:</b> ${tryit}</p><p><b>Spot it next time:</b> ${esc(h.spot_next)}</p>${h.lesson?`<p><button class="linkb" data-go="learn:${h.lesson}">The lesson screen about this</button> · <button class="linkb" data-fgloss="1">Glossary</button></p>`:''}</div></details>
 <details class="more ftech"><summary>Show technical details</summary><div class="pb keep"><table><thead><tr><th>pattern</th><th>in this result</th></tr></thead><tbody>${(f.patterns||[]).map(p=>`<tr><td>${esc(p.tag+' '+p.title)}</td><td>${esc(p.status)}</td></tr>`).join('')}</tbody></table>
  <p class="mono" style="font-size:11.5px">${esc(Object.entries(f.tech||{}).map(([k,v])=>k+' = '+v).join(' · '))}${f.why.evidence?' · evidence: '+esc(f.why.evidence):''}</p></div></details></div>`}
function findingsHTML(L,title){if(!L||!L.length)return '';const s=[...L].sort((a,b)=>b.severity.rank-a.severity.rank);S.fcur=s;
 return `<div class="panel findings" role="region" aria-label="What we found and what it means"><div class="ph"><h4>${esc(title||'What we found and what it means')}</h4></div><div class="pb"><p class="fsum"><b>${esc(findSummary(s))}</b></p>${s.map((f,i)=>findingCard(f,i)).join('')}</div></div>`}
async function sevRules(){const d=S.sevrules||(S.sevrules=await api.get('/api/severity').catch(()=>({missing:true})));if(d.missing){openDlg('How we decide severity','<p>The rule table is not available here.</p>');return}
 openDlg('How we decide severity',`<table class="keep"><tbody>${d.rules.map(r=>`<tr><th style="text-align:left;vertical-align:top">${esc(r[0])}</th><td>${esc(r[1])}</td></tr>`).join('')}</tbody></table><table style="margin-top:10px"><thead><tr><th>level</th><th>how urgent</th></tr></thead><tbody>${[...d.levels].reverse().map(l=>`<tr><td><span class="sev sev-${{Critical:'crit',High:'high',Medium:'med',Low:'low',Info:'info'}[l]}"><b>${esc(d.icons[l])}</b> ${esc(l)}</span></td><td>${esc(d.urgency[l])}</td></tr>`).join('')}</tbody></table>`)}
document.addEventListener('click',e=>{const t=e.target.closest&&e.target.closest('[data-sevrules],[data-ftry],[data-fgloss]');if(!t)return;e.preventDefault();
 if(t.dataset.sevrules)sevRules();else if(t.dataset.fgloss)openHelp('gloss');else if(t.dataset.ftry!=null){if(S.ti>=0){S.predPick[S.ti]=null;loadStep(S.ti)}else run()}});
Studio.findings={html:findingsHTML,card:findingCard,summary:findSummary};

/* 11. Explore a real chip (audit 2-B2): the whole-chip work of the soc module, learner first. Every number is read from
   soc/studio/explore_chip.json. Its results hold within a stated number of clock steps, so they carry the label
   BOUNDED, never PROVED (which in this app means "for any waiting time"). */
const CHIP_PLAIN={picosoc:['PicoSoC with a start check','A small open-source computer on a chip: a processor, a little memory, a serial port and a connection to the memory that holds its program. It has no protection of its own, so this project put a start check in front of it: the chip only starts when an 8-signal code matches a key. There are two versions of that check: one check, and three checks (the same idea as the three-copy lock on the path).'],
 ibex_demo:['Ibex demo system','A small microcontroller chip from lowRISC, built around their Ibex processor, with memory, a serial port and a debug port through which a debugger can take over the processor. There are two versions: as published, and with Ibex’s security setting switched on (a second “shadow” processor runs two steps behind the first, and an alarm goes off when they disagree).']};
const GOAL_PLAIN={boot_release:'The chip starts although the code was wrong.',first_fetch:'The processor starts reading its program although the code was wrong.',
 flash_takeover:'The memory connection is handed to software although no program runs yet.',debug_entry:'The processor switches into debug mode (where whoever controls it can do anything) while nobody is connected.',
 debug_entry_silent:'The same, on the chip with the shadow processor, and its alarm stays quiet.',alarm_suppressed:'The two processor copies disagree, and the alarm stays quiet.'};
const CHIP_BUILD={written:['built as written','written (no optimisation)'],keep:['tidied, each copy kept apart','keep (synthesis, protected blocks kept apart)'],flat:['tidied across everything','flat (synthesis, everything optimised together)']};
const CHIP_VAR={plain:['one check','plain: one comparison, one accept flop'],tmr:['three checks','tmr: three comparators, sparse state codes'],stock:['as published','stock (SecureIbex = 0)'],lockstep:['with the shadow processor and alarm','lockstep (SecureIbex = 1)']};
const LOCKSTEP_NOTE='This shadow-processor version is this project’s own setting of the demo system: it was configured by editing the source for this study. lowRISC does not ship the demo system in this form.';
async function viewChip(el){if(!S.chip)S.chip=await api.get('/api/chip').catch(()=>({error:'offline'}));const d=S.chip;
 if(!d||d.missing||d.broken||d.error){el.innerHTML=orient('Whole open-source chips, asked the same question as the small locks.','Nothing yet: the whole-chip module is not in this project folder.','Nothing to do here yet.')+modProblem(d.missing?{missing:true,looked:d.looked||[]}:d,'The whole-chip module');return}
 const chips=d.chips||[];if(!S.chipSel||!chips.find(c=>c.id===S.chipSel))S.chipSel=(chips.find(c=>c.id==='picosoc')||chips[0]||{}).id;const c=chips.find(x=>x.id===S.chipSel);if(!c){el.innerHTML='<div class="empty"><b>No chip in the file</b></div>';return}
 const CP=CHIP_PLAIN[c.id]||[c.title,''],num=x=>{const n=parseInt(x,10);return String(n)===String(x)?n:null};
 const rows={};(c.variants||[]).forEach(v=>(v.goals||[]).forEach(g=>{(rows[g.id]=rows[g.id]||{title:g.title,cycles:g.cycles,list:[]}).list.push({v,g})}));
 const ord={written:0,keep:1,flat:2},vo={plain:0,tmr:1,stock:0,lockstep:1};
 const goalCard=(gid,r)=>{const L=r.list.sort((a,b)=>(vo[a.v.variant]??9)-(vo[b.v.variant]??9)||(ord[a.v.flow]??9)-(ord[b.v.flow]??9));const lock=L.some(x=>x.v.variant==='lockstep');
  const byVar={};L.forEach(x=>(byVar[x.v.variant]=byVar[x.v.variant]||[]).push(x));
  const tr=Object.entries(byVar).map(([vn,xs])=>{const ns=xs.map(x=>x.g.faults_needed),same=new Set(ns).size===1;
   return `<tr><td>${esc(T((CHIP_VAR[vn]||[vn])[0],(CHIP_VAR[vn]||[vn,vn])[1]))}${vn==='lockstep'?`<div class="chipnote" role="note"><b>Read this first:</b> ${esc(LOCKSTEP_NOTE)}</div>`:''}</td>
    <td>${xs.map(x=>`<div class="chipn"><b>${esc(x.g.faults_needed)}</b> ${num(x.g.faults_needed)!=null?G(num(x.g.faults_needed)):''}<span class="hint"> · ${esc(T((CHIP_BUILD[x.v.flow]||[x.v.flow])[0],(CHIP_BUILD[x.v.flow]||[x.v.flow,x.v.flow])[1]))}</span><span class="tech-only hint"> · slice ${x.g.slice_cells.toLocaleString('en')} of ${x.v.cells.toLocaleString('en')} cells (${x.g.slice_percent} %) · ${x.g.seconds} s</span></div>`).join('')}
    ${!same&&xs.length>2?`<p class="take" style="margin:4px 0 0"><b>Same written design, ${words(xs.length)} ways of building it, ${ns.join(', ')} glitches.</b> Tidying the design can merge the protective copies.</p>`:''}</td></tr>`}).join('');
  return `<div class="panel"><div class="ph"><h4>${esc(T(GOAL_PLAIN[gid]||r.title,r.title))}</h4><span class="sp"></span>${hon('bounded',`Within ${r.cycles} clock steps after the start.`)}</div><div class="pb">
   <table class="chipt"><thead><tr><th>Version</th><th>Glitches needed, within ${r.cycles} steps</th></tr></thead><tbody>${tr}</tbody></table>
   ${lock?'':''}</div></div>`};
 const where=(c.where_security_decisions_live||[]).map(w=>`<li><b>${esc(T(GOAL_PLAIN[w.goal]||w.title,w.title))}</b><span class="tech-only"> ${esc(w.plain)} <span class="keep mono">${esc(w.where)}</span></span></li>`).join('');
 const nr=d.next_rung;
 el.innerHTML=orient(`Two whole open-source chips with tens of thousands of gates each: ${esc(chips.map(x=>(CHIP_PLAIN[x.id]||[x.title])[0]).join(' and '))}. The same question as on the path: how many perfectly-timed glitches turn one of the chip’s security decisions around?`,
   `The numbers hold within a few clock steps after the start, on one way of building each chip. That is why they carry the label ${hon('bounded',null,true)} and not ${hon('proved',null,true)}: nobody checked longer runs. On PicoSoC, look for the row where the same written design gives 3, 2 and 1 glitches.`,
   `Pick a chip. Read what it is, where its security decisions sit, and then what was found. Open “Learn more” for the technical names and sizes.`)+
  `<div class="row" style="margin:0 0 10px">${segBtns('chipsel',chips.map(x=>[x.id,(CHIP_PLAIN[x.id]||[x.title])[0]]),S.chipSel)}</div>
  <div class="panel"><div class="ph"><h4>What this chip is</h4></div><div class="pb"><p style="margin-top:0">${esc(T(CP[1],c.what_this_chip_is))}</p><p class="hint tech-only keep">Source: ${esc(c.source||'')}</p></div></div>
  <div class="panel"><div class="ph"><h4>Where its security decisions live</h4></div><div class="pb"><p style="margin-top:0">A whole chip has tens of thousands of parts, but only a few wires decide questions like “may this chip start?” or “may a debugger take over?”. These are the decisions that were attacked here:</p><ul>${where}</ul></div></div>
  <h3 class="sec">What was found</h3>${findingsHTML(c.findings,'What we found and what it means')}${Object.entries(rows).map(([gid,r])=>goalCard(gid,r)).join('')}
  ${(c.read_with_care||[]).length?`<div class="panel"><div class="ph"><h4>Read with care</h4></div><div class="pb"><ul class="keep">${c.read_with_care.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div>`:''}
  ${learn('Learn more: how these numbers were made, and their limits',`<ul>${(d.intro&&d.intro.limits||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><ul class="tech-only keep">${(c.what_we_found||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p class="tech-only keep">${esc(((d.intro||{}).labels||{}).BOUNDED||'')}</p>`)}
  ${nr?`<div class="panel"><div class="ph"><h4>Next: OpenTitan Earl Grey, a full security chip</h4><span class="sp"></span><span class="hint">no glitch count yet</span></div><div class="pb"><p style="margin-top:0"><b>Read in full, gate step needs a bigger machine.</b> The whole design was read and prepared, but turning it into gates needs more memory than this computer could give, so no glitch count exists for it yet.</p>
   <details class="more"><summary>Learn more: each step and how far it got</summary><table class="keep"><thead><tr><th>step</th><th>result</th><th>time</th><th>memory</th></tr></thead><tbody>${(nr.steps||[]).map(x=>`<tr><td>${esc(x.step)}</td><td>${esc(x.result)}</td><td>${esc(x.wall||'')}</td><td>${esc(x.peak_memory||'')}</td></tr>`).join('')}</tbody></table><p class="keep">${esc(nr.stopped||'')}</p></details></div></div>`:''}
  <div class="fsrc tech-only">data: <span class="keep">${esc(d.file||'')}</span>${d.when?' · file from '+esc(d.when):''} · labels: BOUNDED = exact minimum within T cycles (no unbounded proof)</div>`;
 onSeg('chipsel',v=>{S.chipSel=v;viewChip(el)})}

/* 10. Example gallery: the saved results of the own-design examples. Works with no build tool installed. */
const GALB={plain:['as written','plain'],synth:['tidied across the copies','synth (flatten, full optimisation)'],'synth-keep':['tidied, each copy kept as its own block','synth-keep (per module, then flatten)'],netlist:['the factory cells as given','netlist'],rtl:['the written design','RTL']};
const galTxt=s=>tech()?String(s||''):String(s||'').replace(/flip-flops/g,'memory cells').replace(/flip-flop/g,'memory cell').replace(/\bRedundancy\b/g,'Repeating a check').replace(/\(synth\)/g,'(the tidying one)').replace(/\bcycles\b/g,'steps');
function galSite(s){if(tech())return `<span class="mono keep">${esc(s)}</span>`;let m;
 if((m=/^(\S+) \(.*flip-flop (?:output|stored value)\)$/.exec(s)))return `the memory cell behind <span class="keep">“${esc(m[1])}”</span>`;
 if((m=/^(\S+) \((\w+) gate output\)$/.exec(s)))return `the gate that drives <span class="keep">“${esc(m[1])}”</span>`;
 if((m=/^(\w+) gate #\d+$/.exec(s)))return `a gate inside the circuit (${esc(m[1])})`;return `<span class="keep">${esc(s)}</span>`}
const galLabel=l=>String(l||'').replace(/^\d+\.\s*/,'').replace(/^Run /i,'');
function galRun(r,i,n){const atk=r.verdict==='ATTACK_FOUND',N=r.horizon,ub=r.unbounded||{};
 const ans=atk?`${gl(r.min_faults)} ${r.min_faults===1?'is':'are'} enough`:r.verdict==='NO_ATTACK_UP_TO_BOUND'?`No way in with up to ${gl(r.max_faults)}`:'Not decided';
 const sv=r.survival?Object.entries(r.survival).map(([k,v])=>`<tr><td>${esc(T((GALB[k]||[k])[0],(GALB[k]||[k,k])[1]))}</td><td><b>${numOf(v)!=null?gl(v):v==='NO_ATTACK_UP_TO_BOUND'?'no way in with up to '+r.max_faults:esc(String(v).toLowerCase())}</b></td></tr>`).join(''):'';
 const KN=k=>/^\d+ copies of/.test(k)?`The ${k.match(/^\d+/)[0]} copies of the check`:/^alarm/.test(k)?'The alarm':/^register .* codes/.test(k)?'The spread-out patterns for the lock’s state':/^registers/.test(k)?'The paired step counters':'A protection',KS={rtl:'in the written design',plain:'built as written',synth:'built and tidied','synth-keep':'tidied, each copy kept as its own block',netlist:'in the factory cells'};
 const kp=Object.entries(r.kept||{}).map(([k,st])=>`<p class="hint" style="margin:4px 0 0">${T(KN(k),'<span class="keep">'+esc(k)+'</span>')}: ${Object.entries(st).map(([b,v])=>`${esc(T(KS[b]||b,b))}: <b>${tech()?esc(v):v==='SURVIVED'?'still there':v==='REMOVED'?'not there':v==='UNTRACKED'?'not followed':esc(String(v).toLowerCase())}</b>`).join(' · ')}${Object.values(st).includes('UNTRACKED')?T(' (“not followed”: it could not be traced through that build, so nothing is said about it)',' (UNTRACKED: could not be followed through this flow, so nothing is said about it)'):''}</p>`).join('');
 return `<div class="galr ${i===0&&atk?'weak':'held'}"><div class="who">${n>1?(i+1)+'. ':''}${esc(galLabel(r.label))}</div><div class="ans">${ans}</div>
  <p class="hint" style="margin:0 0 4px">Checked within ${N} steps, with up to ${gl(r.max_faults)}.${atk?'':' Nothing is claimed beyond that, unless the line on waiting time says so.'}</p>
  ${atk&&r.witness.length?`<p style="margin:4px 0"><b>Where the ${G(r.witness.length)} ${r.witness.length===1?'lands':'land'}:</b> ${r.witness.map(w=>`step ${w[0]}, ${galSite(w[1])}`).join('; ')}.</p>`:''}
  ${ub.verdict==='PROVED_UNBOUNDED'?`<p style="margin:4px 0">${hon('proved',null,true)} ${ub.k===0?'Without any glitch this never happens, however long the chip runs.':`With up to ${gl(ub.k)} it can never happen, however long the chip runs.`}</p>`:ub.verdict?`<p class="hint" style="margin:4px 0">For any waiting time: not decided.</p>`:''}
  ${sv?`<p style="margin:6px 0 2px"><b>Did the protection survive the build?</b></p><table>${sv}</table>`:''}${kp}${(r.findings||[]).length?`<details class="more"><summary>What this means, how bad it is, and how it was found</summary>${findingsHTML(r.findings,' ')}</details>`:''}
  <p class="hint tech-only keep" style="margin:6px 0 0">${esc(r.key)} · check ${esc(r.check)} · top ${esc(r.top||'')} · frontend ${esc(r.frontend||'')} · ${r.runtime_s} s when recorded${r.surface&&r.surface.count?` · ${r.surface.count} cheapest attacks${r.surface.complete?'':' (list not complete)'}`:''}</p></div>`}
async function viewGallery(el){if(!S.gal)S.gal=await api.get('/api/gallery').catch(()=>({missing:true}));const d=S.gal;
 if(!d||d.missing||!(d.examples||[]).length){el.innerHTML=`<div class="empty"><b>The example gallery is not in this project folder</b>Nothing can be shown, and nothing is guessed.</div>`;return}
 const hasMine=VIEWS.some(v=>v.id==='mine');
 const SAME={hello_lock:'The same idea as path steps 1 and 3: one check against three separate copies.',secure_boot:'The same idea as the path, on a boot check: one compare against three compares with an alarm.',opentitan_count:'A counter from OpenTitan, a real open-source security chip, next to a plain counter.',sky130_lock:'The hello lock again, after it was turned into the ready-made gates of a real chip factory.'};
 el.innerHTML=orient(`Four small designs, each in a weak and a protected version, with the saved result of each: how many glitches are needed, where the glitch lands, and whether the protection survived the build.`,`Compare the two versions of each design. The number says how many perfectly-timed glitches a thief needs; the “survive the build” lines say whether the build tool kept the copies.`,`Guess each answer before you read it. Then open <b>Why?</b> under each pair and compare with your own explanation. Nothing has to be installed.`)+
 `<div class="banner"><span><b style="color:var(--txt)">You are seeing saved results. Nothing is missing.</b> ${d.yosys?'The build tool is installed, so these examples can also be run live':'Running an example live needs the build tool, which is not installed on this computer; these are the saved results of the same runs'}${hasMine?' (live runs are in <button class="linkb" id="gal-mine">Open my design</button>)':''}. <button class="linkb" data-go="live">How to run it live</button></span></div>`+
 d.examples.map(x=>{const runs=[...x.runs].sort((a,b)=>(a.verdict==='ATTACK_FOUND'?a.min_faults:99)-(b.verdict==='ATTACK_FOUND'?b.min_faults:99));
  return `<div class="panel"><div class="ph"><h4>${esc(galTxt(x.title))}</h4><span class="sp"></span>${hon('recorded')}</div>
  <div class="gal3"><div><b>What it is</b>${esc(galTxt(x.what))}</div><div><b>Why the protection matters</b>${esc(galTxt(x.why))}</div><div><b>Compare with</b>${esc(SAME[x.id]||galTxt(x.teaches))}</div></div>
  <div class="galx">${runs.map((r,i)=>galRun(r,i,runs.length)).join('')}</div>
  <details class="more learn" style="margin:0 12px 10px"><summary>Why? Open after you have written your own explanation</summary><div class="pb"><p style="margin:0 0 6px">${esc(galTxt(x.teaches))}</p><p style="margin:0">${esc(galTxt(x.after))}</p></div></details>
  <div class="fsrc tech-only">saved results: <span class="keep">${esc(x.file)}</span>${x.when?' · file from '+esc(x.when):''} · computed by the own-design tool (glitchsat run), labelled MEASURED in that file; shown here as recorded because nothing is re-run</div></div>`}).join('')+
 `<p class="hint" style="margin:0 2px 10px">Own designs: this tool answers the build question only (does the protection survive the build tool?). The laser-spot analysis exists for the built-in layouts on the page “Laser shots on the chip”.</p>`;
 const gm=$('#gal-mine');if(gm)gm.onclick=()=>show('mine')}
Studio.registerView({id:'x-spots',group:'explore',title:'Weak spots',ttitle:'Attack surface and merge lint',icon:ICON.spots,blurb:'Every cheapest way in, and which parts they use.',labels:['recorded'],render:viewSurface});
Studio.registerView({id:'x-fix',group:'explore',title:'Suggest a fix',ttitle:'Suggest a fix (auto-harden)',icon:ICON.fix,blurb:'The cheapest change that makes the thief need more glitches.',labels:['recorded'],render:viewFix});
Studio.registerView({id:'x-forever',group:'explore',title:'Holds for any waiting time?',ttitle:'Unbounded proof status',icon:ICON.forever,blurb:'Proofs that hold however long the thief waits.',labels:['proved'],render:viewForever});
Studio.registerView({id:'x-shots',group:'explore',title:'Laser shots on the chip',ttitle:'Glitch shots on the layout',icon:ICON.shots,blurb:'Where on the real layout a pulse must land.',labels:['simulated'],render:viewShots});
Studio.registerView({id:'x-lab',group:'explore',title:'Clock-glitch lab',ttitle:'Virtual glitch campaign',icon:ICON.lab,blurb:'Every clock-glitch timing, tried in software.',labels:['simulated'],render:viewVlab});
Studio.registerView({id:'x-fw',group:'explore',title:'Boot program',ttitle:'Firmware secure boot',icon:ICON.fw,blurb:'Glitches against the program that starts the chip.',labels:['simulated'],render:viewFirmware,findings:()=>{const q=S.fw||{};const d=S.mods[`firmware&variant=${q.variant}&opt=${q.opt}&mode=${q.mode}`];return d&&d.findings}});
Studio.registerView({id:'x-hw',group:'explore',title:'Our boot-check hardware',ttitle:'Secure-boot hardware',icon:ICON.hw,blurb:'Our own protected circuit; the long run is still to come.',labels:[],hidePlain:()=>!(S.hw&&S.hw.run>0),render:viewSecboot});
Studio.registerView({id:'x-rep',group:'explore',title:'Evidence report',ttitle:'Evidence report and margin',icon:ICON.rep,blurb:'The count turned into the points test labs use.',labels:['estimate'],render:viewEvidence});
Studio.registerView({id:'x-real',group:'explore',title:'Real chip designs',ttitle:'Real designs (OpenTitan)',icon:ICON.real,blurb:'Same answers as a published tool on real security-chip blocks.',labels:['recorded'],render:viewReal});
Studio.registerView({id:'x-chip',group:'explore',title:'Explore a real chip',ttitle:'Whole chip (PicoSoC, Ibex demo system)',icon:ICON.real,blurb:'Whole open-source chips: where the security decisions sit, and how many glitches break them.',labels:['bounded'],render:viewChip});
Studio.registerView({id:'x-gal',group:'explore',title:'Example gallery',ttitle:'Example gallery (own-design tool)',icon:ICON.real,blurb:'Weak and protected versions of four small designs. Hands-on, nothing to install.',labels:['recorded'],hide:()=>!S.gal||S.gal.missing||!(S.gal.examples||[]).length,render:viewGallery});

Studio.registerView({id:'start',title:'Start',tip:'Where to begin: try an attack, follow the path, explore',mount:el=>{},show:el=>drawStart(el)});
Studio.registerView({id:'analyze',title:'Try an attack',tip:'Run one attack and read its result',mount:el=>{el.innerHTML='<div id="story"></div><div id="dirty"></div><div id="result"></div>'},show:()=>{if(S.last)requestAnimationFrame(()=>{drawWave();drawMap()})}});
Studio.registerView({id:'explore',title:'Explore',tip:'Weak spots, fixes, proofs, laser shots, boot program and more',show:el=>drawExplore(el)});
Studio.registerView({id:'compare',title:'Compare',tip:'The attacks you tried, side by side',show:drawCompare});
Studio.registerView({id:'findings',title:'Studies',tip:'The studies of the project: recorded results, and the same cells computed live on this computer',show:()=>loadFindings()});
Studio.registerView({id:'about',title:'About',tip:'What the tool does, its limits, versions',show:drawAbout});

/* ---------------- view / theme / keys */
function setView(v){S.view=v;LS.set('gs_view',v);document.documentElement.dataset.view=v;seg('viewseg',v);fillDesign();syncControls();drawSteps();render();drawLog();drawFoot();$('#setdet').open=v==='tech'||LS.get('gs_setopen',false);const cur=VIEWS.find(x=>x.id===S.tab);if(cur&&cur.show&&S.tab!=='analyze')cur.show($('#v-'+S.tab))}
$('#viewseg').onclick=e=>{const b=e.target.closest('button');if(b)setView(b.dataset.v)};
function setTheme(t){S.theme=t;LS.set('gs_theme',t);document.documentElement.dataset.theme=t}
$('#b-theme').onclick=()=>setTheme(S.theme==='dark'?'light':'dark');
document.addEventListener('keydown',e=>{const tg=e.target,tn=tg.tagName;
 if(S.fr)return;/* FIRST-RUN-VIEW: the welcome story or Presenter mode has the keys */
 if(S.story!=null){if(e.key==='Escape')closeStory();else if(e.key==='ArrowRight'&&$('#snx'))$('#snx').click();else if(e.key==='ArrowLeft'&&$('#sbk')&&!$('#sbk').disabled)$('#sbk').click();return}
 if(S.dlg){if(e.key==='Escape')closeDlg();return}
 if(S.help){if(e.key==='Escape')closeHelp();else if(e.key==='ArrowRight'&&$('#hn'))$('#hn').click();else if(e.key==='ArrowLeft'&&$('#hb')&&!$('#hb').disabled)$('#hb').click();return}
 if(e.key==='Escape'&&S.busy){stopRun();return}
 if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();if(!S.busy)$('#run').click();return}
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 const inSide=!!(tg.closest&&tg.closest('aside')),typing=tn==='INPUT'||tn==='SELECT'||tn==='TEXTAREA';
 /* Enter runs, except on controls whose own action is Enter (links, tour and navigation buttons, drop-downs) */
 if(e.key==='Enter'){const own=tn==='A'||tn==='SUMMARY'||tn==='SELECT'||(tn==='BUTTON'&&!(inSide&&tg.closest('.seg')));if(!own&&!S.busy&&(tech()||$('#setdet').open)&&S.tab==='analyze'){e.preventDefault();$('#run').click()}return}
 if(typing)return;
 if(e.key==='ArrowRight'||e.key==='ArrowLeft'){if(tg.id==='wsvg'||(inSide&&!tg.closest('#steps'))||S.ti<0||S.tab!=='analyze')return;e.preventDefault();const n=S.ti+(e.key==='ArrowRight'?1:-1);if(n>=0&&n<TOUR.length&&!S.busy)loadStep(n)}
 else if(e.key==='v'||e.key==='V')setView(tech()?'plain':'tech');
 else if(e.key==='t'||e.key==='T')$('#b-theme').click();
 else if(e.key==='`')toggleLog();
 else if(e.key==='?')openHelp('keys');
 else if(e.key==='s'||e.key==='S')openStory(0);
 else if(e.key==='f'||e.key==='F')openFound();
 else if(e.key==='l'||e.key==='L')openLive();
 else if(/^[1-9]$/.test(e.key)){const tabs=VIEWS.filter(v=>!v.card);if(tabs[+e.key-1])show(tabs[+e.key-1].id)}});
let rz;addEventListener('resize',()=>{clearTimeout(rz);rz=setTimeout(()=>{if(S.last&&!S.last.error){drawWave();drawMap()}},120)});

/* ---------------- lifecycle: the server stops only when every window has closed */
function ping(){fetch('/api/ping?cid='+CID).then(r=>r.json()).then(p=>{const back=S.offline,restarted=!!(p&&p.boot&&S.boot&&p.boot!==S.boot);if(p&&p.boot&&!S.boot)S.boot=p.boot;
  if(back||restarted){S.offline=false;if(restarted)S.boot=p.boot;S.restarted=S.restarted||restarted;
   api.get('/api/status').then(s=>{S.status=s;syncControls();drawFoot();announce(restarted?'The Studio was restarted. Reload this window if a page does not answer.':'The Studio answers again.')}).catch(()=>drawFoot())}})
 .catch(()=>{if(!S.offline){S.offline=true;drawFoot();announce('The Studio is not answering.')}})}
setInterval(ping,15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)ping()});
addEventListener('pagehide',()=>{try{fetch('/api/bye',{method:'POST',keepalive:true,headers:{'X-GlitchSAT':'1','Content-Type':'application/json'},body:JSON.stringify({cid:CID})})}catch(e){}});
addEventListener('pageshow',ping);

/* ---------------- boot */
setTheme(S.theme);document.documentElement.dataset.view=S.view;seg('viewseg',S.view);fillDesign();$('#design').value='v2';drawSteps();syncControls();render();drawFoot();ping();
$('#b-story').onclick=()=>openStory(0);$('#setdet').open=tech()||LS.get('gs_setopen',false);$('.app').classList.toggle('setopen',$('#setdet').open);$('#setdet').addEventListener('toggle',()=>{$('.app').classList.toggle('setopen',$('#setdet').open);if(!tech())LS.set('gs_setopen',$('#setdet').open)});
show('start');observePlain();
api.get('/api/status').then(s=>{S.status=s;$('#ver').textContent=s.version||'';document.title='GlitchSAT Studio '+(s.version||'');syncControls();render();drawFoot();
 logLine('ready',s.live?`GlitchSAT ${s.version} · z3 ${s.z3} · ${s.yosys||'Yosys not installed'} · ${s.workers} worker process(es)`:`GlitchSAT ${s.version} · recorded mode: z3 not installed; results are read from the project files`,'p');
 loadFindings();if(S.tab==='start')drawStart();if(!LS.get('gs_seen3',0)&&!(Studio.firstRun&&Studio.firstRun()))openStory(0);/* FIRST-RUN-VIEW */
 const redo=()=>{if(S.story!=null||S.dlg||S.help)return;if(S.tab==='start')drawStart();else if(S.tab==='about')drawAbout();else if(S.tab==='explore')drawExplore()};
 if(s.gallery)api.get('/api/gallery').then(g=>{S.gal=g;redo()}).catch(()=>{});
 getMod('real').then(d=>{S.real=d&&!d.missing&&!d.error&&!d.broken?d:null;redo();if(S.story!=null&&S.tab==='start')drawStart()});
 getMod('secboot_hw').then(d=>{if(d&&d.cards)S.hw={total:d.cards.length,run:d.cards.filter(c=>c.status!=='NOT_RUN').length};redo();if(S.story!=null&&S.tab==='start')drawStart()})}).catch(()=>{S.offline=true;drawFoot();drawStart()});
</script></body></html>'''

# ---- LEARN-VIEW hook: the "Why protect chips?" lesson lives in learn_view.py (tab, story card, Start link, Explore lines)
learn_view = None
try:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location('learn_view', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'learn_view.py'))
    learn_view = _ilu.module_from_spec(_sp); _sp.loader.exec_module(learn_view); PAGE = learn_view.install(PAGE)
except Exception as _e:                # noqa: BLE001  - the Studio must start without it
    learn_view = None; print(f'learn_view not loaded: {_e}', file=sys.stderr)

# ---- FIRST-RUN-VIEW hook: the welcome story ("Why GlitchSAT?") and Presenter mode live in first_run_view.py
first_run_view = None
try:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location('first_run_view', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'first_run_view.py'))
    first_run_view = _ilu.module_from_spec(_sp); _sp.loader.exec_module(first_run_view); PAGE = first_run_view.install(PAGE)
except Exception as _e:                # noqa: BLE001  - the Studio must start without it
    first_run_view = None; print(f'first_run_view not loaded: {_e}', file=sys.stderr)

# ---- LABS-VIEW hook: the "Labs" tab (experiments in progress) lives in labs_view.py; it only reads saved Labs results
labs_view = None
try:
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location('labs_view', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'labs_view.py'))
    labs_view = _ilu.module_from_spec(_sp); _sp.loader.exec_module(labs_view); PAGE = labs_view.install(PAGE)
except Exception as _e:                # noqa: BLE001  - the Studio must start without it
    labs_view = None; print(f'labs_view not loaded: {_e}', file=sys.stderr)

# ---- PLUGIN hook: add-ons found on disk are loaded by the one start command; no environment variable is needed.
# The loading contract (studio.py never edits a plug-in file, and a plug-in never has to edit studio.py):
#   * A plug-in is marked by its launcher file  tools/studio/studio_byod.py  (looked for in the project, next to this
#     file, in tools/byod/ and, for testing, in $GLITCHSAT_EXT/byod).
#   * Next to the launcher lives the view module  byod_view.py  with two functions:
#         install(page) -> page                 adds its style and script; the script calls Studio.registerView({...})
#         handle(h, method, path, q) -> bool    answers its own requests (True when it answered); h is the request handler
#   * A launcher that defines  attach(studio_module)  is asked instead; it returns an object with handle(...) (or None)
#     and may change studio_module.PAGE itself.
# Skipped for worker processes, with --no-plugins, and when the page already has the plug-in (started through the launcher).
def load_plugins():
    global PAGE
    if PLUGINS or IS_WORKER or '--no-plugins' in sys.argv or '/api/byod/' in PAGE: return
    import importlib.util as ilu
    for lp in _plugin_candidates()[:1]:
        try:
            d = os.path.dirname(lp)
            if 'def attach(' in open(lp, encoding='utf-8').read():
                sp = ilu.spec_from_file_location('studio_byod', lp); m = ilu.module_from_spec(sp); sp.loader.exec_module(m)
                obj = m.attach(sys.modules[__name__])
                if obj is not None: PLUGINS.append(dict(name='Open my design', path=lp, handle=obj.handle))
            else:
                sp = ilu.spec_from_file_location('byod_view', os.path.join(d, 'byod_view.py')); m = ilu.module_from_spec(sp); sp.loader.exec_module(m)
                PAGE = m.install(PAGE)
                PLUGINS.append(dict(name='Open my design', path=lp, handle=m.handle))
        except Exception as e:                 # noqa: BLE001  - the Studio must start without it
            PLUGIN_NOTES.append('Open my design was found at %s but could not be loaded (%s: %s)' % (lp, type(e).__name__, str(e)[:160]))
            print('plug-in not loaded: %s: %s' % (lp, e), file=sys.stderr)

def _arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 >= len(sys.argv) or sys.argv[i + 1].startswith('--'):
            sys.exit(f'{name} needs a value, for example: {name} 8765')
        return sys.argv[i + 1]
    return default

def _open_window(url):
    for b in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'brave-browser', 'microsoft-edge'):
        if shutil.which(b):
            subprocess.Popen([b, f'--app={url}', '--window-size=1440,900'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            BROWSER_USED[0] = b + ' (app window)'; return
    webbrowser.open(url)
    BROWSER_USED[0] = 'default browser (tab); install Chromium for a separate app window'

HELP = '''GlitchSAT Studio %s - counts how many glitches an attacker needs, on this computer only.

usage: python3 studio.py [--port N] [--no-browser] [--no-autostop] [--no-plugins] [--allow-root DIR]
       python3 studio.py --help | --version

  --port N        first port to try on 127.0.0.1 (default 8765; the next free one is used)
  --no-browser    do not open a window; open the printed address yourself
  --no-autostop   keep running when every window is closed
  --no-plugins    start without the "Open my design" plug-in
  --allow-root DIR  let "Open my design" open folders under DIR too (default: only the home folder)
  -h, --help      show this text and exit (no server is started)
  -V, --version   show the versions and exit

The project folder is $GLITCHSAT_ROOT, else the repository that contains this file, else the current folder.
Without z3 every result is a saved result from the project files, labelled RECORDED.'''

def info_only():
    """--help / --version: print and return True, before anything is started."""
    if '--version' in sys.argv or '-V' in sys.argv:
        print('GlitchSAT %s, Studio interface %s (project: %s%s)' % (ENGINE_VERSION or '?', STUDIO_VERSION, ROOT,
                                                                     '' if project_found() else ', NOT a GlitchSAT project folder'))
        return True
    print(HELP % STUDIO_VERSION)
    return True

def not_project_note():
    return ('This is not a GlitchSAT project folder: %s has no scripts/glitchsat.py and results/. Start the Studio from the '
            'repository (python3 tools/studio/studio.py), or set GLITCHSAT_ROOT=/path/to/the/repository.' % ROOT)

def main():
    try: sys.stdout.reconfigure(line_buffering=True)   # the address must appear at once, also when the output goes to a file
    except Exception: pass                             # noqa: BLE001
    if not project_found(): print('WARNING: ' + not_project_note(), file=sys.stderr, flush=True)
    load_plugins()
    try: port = int(_arg('--port', '8765'))
    except ValueError: sys.exit('--port needs a number, for example: --port 8765')
    try:                                       # a Studio already running on this port? Reuse it instead of starting a second server.
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/status', timeout=1.5) as r:
            st = json.loads(r.read().decode())
        if isinstance(st, dict) and 'studio' in st:
            url = f'http://127.0.0.1:{port}/'
            print(f'GlitchSAT Studio is already running at {url} - opening it.')
            if '--no-browser' not in sys.argv: _open_window(url)
            return
    except Exception:                          # noqa: BLE001
        pass
    srv = None
    for p in range(port, port + 20):
        try: srv = ThreadingHTTPServer(('127.0.0.1', p), H); port = p; break
        except OSError: continue
    if srv is None: sys.exit('no free port')
    srv.daemon_threads = True
    PORT[0] = port
    url = f'http://127.0.0.1:{port}/'
    print(f'GlitchSAT {ENGINE_VERSION or "?"} Studio running at {url}')
    print(f'  engine : {"live, z3 " + Z3V if LIVE else "recorded results only (z3 not installed)"}')
    print(f'  Yosys  : {YOSYS_V or "not installed (rebuilt designs use recorded results)"}')
    if not LIVE: print('  to compute live: pip install z3-solver (inside a Python virtual environment), then start the Studio again')
    print(f'  project: {ROOT}' + ('' if project_found() else '   <- NOT a GlitchSAT project folder (see the warning above)'))
    print('  lesson : ' + ('"Why protect chips?" loaded' if learn_view else 'not loaded (learn_view.py missing)'))
    print('  design : ' + ('"Open my design" loaded from ' + PLUGINS[0]['path'] if PLUGINS else '"Open my design" tab already installed by its launcher' if '/api/byod/' in PAGE
                           else (PLUGIN_NOTES[0] if PLUGIN_NOTES else '"Open my design" plug-in not found (optional)')))
    if '--no-browser' not in sys.argv:
        _open_window(url)
        print(f'  window : {BROWSER_USED[0]}')
    print('Close the app window or press Ctrl+C to stop.')
    def watchdog():
        # Stops only when EVERY window has said it is closing (and none came back within a few seconds), or after a long
        # silence. A minimised window still pings, slowly, so a demo is never cut off. Explainer pages opened from Findings
        # and running searches also keep the server alive.
        while True:
            time.sleep(2)
            now = time.time()
            for cid, seen in list(CLIENTS.items()):
                if now - seen > IDLE_LIMIT_S: CLIENTS.pop(cid, None)
            busy = bool(RUNS) or any(j.status == 'running' for j in JOBS.values())
            last = max([STARTED, LAST_BYE[0], LAST_PAGE_GET[0]] + list(CLIENTS.values()))
            if CLIENTS:
                continue
            if EVER_CLIENT[0] and LAST_BYE[0] and now - LAST_BYE[0] > BYE_GRACE_S and now - LAST_PAGE_GET[0] > IDLE_LIMIT_S:
                if busy: cancel_everything()
                print('All app windows closed - stopping.'); srv.shutdown(); return
            if now - last > IDLE_LIMIT_S and not busy:
                print(f'No activity for {IDLE_LIMIT_S // 60} minutes - stopping.'); srv.shutdown(); return
    if '--no-autostop' not in sys.argv:
        threading.Thread(target=watchdog, daemon=True).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        cancel_everything(); CACHE.save()
        time.sleep(0.2)
        shutil.rmtree(WORK, ignore_errors=True)

if __name__ == '__main__':
    if INFO_ONLY:
        info_only()
    elif IS_WORKER:
        i = sys.argv.index('--worker')
        worker_main(sys.argv[i + 1], sys.argv[i + 2])
    else:
        main()
