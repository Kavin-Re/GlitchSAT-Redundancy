"""`glitchsat init` and the Studio wizard share this file: suggest() reads the design and guesses with evidence,
make_yaml() writes the same commented glitchsat.yaml from the answers.

Five steps: 1 design files, 2 top / clock / reset (pre-filled), 3 who controls which input, 4 what must never
happen (a template), 5 how hard to search (defaults: 20 cycles, up to 3 single-bit flips)."""
import glob
import os
import re
import sys
import tempfile

from . import detect as DET
from . import flows as FL
from . import templates as TPL
from .errors import GSError

HDL = ('.v', '.sv')


def find_sources(folder):
    out = []
    for sub in ('', 'rtl', 'src', 'hdl', 'hw'):
        for ext in HDL:
            out += glob.glob(os.path.join(folder, sub, '*' + ext))
    return sorted(set(os.path.relpath(p, folder) for p in out if not os.path.basename(p).startswith(('tb_', 'test_')) and '_tb' not in os.path.basename(p)))


def suggest(folder, sources, top=None, frontend='auto', params=None):
    """Elaborate and detect. Returns dict(top, ports, clock, reset, secrets, test_inputs, evidence, outputs, inputs)."""
    spec = dict(sources=[os.path.join(folder, s) for s in sources], top=top, frontend=frontend, include_dirs=[], defines={},
                params=params or {}, liberty=[], blackboxes=[], netlist_input=False)
    work = tempfile.mkdtemp(prefix='glitchsat-init-')
    E = FL.elaborate(spec, work)
    det = DET.detect(E['detect']['modules'][E['top']])
    det['top'] = E['top']
    det['frontend'] = E['frontend']
    det['yosys'] = E['ys'].short()
    return det


def _y(v):
    """One YAML value, written by the YAML library (quoted and escaped as needed), on one line."""
    import yaml
    if isinstance(v, str) and any(ord(ch) < 32 or ord(ch) == 127 for ch in v):
        return _q(v)
    t = yaml.safe_dump(v, default_flow_style=True, width=10 ** 9, allow_unicode=True).strip()
    if t.endswith('\n...'):
        t = t[:-4]
    if t.endswith('...'):
        t = t[:-3].strip()
    return t


def _q(v):
    """A string value always in double quotes (Verilog expressions), escaped by the YAML library."""
    import yaml
    if not isinstance(v, str):
        return _y(v)
    t = yaml.safe_dump(v, default_style='"', width=10 ** 9, allow_unicode=True).strip()
    return t[:-3].strip() if t.endswith('...') else t


def make_yaml(ans):
    """ans: dict(name, sources, top, clock, reset{port,active}|None, attacker[list]|'all', secret[], fixed{},
    template, params{}, bad, must_hold[], horizon, max_faults, explain, evidence[]). Every value is written by the YAML
    library, so a value can never add a key or a line to the file."""
    L = ['# GlitchSAT project file. Written by `glitchsat init` (or the Studio wizard); edit freely.',
         '# Format: docs/SCHEMA.md. Check it with `glitchsat check`, run it with `glitchsat run`.',
         'glitchsat: 1', 'name: %s' % _y(str(ans.get('name') or 'my_design')), '', '# 1. The design', 'design:',
         '  sources: %s' % _y([str(x) for x in ans['sources']]), '  top: %s' % _y(str(ans['top']))]
    if ans.get('params'):
        L.append('  params: %s' % _y(dict(ans['params'])))
    L += ['', '# 2. Clock and reset (found automatically; the evidence is in the comments)']
    for e in ans.get('evidence') or []:
        L.append('#    %s' % str(e).replace('\n', ' ').replace('\r', ' '))
    L.append('clock: %s' % _y(str(ans['clock'] or 'none')))
    if ans.get('reset'):
        r = ans['reset']
        L.append('reset: %s      # held for 1 cycle; faults start after reset'
                 % _y(dict(port=str(r['port']), active=str(r.get('active') or 'low'))))
    else:
        L.append('reset: none')
    L += ['', '# 3. Who controls what', 'inputs:']
    att = ans.get('attacker', 'all')
    L.append('  attacker: %s' % ('all' if att == 'all' else _y([str(x) for x in att])) +
             '          # inputs the attacker can drive (a new value every cycle)')
    if ans.get('secret'):
        L.append('  secret: %s               # a key: held constant, any value' % _y([str(x) for x in ans['secret']]))
    if ans.get('fixed'):
        L.append('  fixed: %s' % _y({str(k): v for k, v in ans['fixed'].items()}))
    L += ['', '# 4. What must never happen', 'checks:', '  - id: %s' % _y(str(ans.get('check_id', 'never_happens')))]
    goal = ans.get('goal') or TPL.GOAL.get(ans.get('template') or '')
    if goal and goal not in TPL.GOALS:
        raise GSError('GS002', 'unknown goal %r' % (goal,), help='goals: ' + ', '.join(TPL.GOALS))
    if goal:
        L.append('    goal: %s     # what an attacker gets: %s' % (goal, TPL.GOALS[goal]))
    else:
        L.append('    # goal: lock_bypass   # what an attacker gets if this fails: %s' % ', '.join(TPL.GOALS))
    if ans.get('template') and ans['template'] != 'custom':
        if ans['template'] not in TPL.PLAIN:
            raise GSError('GS002', 'unknown template %r' % (ans['template'],))
        L.append('    template: %s     # %s' % (ans['template'], TPL.PLAIN[ans['template']]))
        L.append('    params:')
        for k, v in (ans.get('params_t') or {}).items():
            if v in (None, ''):
                continue
            L.append('      %s: %s' % (_y(str(k)), _q(v)))
    else:
        L.append('    bad: %s' % _q(str(ans.get('bad') or "1'b0")))
    if ans.get('must_hold'):
        L.append('    must_hold:                 # must stay true: what a legitimate user may do, a quiet alarm')
        for m in ans['must_hold']:
            L.append('      - %s' % _q(str(m)))
    else:
        L.append('    # must_hold: ["%s"]   # MISSING: what a legitimate user may do. Without it the first run' % re.sub(r'[\r\n"]', ' ', str(ans.get('must_hold_example') or "!(code_i == 8'hA5)")))
        L.append('    #                      usually finds the "attack" with no glitch at all (the right code typed).')
    if ans.get('explain'):
        L.append('    explain: %s' % _q(str(ans['explain'])))
    L += ['', '# 5. How hard to search (SymbiYosys uses the same default depth of 20 cycles)', 'faults:',
          '  types: [flip]                # a value inverted for one clock cycle',
          '  max_faults: %d                # search 1, 2, ... up to this many faults' % int(ans.get('max_faults', 3)),
          '  horizon: %d                  # cycles after reset' % int(ans.get('horizon', 20)), '']
    return '\n'.join(L)


