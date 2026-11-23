"""glitchsat.yaml: load, check against the schema, apply a task, fill defaults. Produces a plain dict `spec`."""
import copy
import os
import re

from . import schema as SC
from . import templates as TPL
from .errors import GSError, GSWarning

DEFAULT_HORIZON = 20
DEFAULT_KMAX = 3
PHYSICAL_DEFAULT = ['*tap*', '*fill*', '*decap*', '*diode*']


def _yaml():
    try:
        import yaml
        return yaml
    except ImportError:
        raise GSError('GS001', 'PyYAML is not installed', help='pip install pyyaml (or give the project as JSON: glitchsat.json)')


def load_file(path):
    if not os.path.isfile(path):
        raise GSError('GS003', 'project file %s does not exist' % path,
                      help='create one with `glitchsat init`, or copy an example: `glitchsat examples copy hello_lock`')
    text = open(path, encoding='utf-8').read()
    if path.endswith('.json'):
        import json
        try:
            return json.loads(text)
        except ValueError as e:
            raise GSError('GS001', 'cannot read %s: %s' % (path, e))
    if '\t' in text.split('#')[0] and re.search(r'^\t', text, re.M):
        ln = next(i for i, l in enumerate(text.splitlines(), 1) if l.startswith('\t'))
        raise GSError('GS001', 'line %d of %s starts with a tab' % (ln, os.path.basename(path)), where='%s:%d' % (path, ln),
                      help='YAML indentation must use spaces; replace the tab by spaces')
    y = _yaml()
    try:
        doc = y.safe_load(text)
    except y.YAMLError as e:
        mark = getattr(e, 'problem_mark', None)
        where = '%s:%d:%d' % (path, mark.line + 1, mark.column + 1) if mark else path
        raise GSError('GS001', 'cannot read %s: %s' % (os.path.basename(path), getattr(e, 'problem', None) or e), where=where,
                      help='if the line holds a Verilog expression, put it in double quotes, e.g. bad: "!locked && dbg_en"')
    if not isinstance(doc, dict):
        raise GSError('GS001', '%s does not contain a mapping (key: value pairs)' % path)
    return doc


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def check_schema(doc, path='glitchsat.yaml'):
    if doc.get('glitchsat') not in (1, None):
        raise GSError('GS006', 'file format version %r is not supported' % doc.get('glitchsat'), help='set `glitchsat: 1`')
    errs = SC.validate(doc)
    if errs:
        lines = SC.format_errors(errs)
        first = lines[0]
        raise GSError('GS002', '%s: %s' % (os.path.basename(path), first), note='\n'.join(lines[1:6]) if len(lines) > 1 else None,
                      help='the format is described in docs/SCHEMA.md (schema/glitchsat.schema.json)')


def read_filelist(fl, base):
    """-f style filelist: paths, +incdir+DIR, +define+N[=V], -f nested, // and # comments."""
    out = dict(sources=[], include_dirs=[], defines={})
    p = os.path.join(base, fl)
    if not os.path.isfile(p):
        raise GSError('GS009', 'filelist %s does not exist' % fl)
    d = os.path.dirname(p)
    for raw in open(p, encoding='utf-8'):
        ln = re.sub(r'(//|#).*$', '', raw).strip()
        if not ln:
            continue
        for tok in ln.split():
            if tok.startswith('+incdir+'):
                out['include_dirs'] += [os.path.join(d, x) for x in tok[8:].split('+') if x]
            elif tok.startswith('+define+'):
                for x in tok[8:].split('+'):
                    if x:
                        k, _, v = x.partition('=')
                        out['defines'][k] = v or None
            elif tok.startswith('-f') or tok.startswith('-F'):
                continue
            elif tok.startswith('-') or tok.startswith('+'):
                raise GSError('GS009', 'filelist %s: option %s is not supported' % (fl, tok), help='supported: file paths, +incdir+, +define+')
            else:
                out['sources'].append(os.path.normpath(os.path.join(d, tok)))
    return out