_ROLE_HINTS = {   # template parameter -> (which ports, name pattern) used to prefill it from the design
    'counter': ('outputs', r'cnt|count|tries|left|ctr'), 'unlocked': ('outputs', r'unlock|open|dbg|debug|en'),
    'accept': ('outputs', r'accept|ok|pass|valid|grant|boot'), 'output': ('outputs', r'out|data|_o$'),
    'locked': ('inputs', r'lc|life|lock'), 'key_input': ('inputs', r'key|tag|sig|code'), 'key': ('inputs', r'key|secret'),
    'alarm': ('outputs', r'alarm|err|tamper|fault|alert'), 'trigger': ('inputs', r'tamper|trig|glitch|attack'),
    'must_step_when': ('inputs', r'try|attempt|check|wrong|fail'), 'state': ('outputs', r'state|st_|fsm'),
}


def prefill(tid, params, det):
    """Template parameters with names taken from the user's design: a default whose names are not ports of the
    design is replaced by a port that fits (by name, else the first output), or dropped if optional."""
    import re
    ports = set(det.get('inputs') or []) | set(det.get('outputs') or [])
    out = {}
    for k, v in (params or {}).items():
        names = [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_$.]*", str(v)) if not re.match(r"^[hbdo][0-9a-fA-F_]+$", w)]
        if not isinstance(v, str) or not names or all(n in ports for n in names):
            out[k] = v
            continue
        side, rx = _ROLE_HINTS.get(k, ('outputs', r'^$'))
        cands = [p for p in det.get(side) or [] if re.search(rx, p, re.I)]
        if not cands and k in ('counter', 'unlocked', 'accept', 'output', 'state'):
            cands = list(det.get('outputs') or [])
        if cands:
            out[k] = cands[0] if k != 'must_step_when' else cands[0]
        elif k in ('counter', 'unlocked', 'accept', 'locked', 'key_input', 'key', 'output', 'trigger', 'alarm', 'state'):
            out[k] = v
    return out


def must_hold_example(det, clock=None, reset=None):
    ins = [p for p in det.get('inputs') or [] if p not in (clock, reset)]
    if not ins:
        return None
    w = (det.get('ports') or {}).get(ins[-1], ('input', 1))[1]
    return "!(%s == %d'h%s)" % (ins[-1], w, '0' * max(1, (w + 3) // 4)) if w > 1 else '!%s' % ins[-1]


def _ask(prompt, default, yes):
    if yes:
        print('%s [%s]' % (prompt, default))
        return default
    try:
        v = input('%s [%s]: ' % (prompt, default)).strip()
    except EOFError:
        v = ''
    return v or default


def main(a):
    folder = os.getcwd()
    tt = None
    if a.from_tinytapeout:
        from .importers import tinytapeout
        tt = tinytapeout(a.from_tinytapeout)
        folder = os.path.abspath(a.from_tinytapeout)
        a.out = os.path.join(folder, os.path.basename(a.out))
    if os.path.exists(a.out) and not a.force:
        print('error[GS003]: %s already exists\n  = help: use --force to overwrite, or --out other.yaml' % a.out, file=sys.stderr)
        return 3
    print('GlitchSAT setup: five questions. Press Enter to accept the suggestion in [brackets].\n')
    srcs = a.sources or (tt['sources'] if tt else find_sources(folder))
    print('1/5 Design files. Found: %s' % (', '.join(srcs) or 'none'))
    if not srcs:
        print('error[GS004]: no .v or .sv files here or in rtl/, src/\n  = help: run init in your project folder, or pass --sources file.v', file=sys.stderr)
        return 3
    s = _ask('    Files to use (space separated)', ' '.join(srcs), a.yes)
    srcs = s.split()
    try:
        det = suggest(folder, srcs, a.top or (tt['top'] if tt else None))
    except GSError as e:
        print(e.render(), file=sys.stderr)
        return 3
    print('\n2/5 Top module `%s` (%d flip-flops). What was found:' % (det['top'], det['flops']))
    for e in det['evidence']:
        print('    - ' + e)
    clock = _ask('    Clock input', det['clock'] or 'none', a.yes)
    rs = det['reset']
    rport = _ask('    Reset input (none if there is no reset)', rs['port'] if rs else 'none', a.yes)
    reset = None
    if rport != 'none':
        act = _ask('    Reset is active (low/high)', (rs or {}).get('active', 'low' if rport.endswith('n') else 'high'), a.yes)
        reset = dict(port=rport, active=act)
    ins = [p for p in det['inputs'] if p not in (clock, rport)]
    print('\n3/5 Inputs: %s' % ', '.join(ins))
    fixed = {p: 0 for p in det['test_inputs'] if p in ins}
    sugg = [p for p in det['secrets'] if p in ins]
    att_def = ' '.join(p for p in ins if p not in fixed) or 'all'
    att = _ask('    Which inputs can the attacker change?', att_def, a.yes).split()
    if sugg:
        print('    These look like a secret by their name: %s. "Secret" means: held constant at an unknown value that the '
              'search may choose (the result then shows which key value the attack needs). Only list an input as secret '
              'if the attacker really cannot drive it.' % ', '.join(sugg))
    sec = _ask('    Which inputs carry a secret key? (none)', 'none', a.yes)
    sec = [] if sec == 'none' else sec.split()
    att = [p for p in att if p not in sec]
    print('\n4/5 What must never happen? Templates:')
    for i, n in enumerate(TPL.NAMES, 1):
        print('    %d. %-24s %s' % (i, n, TPL.PLAIN[n]))
    t = _ask('    Number or name', a.template or 'custom', a.yes)
    if t.isdigit() and 1 <= int(t) <= len(TPL.NAMES):
        t = TPL.NAMES[int(t) - 1]
    ans = dict(name=det['top'], sources=srcs, top=det['top'], clock=None if clock == 'none' else clock, reset=reset,
               attacker=att, secret=sec, fixed=fixed, evidence=det['evidence'], template=t)
    if t == 'custom':
        outs = det['outputs']
        ans['bad'] = _ask('    Bad condition as a Verilog expression over ports (e.g. %s == 1)' % (outs[0] if outs else 'out'),
                          '%s != 0' % outs[0] if outs else "1'b0", a.yes)
    else:
        snippet = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', t + '.yaml')).read()
        print('    Template parameters (edit them in the file afterwards):')
        import yaml
        doc = yaml.safe_load(snippet)
        ans['params_t'] = doc['checks'][0].get('params', {})
        ans['params_t'] = prefill(t, ans['params_t'], det)
        for k, v in list(ans['params_t'].items()):
            ans['params_t'][k] = _ask('      %s' % k, v, a.yes)
    ex = must_hold_example(det, ans['clock'], rport)
    print('    What may a legitimate user do that is allowed? (a must-hold condition: the attack must not simply do this.')
    print('    For a lock: "the right code is never typed", e.g. %s; "none" if nothing is allowed)' % (ex or "!(code_i == 8'hA5)"))
    mh = _ask('    Must-hold condition', 'none', a.yes)
    ans['must_hold_example'] = ex
    if mh != 'none':
        ans['must_hold'] = [mh]
    elif ans['attacker']:
        print('    NOTE: no must-hold condition. The attacker can drive %s, so the first run will most likely report the attack '
              '"WITHOUT any fault" (ordinary use already does it). The file gets a commented line to fill in.' % ', '.join(ans['attacker']))
    print('\n5/5 Search depth.')
    ans['horizon'] = int(_ask('    Cycles to look at after reset', '20', a.yes))
    ans['max_faults'] = int(_ask('    Largest number of faults to try', '3', a.yes))
    text = make_yaml(ans)
    with open(a.out, 'w') as f:
        f.write(text)
    print('\nWrote %s. Next: glitchsat check %s && glitchsat run %s' % (a.out, a.out, a.out))
    return 0