def parse_value(v, width=None):
    """Integers, booleans, "0xC3", "8'hC3", "'b1010"."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    s = str(v).strip().replace('_', '')
    m = re.fullmatch(r"(\d+)?'([sS]?)([bBoOdDhH])([0-9a-fA-F]+)", s)
    if m:
        return int(m.group(4), {'b': 2, 'o': 8, 'd': 10, 'h': 16}[m.group(3).lower()])
    try:
        return int(s, 0)
    except ValueError:
        raise GSError('GS016', 'value %r is not a number' % v, help="write 5, 0x5, 8'h05 or 4'b0101")


_CHECK_ID = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')


def _no_placeholders(x, path=''):
    if isinstance(x, str) and re.match(r'^\s*TODO', x):
        raise GSError('GS002', '`%s` is still the placeholder %r' % (path or '(top level)', x),
                      help='an importer left this for you to fill in; replace it with the real value')
    if isinstance(x, dict):
        for k, v in x.items():
            _no_placeholders(v, (path + '.' if path else '') + str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _no_placeholders(v, '%s[%d]' % (path, i))


def check_strings(spec):
    """A project file is data. Every string that reaches a Yosys script or a file name is checked here (GS002), so
    `glitchsat check` refuses the same files `glitchsat run` would refuse."""
    from . import flows as FL
    if spec['top'] is not None:
        FL.check_ident(spec['top'], '`design.top`')
    for k, v in spec['defines'].items():
        FL.check_define(k, v)
    for k, v in spec['params'].items():
        FL.check_ident(k, '`design.params` name')
        FL._pval(v)
    for x in spec['sources']:
        FL.check_path(x, 'design source')
    for x in spec['include_dirs']:
        FL.check_path(x, 'include dir')
    for x in spec['liberty']:
        FL.check_path(x, 'Liberty')
    for bb in spec['blackboxes']:
        FL.check_ident(bb['module'], '`design.blackboxes` module')
        if bb.get('stub'):
            FL.check_path(bb['stub'], 'black-box stub')
    if spec['clock'] not in (None, 'none'):
        FL.check_ident(spec['clock'], '`clock`')
    if isinstance(spec['reset'], dict):
        FL.check_ident(spec['reset']['port'], '`reset.port`')
    for p in (spec['attacker'] if isinstance(spec['attacker'], list) else []) + spec['secret'] + list(spec['fixed']):
        FL.check_ident(p, 'input name')
    for a, h in spec['probes'].items():
        FL.check_ident(a, 'probe alias')
        FL.check_hier(h, 'probe `%s`' % a)
    for c in spec['checks']:
        if not isinstance(c['id'], str) or not _CHECK_ID.match(c['id']) or '..' in c['id']:
            raise GSError('GS002', 'check id %r cannot be used (it becomes a folder name)' % (c['id'],),
                          help='use letters, digits, `_`, `-` and `.`, starting with a letter; no `..`')
        for e in [c.get('bad')] + list(c.get('must_hold') or []):
            if isinstance(e, str) and re.search(r'[\x00-\x08\x0b-\x1f\x7f`]', e):
                raise GSError('GS002', 'condition of check `%s` contains a control character or backquote' % c['id'])
    if spec['task'] is not None and not re.match(r'^[A-Za-z_][A-Za-z0-9_-]*$', str(spec['task'])):
        raise GSError('GS002', 'task name %r cannot be used (it becomes a file name)' % (spec['task'],))
    for t in (spec['raw'].get('tasks') or {}):
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_-]*$', str(t)):
            raise GSError('GS002', 'task name %r cannot be used (it becomes a file name)' % (t,),
                          help='use letters, digits, `_` and `-`')
    rb = os.path.realpath(spec['base'])
    ro = os.path.realpath(spec['out'])
    if not (ro == rb or ro.startswith(rb + os.sep)):
        raise GSError('GS002', '`report.out` must be a folder inside the project folder, not %s' % spec['out'],
                      help='use a relative path such as .glitchsat (the default)')
    for pat in spec['include'] + spec['exclude']:
        if not isinstance(pat, str) or re.search(r'[\x00-\x1f\x7f]', pat):
            raise GSError('GS002', 'fault-site pattern %r contains a control character' % (pat,))
        if pat.startswith('re:'):
            try:
                re.compile(pat[3:])
            except re.error as e:
                raise GSError('GS002', 'fault-site pattern %r is not a valid regular expression: %s' % (pat, e))
    for pat in spec['physical_cells']:
        if not isinstance(pat, str) or not re.match(r'^[A-Za-z0-9_*?]+$', pat):
            raise GSError('GS002', '`design.physical_cells` pattern %r is not a plain cell-type pattern' % (pat,),
                          help='letters, digits, `_`, `*` and `?` only, e.g. "*tap*"')
    _no_placeholders(spec['raw'])
    if spec['yosys_script']:
        FL.user_script(spec)
        if 'custom' not in spec['flows']:
            raise GSError('GS002', '`design.yosys_script` is only used by flow `custom`',
                          help='add `custom` to `flows:`, or remove `design.yosys_script`')
    if 'custom' in spec['flows'] and not spec['yosys_script']:
        raise GSError('GS025', 'flow `custom` needs `design.yosys_script`')


def load(path, task=None):
    """Returns (spec, warnings)."""
    path = os.path.abspath(path)
    base = os.path.dirname(path)
    doc = load_file(path)
    raw = copy.deepcopy(doc)
    tasks = doc.pop('tasks', None) or {}
    if task:
        if task not in tasks:
            raise GSError('GS002', 'task `%s` is not defined' % task, help='tasks: ' + (', '.join(tasks) or 'none'))
        doc = deep_merge(doc, tasks[task])
    check_schema(dict(doc, tasks=tasks) if tasks else doc, path)
    W = []
    d = doc.get('design') or {}
    srcs, incs, defs = [], [os.path.join(base, x) for x in d.get('include_dirs') or []], dict(d.get('defines') or {})
    for s in d.get('sources') or []:
        if isinstance(s, dict):
            fl = read_filelist(s['filelist'], base)
            srcs += fl['sources']; incs += fl['include_dirs']; defs.update(fl['defines'])
        else:
            srcs.append(os.path.normpath(os.path.join(base, s)))
    if not srcs:
        raise GSError('GS004', 'no design sources', help='add `design: {sources: [rtl/top.v]}` to %s' % os.path.basename(path))
    for s in srcs:
        if not os.path.isfile(s):
            raise GSError('GS003', 'design source %s does not exist' % os.path.relpath(s, base),
                          help='paths are relative to %s' % base)
    if not os.environ.get('GLITCHSAT_ALLOW_OUTSIDE'):
        rb = os.path.realpath(base)
        for s in srcs:                     # a project file must not make the tool read files elsewhere (audit 4-S3)
            if not (os.path.realpath(s) + os.sep).startswith(rb + os.sep):
                raise GSError('GS003', 'design source %s is outside the project folder' % os.path.relpath(s, base),
                              help='copy the file into the project folder, or run with --allow-outside (environment: '
                                   'GLITCHSAT_ALLOW_OUTSIDE=1) if you trust this project file')
    libs = []
    from .flows import libs_dir
    os.environ.setdefault('GLITCHSAT_LIBS', libs_dir())
    for l in d.get('liberty') or []:
        lp = os.path.expandvars(os.path.expanduser(l))
        lp = lp if os.path.isabs(lp) else os.path.join(base, lp)
        if not os.path.isfile(lp):
            raise GSError('GS003', 'Liberty file %s does not exist' % lp,
                          help=('run `sh scripts/fetch_libs.sh` once (it fetches the open libraries into %s), or set GLITCHSAT_LIBS'
                                % os.environ['GLITCHSAT_LIBS']) if 'GLITCHSAT_LIBS' in l else
                          'Liberty files are read in place; give the path to the file in your PDK installation')
        libs.append(lp)
    bbs = []
    for bb in d.get('blackboxes') or []:
        st = os.path.join(base, bb['stub']) if bb.get('stub') else None
        if st and not os.path.isfile(st):
            raise GSError('GS003', 'black-box stub %s does not exist' % bb['stub'])
        bbs.append(dict(module=bb['module'], stub=st))
    flt = doc.get('faults') or {}
    for k in ('per_cycle', 'cycles'):
        if flt.get(k) is not None:
            raise GSError('GS008', '`faults.%s` is not modelled in this release' % k,
                          help='remove it: the search allows any number of faults per cycle, in any cycle of the horizon')
    types = []
    for t in flt.get('types') or ['flip']:
        t = {'bitflip': 'flip', 'stuck_at_0': 'reset', 'stuck_at_1': 'set'}.get(t, t)
        if t not in types:
            types.append(t)
    if any(t in (flt.get('types') or []) for t in ('stuck_at_0', 'stuck_at_1')):
        W.append(GSWarning('GS008', 'stuck_at_* is modelled as a one-cycle set/reset fault (a permanent fault is not modelled)'))
    where = {'registers': 'flops', 'combinational': 'gates'}.get(flt.get('where', 'both'), flt.get('where', 'both'))
    horizon = flt.get('horizon') or flt.get('depth') or DEFAULT_HORIZON
    kmax = flt.get('max_faults', flt.get('search_k_up_to', DEFAULT_KMAX))
    checks = []
    for c in doc['checks']:
        kind = c.get('kind', 'fault')
        ch = dict(id=c['id'], kind=kind, explain=c.get('explain', ''), bad=c.get('bad'), must_hold=list(c.get('must_hold') or []),
                  detect_latency=int(c.get('detect_latency', 0)), assertions=None, fixed={}, width_of=None,
                  horizon=c.get('horizon') or horizon, kmax=c.get('max_faults', kmax), template=c.get('template'), raw=c,
                  goal=c.get('goal') or TPL.GOAL.get(c.get('template') or ''),
                  goal_source='stated' if c.get('goal') else ('template' if TPL.GOAL.get(c.get('template') or '') else None))
        if kind != 'fault':
            ch['not_run'] = 'the %s analysis is part of the file format but not of this release' % kind
            checks.append(ch); continue
        if c.get('template') and c['template'] != 'custom':
            ex = TPL.expand(c['template'], c.get('params') or {})
            ch['bad'] = ch['bad'] or ex['bad']
            ch['must_hold'] = ex['must_hold'] + ch['must_hold']
            ch['explain'] = ch['explain'] or ex['explain']
            ch['fixed'] = ex['fixed']
            ch['detect_latency'] = ch['detect_latency'] or ex.get('detect_latency', 0)
            ch['width_of'] = ex.get('width_of')
        if c.get('detected_by'):
            ch['must_hold'].append('!(%s)' % c['detected_by'])
        if c.get('assertions'):
            ap = os.path.join(base, c['assertions'])
            if not os.path.isfile(ap):
                raise GSError('GS003', 'assertion file %s does not exist' % c['assertions'])
            ch['assertions'] = ap
        if not ch['bad'] and not ch['assertions']:
            raise GSError('GS005', 'check `%s` has no condition' % c['id'],
                          help='give `bad: "<Verilog expression>"`, a `template` with its params, or `assertions: file.sv`')
        checks.append(ch)
    clock = doc.get('clock')
    if isinstance(clock, dict):
        clock = clock['port']
    reset = doc.get('reset')
    if isinstance(reset, dict):
        reset = dict(port=reset['port'], active=reset.get('active'), cycles=int(reset.get('cycles', 1)),
                     glitch_during_reset=bool(reset.get('glitch_during_reset', False)))
    ins = doc.get('inputs') or {}
    fixed = {k: v for k, v in (ins.get('fixed') or {}).items()}
    solver = doc.get('solver') or {}
    rep = doc.get('report') or {}
    spec = dict(
        path=path, base=base, name=doc.get('name') or os.path.basename(base), raw=raw, task=task,
        sources=srcs, top=d.get('top'), frontend=d.get('frontend', 'auto'), include_dirs=incs, defines=defs,
        params=dict(d.get('params') or {}), liberty=libs, blackboxes=bbs, yosys_script=d.get('yosys_script'),
        physical_cells=list(d['physical_cells'] if 'physical_cells' in d else
                            (PHYSICAL_DEFAULT if d.get('frontend') == 'netlist' else [])),
        netlist_input=d.get('frontend') == 'netlist',
        clock=clock, reset=reset, powerup=doc.get('powerup'),
        attacker=ins.get('attacker', 'all'), attacker_changes=ins.get('attacker_changes', 'every_cycle'),
        secret=list(ins.get('secret') or []), fixed=fixed, observe=doc.get('observe'),
        probes=dict(doc.get('probes') or {}), assets=doc.get('assets') or {},
        checks=checks, fault_types=types, where=where, include=list(flt.get('include') or []),
        exclude=list(flt.get('exclude') or []), horizon=horizon, kmax=kmax,
        flows=list(doc.get('flows') or (['netlist'] if d.get('frontend') in ('netlist', 'json') else ['plain'])),
        analyses=list(doc.get('analyses') or ['validate', 'min_faults', 'attack_surface', 'merge_lint', 'survival', 'unbounded']),
        backend=solver.get('backend', 'auto'), time_s=float(solver.get('time_s', 300)), workers=int(solver.get('workers', 1)),
        unbounded=doc.get('unbounded') or {}, validation=doc.get('validation') or {},
        redact=bool(rep.get('redact', False)), out=os.path.join(base, rep.get('out', '.glitchsat')),
    )
    stem = os.path.splitext(os.path.basename(path))[0]
    spec['work'] = os.path.join(spec['out'], *([] if stem == 'glitchsat' else [stem]), task or 'default')
    check_strings(spec)
    if spec['backend'] in ('cadical', 'kissat'):
        import shutil
        b = shutil.which(spec['backend'])
        if not b:
            raise GSError('GS002', 'solver %s is not installed' % spec['backend'], help='use `backend: auto` (built-in solver)')
        spec['backend'] = 'dimacs:' + b
    return spec, W
