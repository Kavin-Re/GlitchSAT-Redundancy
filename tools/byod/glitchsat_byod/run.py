"""`glitchsat run`: the whole pipeline for one project file.

  1 read glitchsat.yaml            5 generated monitor + wrapper, RTL reference
  2 elaborate, detect, resolve     6 validation by simulation (every flow)
  3 synthesise each flow           7 analyses: minimum faults, attack surface, merge lint, survival, unbounded
  4 import each netlist (Liberty)  8 report (JSON + text) and glitchsat.lock
"""
import hashlib
import json
import os
import platform
import sys
import time

from . import __version__
from . import analyses as AN
from . import compose as CO
from . import detect as DET
from . import flows as FL
from . import liberty as LIB
from . import netlist as NL
from . import project as PRJ
from . import validate as VAL
from .errors import GSError, GSWarning

_LIBCACHE = {}


def _lib(paths):
    key = tuple(paths)
    if key not in _LIBCACHE:
        try:
            _LIBCACHE[key] = LIB.load_many(list(paths)) if paths else None
        except LIB.LibertyError as e:
            raise GSError('GS043', str(e))
    return _LIBCACHE[key]


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


class Progress:
    def __init__(self, cb=None):
        self.cb = cb
        self.t0 = time.time()
        self.steps = []

    def __call__(self, msg, frac=None):
        self.steps.append(dict(t=round(time.time() - self.t0, 2), msg=msg))
        if self.cb:
            self.cb(msg, frac)


def import_flow(spec, flow, top, workdir, keep_sel, progress):
    progress('synthesising with flow `%s`' % flow)
    s = FL.synthesize(spec, flow, top, workdir, keep_sel)
    libs = list(s['libs']) + [l for l in spec['liberty'] if l not in s['libs']]
    lib = _lib(libs)
    blackboxes = [b['module'] for b in spec['blackboxes']]
    progress('reading the %s netlist into the fault model' % flow)
    R = NL.import_module(s['module'], top, lib, blackboxes=blackboxes, clock_ports=[CLOCK[0]] if CLOCK[0] else [])
    used = {cv['type'] for cv in s['module']['cells'].values()}
    checked = {}
    if lib:
        for t in sorted(used):
            if t in lib.cells and lib.cells[t].kind in ('comb', 'ff'):
                v = LIB.verify_cell(lib.cells[t])
                if v['ok'] is False:
                    raise GSError('GS042', 'Liberty cell %s failed its truth-table check: %s' % (t, v['detail']))
                checked[t] = v['rows']
    for t in sorted(used):
        if t in NL.YOSYS_CELLS:
            v = LIB.verify_cell(NL.YOSYS_CELLS[t])
            if v['ok'] is False:
                raise GSError('GS042', 'internal model of %s failed its truth-table check: %s' % (t, v['detail']))
            checked[t] = v['rows']
    if CLOCK[0]:
        ck = set(R.port_bits.get(CLOCK[0], []))
        bad = [n for n in R.clock_nets if n not in ck and not _is_clock_buffer(R, n, ck, s['module'])]
        if bad:
            raise GSError('GS013', 'flip-flops in flow %s are clocked by a net that is not the clock `%s`' % (flow, CLOCK[0]),
                          note='net: %s' % R.circ.names.get(bad[0], bad[0]),
                          help='gated or generated clocks are not modelled; use a clock enable instead')
        if len(R.edges) > 1:
            raise GSError('GS013', 'flip-flops use both clock edges in flow %s' % flow, help='only one clock edge is modelled')
    scan_ports = sorted({R.circ.inputs[n][0] for n in R.scan_enable_nets if n in R.circ.inputs})
    info = dict(flow=flow, yosys=s.get('yosys'), commands=s['commands'], netlist=os.path.relpath(s['json'], spec['base']),
                stats=NL.stats(R), cells_checked=checked, liberty=[dict(path=p, sha256=sha256(p)) for p in libs],
                risks=dict(R.risks), blackbox_outputs=[dict(cell=NL.pretty_cell(c), pin=p) for c, p, n in R.blackbox_outputs],
                blackbox_inputs=[dict(cell=NL.pretty_cell(c), pin=p) for c, p, n in R.blackbox_inputs],
                skipped_cells=dict(R.skipped), scan_enable_nets=len(R.scan_enable_nets), scan_enable_ports=scan_ports,
                scan_flops=R.scan_flops, physical_dropped=dict(spec.get('physical_dropped') or {}),
                normalised='dffunmap: enable and synchronous-reset flip-flops lowered to D flip-flops plus gates; '
                           'flip-flop fault site = stored value')
    return R, s, info


CLOCK = [None]


def _is_clock_buffer(R, net, ck, mod):
    """A clock net driven from the clock port through buffers/inverters only (clock tree cells)."""
    seen = set()
    n = net
    c = R.circ
    while isinstance(n, int) and n not in seen:
        seen.add(n)
        if n in ck:
            return True
        g = c.gates.get(n)
        if not g or g[0] not in ('AND', 'NOT', 'OR'):
            return False
        fi = [f for f in g[1] if f not in ('0', '1')]
        if len(set(fi)) != 1:
            return False
        n = fi[0]
    return False


def run_project(path, task=None, progress_cb=None, only=None, quick=False):
    """Returns the report dict. Raises GSError for input problems."""
    P = Progress(progress_cb)
    t0 = time.time()
    spec, warnings = PRJ.load(path, task)
    from .engine import gscale
    gscale()                                  # GS021 with the folders looked in, before any Yosys run
    if only:
        spec['analyses'] = [a for a in spec['analyses'] if a in only]
    work = spec['work']
    os.makedirs(work, exist_ok=True)
    P('reading the design')
    try:
        E = FL.elaborate(spec, work)
    except GSError as e:
        raise _explain_missing_cell(spec, e)
    top = E['top']
    spec['top_resolved'] = top
    fm = E['flat']['modules'][top]
    spec['design_names'] = sorted(set(list(fm.get('netnames') or {}) + list(fm.get('ports') or {}) + list(E['hier']['modules'])
                                      + [top] + [cn for m in E['hier']['modules'].values() for cn in (m.get('cells') or {})
                                                 if not cn.startswith('$')]))
    det = DET.detect(E['detect']['modules'][top])
    res = CO.resolve(spec, det, warnings)
    CLOCK[0] = res['clock']
    spec['top_ports'] = sorted(det['ports'])
    rep = dict(tool='GlitchSAT bring-your-own-design %s' % __version__, project=os.path.basename(path), name=spec['name'],
               task=task, top=top, frontend=E['frontend'], label='MEASURED', checks=[], warnings=[], flows={})
    rep['design'] = dict(ports={p: dict(direction=d, width=w) for p, (d, w) in det['ports'].items()}, flops_rtl=det['flops'],
                         roles=res['roles'], fixed={k: hex(v) for k, v in res['fixed'].items()}, clock=res['clock'],
                         reset=res['reset'], powerup=res['powerup'], attacker_changes=spec['attacker_changes'],
                         evidence=res['evidence'], suggested_secrets=det['secrets'], secret_like_registers=det['secret_regs'])
    # probes: resolve to modules for keep
    inst = FL.instance_modules(E['hier'], top)
    keep_sel, lock_probes = [], {}
    monitors = []
    for ch in spec['checks']:
        if ch.get('not_run'):
            continue
        M, text = CO.make_monitor(spec, ch, res, det, E['flat']['modules'][top])
        monitors.append((ch, M, text))
        for a, h in M.probe_names.items():
            path_, _, wire = h.rpartition('.')
            modn = inst.get(path_)
            if modn:
                keep_sel.append('%s/w:%s' % (modn, wire))
            lock_probes[h] = dict(alias=a, width=M.probe_widths.get(a), module=modn, wire=wire)
    keep_sel = sorted(set(keep_sel))
    # flows
    flows = {}
    for fl in spec['flows']:
        if fl not in FL.FLOWS:
            raise GSError('GS025', 'unknown flow `%s`' % fl, help='flows: ' + ', '.join(FL.FLOWS))
        try:
            flows[fl] = import_flow(spec, fl, top, work, keep_sel, P)
            rep['flows'][fl] = flows[fl][2]
            sa = [p for p in flows[fl][2]['scan_enable_ports'] if res['roles'].get(p) == 'attacker']
            flows[fl][2]['scan_enable_attacker'] = sa
            if sa and fl == spec['flows'][0]:
                warnings.append(GSWarning('GS073', 'the scan enable of %d flip-flop(s) is driven by attacker input %s'
                                          % (flows[fl][2]['scan_flops'], ', '.join(sa)),
                                          'tie it with `inputs.fixed` if it is a test pin'))
        except GSError as e:
            if fl == spec['flows'][0]:
                raise
            rep['flows'][fl] = dict(flow=fl, error=e.to_json())
            warnings.append(GSWarning(e.code, 'flow %s skipped: %s' % (fl, e.msg), e.help))
    main = spec['flows'][0]
    for ch, M, text in monitors:
        P('check `%s`: building the monitor' % ch['id'])
        cdir = os.path.join(work, 'check_' + ch['id'])
        os.makedirs(cdir, exist_ok=True)
        mv = os.path.join(cdir, 'glitchsat_monitor.v')
        open(mv, 'w').write(text)
        ms = FL.synth_small(mv, 'glitchsat_monitor', cdir, 'monitor')
        Mi = NL.import_module(ms['module'], 'glitchsat_monitor', None, clock_ports=[CO.MON.CLK])
        if ch.get('assertions'):
            asy = FL.synth_small(ch['assertions'], _first_module(ch['assertions']), cdir, 'assertions', formal=True)
            Ai = NL.import_module(asy['module'], 'assert', None, clock_ports=['clk', 'clk_i'])
            if not Ai.asserts:
                raise GSError('GS024', 'assertion file %s gives no assert/assume after elaboration' % os.path.basename(ch['assertions']))
            ch['assertion_count'] = {k: sum(1 for x in Ai.asserts if x['kind'] == k) for k in ('assert', 'assume')}
            Mi = _merge_assertions(Mi, Ai, asy['module'])
        probe_map = dict(M.probe_names)
        wrap = None
        ports = det['ports']
        pw = {a: (h, M.probe_widths[a]) for a, h in probe_map.items()}
        wtext = CO.MON.wrapper_verilog(top, ports, res['roles'], res['fixed'], res['reset'], spec['params'], M.used, pw)
        wv = os.path.join(cdir, 'glitchsat_wrap.v')
        open(wv, 'w').write(wtext + '\n' + text)
        crep = dict(id=ch['id'], explain=ch['explain'], bad=ch['bad'],
                    assertions=os.path.relpath(ch['assertions'], spec['base']) if ch.get('assertions') else None, must_hold=ch['must_hold'], horizon=ch['horizon'],
                    max_faults=ch['kmax'], template=ch['template'], goal=ch.get('goal'), goal_source=ch.get('goal_source'),
                    generated=dict(monitor=os.path.relpath(mv, spec['base']),
                                                                                 wrapper=os.path.relpath(wv, spec['base'])),
                    flows={}, analyses={}, detect_latency=ch['detect_latency'])
        if ch.get('assertion_count'):
            crep['assertion_count'] = ch['assertion_count']
        rep['checks'].append(crep)
        ref = None
        if 'validate' in spec['analyses'] and not ch.get('assertions'):
            P('check `%s`: elaborating the RTL reference (design + generated wrapper)' % ch['id'])
            conns = [(a, CO.MON.DUT + '.' + h) for a, h in probe_map.items()]
            rr = FL.reference(spec, wv, 'glitchsat_wrap', top, cdir, connects=conns)
            ref = NL.import_module(rr['module'], 'glitchsat_wrap', _lib(list(spec['liberty'])) if E['frontend'] == 'netlist' else None,
                                   blackboxes=[b['module'] for b in spec['blackboxes']], clock_ports=[CO.MON.CLK], allow_x=True)
        for fl, (R, s, info) in flows.items():
            frep = crep['flows'].setdefault(fl, {})
            mode_an = 'from_powerup' if (res['reset'] and res['reset']['glitch_during_reset']) else 'after_reset'
            try:
                X = CO.compose(spec, res, R, s['module'], Mi, ch, probe_map, mode=mode_an, warnings=warnings)
            except GSError as e:
                if fl == main:
                    raise
                frep['error'] = e.to_json(); continue
            frep['sites'] = X.site_stats
            frep['reset_state'] = X.reset_state
            if ref is not None:
                P('check `%s`, flow %s: validating by simulation against the RTL' % (ch['id'], fl))
                Xv = CO.compose(spec, res, R, s['module'], Mi, ch, probe_map, mode='from_powerup', warnings=[])
                cyc = int(spec['validation'].get('cycles') or (ch['horizon'] + (res['reset']['cycles'] if res['reset'] else 0)))
                try:
                    frep['validation'] = VAL.run(Xv, ref, res, det['ports'], cyc, runs=int(spec['validation'].get('runs', 256)),
                                                 seed=int(spec['validation'].get('seed', 1)))
                    frep['validation']['label'] = 'MEASURED (simulation)'
                except GSError as e:
                    e = _explain_mismatch(spec, E, R, s, e, ref_yosys=rr.get('yosys'))
                    if fl == main:
                        raise e
                    frep['validation'] = dict(error=e.to_json()); continue
            frep['_X'] = X
        X = crep['flows'][main]['_X']
        AN.run_all(spec, res, ch, crep, flows, main, P, quick=quick)
        for fl in crep['flows'].values():
            fl.pop('_X', None)
        from . import report as RP
        crep['what_to_do'] = RP.remedies(crep, rep['flows'])
    for ch in spec['checks']:
        if ch.get('not_run'):
            rep['checks'].append(dict(id=ch['id'], kind=ch['kind'], status='NOT_RUN', why=ch['not_run'], explain=ch.get('explain'),
                                      goal=ch.get('goal'), goal_source=ch.get('goal_source')))
    rep['warnings'] = [w.to_json() for w in warnings]
    spec['files_read'] = files_read(spec)
    rep['provenance'] = provenance(spec, E, flows, t0)
    rep['progress'] = P.steps
    rep['summary'] = summarize(rep)
    lock = write_lock(spec, E, res, det, lock_probes, flows, rep)
    rep['lock'] = lock
    return rep, spec


def check_names(spec, warnings):
    """`glitchsat check`: read the design (Yosys, no synthesis) and resolve every name the project uses: clock, reset,
    attacker/secret/fixed inputs, template inputs and every signal in a condition. Raises the same GS011/GS017 errors
    as `run`. Returns a short summary."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='glitchsat_check_') as work:
        E = FL.elaborate(dict(spec, out=work), work)
        top = E['top']
        det = DET.detect(E['detect']['modules'][top])
        res = CO.resolve(spec, det, warnings)
        n = 0
        for ch in spec['checks']:
            if ch.get('not_run') or ch.get('assertions'):
                continue
            CO.make_monitor(spec, ch, res, det, E['flat']['modules'][top])
            n += 1
    ins = [p for p, (d, w) in det['ports'].items() if d == 'input']
    outs = [p for p, (d, w) in det['ports'].items() if d == 'output']
    return dict(top=top, inputs=len(ins), outputs=len(outs), clock=res['clock'], reset=(res['reset'] or {}).get('port'),
                conditions=n, yosys=E['ys'].short())


def _first_module(p):
    import re
    m = re.search(r'^\s*module\s+([A-Za-z_]\w*)', open(p).read(), re.M)
    if not m:
        raise GSError('GS024', 'no module in assertion file %s' % p)
    return m.group(1)


def _merge_assertions(Mi, Ai, amod):
    """Assertions as the monitor: the checker module's ports are top-level names; asserts -> bad, assumes -> ok."""
    from .engine import gscale
    G = gscale()
    c = Ai.circ
    nb = max([Ai.next_free] + [0]) + 1
    b0 = nb; c.gates[b0] = ('AND', ('0', '0'))
    o1 = nb + 1; c.gates[o1] = ('OR', ('1', '1'))
    c.ports[CO.MON.BAD] = ('output', [b0]); c.ports[CO.MON.OK] = ('output', [o1])
    Ai.next_free = nb + 2
    return Ai


def provenance(spec, E, flows, t0):
    import shutil
    srcs = [dict(path=os.path.relpath(p, spec['base']), sha256=sha256(p)) for p in spec['sources']]
    eng = {}
    try:
        from .engine import gscale, repo_root
        G = gscale()
        eng['gscale'] = G.__version__
        eng['repository'] = repo_root()
    except Exception as e:                    # noqa: BLE001
        eng['error'] = str(e)
    extra = [dict(path=os.path.relpath(p, spec['base']), sha256=sha256(p)) for p in spec.get('files_read') or []
             if p not in spec['sources']]
    return dict(sources=srcs, files_read=extra, project_sha256=sha256(spec['path']), frontend=E['frontend'], yosys_elab=E['ys'].short(),
                elab_commands=E['commands'], python=sys.version.split()[0], platform=platform.platform(),
                solvers=dict(backend=spec['backend'], cadical=shutil.which('cadical'), kissat=shutil.which('kissat')),
                engines=eng, flows={k: dict(commands=v[2]['commands'], yosys=v[2]['yosys'], liberty=v[2]['liberty'],
                                            blackboxes=v[2]['blackbox_outputs'], skipped_cells=v[2]['skipped_cells'])
                                    for k, v in flows.items()},
                network='none: GlitchSAT makes no network connections',
                runtime_s=round(time.time() - t0, 2))


def summarize(rep):
    out = []
    worst = 0
    for c in rep['checks']:
        if c.get('status') == 'NOT_RUN':
            out.append(dict(check=c['id'], verdict='NOT_RUN'))
            continue
        mf = c['analyses'].get('min_faults', {})
        v = mf.get('verdict', 'NOT_RUN')
        out.append(dict(check=c['id'], verdict=v, min_faults=mf.get('min_faults'), bound=mf.get('max_faults'),
                        horizon=c['horizon']))
        if v in ('ATTACK_FOUND', 'FAILS_WITHOUT_FAULTS'):
            worst = max(worst, 1)
        elif v not in ('NO_ATTACK_UP_TO_BOUND',):
            worst = max(worst, 2)
    return dict(checks=out, exit_code=worst)


def files_read(spec):
    """Every file the analysis depends on: sources, `include files (followed through the include folders), black-box
    stubs, assertion files, filelists and Liberty files."""
    import re
    out, seen = [], set()

    def add(p):
        p = os.path.normpath(p)
        if p not in seen and os.path.isfile(p):
            seen.add(p); out.append(p)
            return True
        return False
    todo = list(spec['sources'])
    for p in todo:
        add(p)
    while todo:
        f = todo.pop(0)
        if f.endswith('.json'):
            continue
        try:
            text = open(f, errors='replace').read()
        except OSError:
            continue
        for inc in re.findall(r'`include\s+"([^"]+)"', text):
            for d in [os.path.dirname(f)] + list(spec['include_dirs']):
                q = os.path.join(d, inc)
                if os.path.isfile(q):
                    if add(q):
                        todo.append(os.path.normpath(q))
                    break
    for b in spec['blackboxes']:
        if b.get('stub'):
            add(b['stub'])
    for c in spec['checks']:
        if c.get('assertions'):
            add(c['assertions'])
    for x in (spec['raw'].get('design') or {}).get('sources') or []:
        if isinstance(x, dict) and x.get('filelist'):
            add(os.path.join(spec['base'], x['filelist']))
    return out


def _lib_key(p, spec):
    """Liberty files are recorded relative to $GLITCHSAT_LIBS or to the project, so locks are portable."""
    from .flows import libs_dir
    for f in (os.path.abspath, os.path.realpath):
        for root, tag in ((libs_dir(), '$GLITCHSAT_LIBS'), (spec['base'], '.')):
            r, rp = f(root), f(p)
            if rp.startswith(r + os.sep):
                return tag + '/' + os.path.relpath(rp, r)
    return os.path.basename(p)


def lock_path(spec):
    stem = os.path.splitext(os.path.basename(spec['path']))[0]
    return os.path.join(spec['base'], stem + ('.%s' % spec['task'] if spec['task'] else '') + '.lock')


def write_lock(spec, E, res, det, probes, flows, rep):
    from . import __version__
    checks = {}
    for c in spec['checks']:
        checks[c['id']] = dict(kind=c['kind'], template=c.get('template'), bad=c.get('bad'), must_hold=c.get('must_hold'),
                               detect_latency=c.get('detect_latency'), horizon=c.get('horizon'), max_faults=c.get('kmax'),
                               assertions=os.path.relpath(c['assertions'], spec['base']) if c.get('assertions') else None)
    lock = dict(glitchsat_lock=2, glitchsat_version=__version__, project=os.path.basename(spec['path']),
                project_sha256=sha256(spec['path']), task=spec['task'], top=E['top'],
                frontend=E['frontend'], clock=res['clock'], reset=res['reset'], powerup=res['powerup'],
                roles=res['roles'], fixed={k: v for k, v in res['fixed'].items()}, probes=probes,
                checks=checks,
                faults=dict(types=spec['fault_types'], where=spec['where'], include=spec['include'], exclude=spec['exclude'],
                            attacker_changes=spec['attacker_changes'], normalisation='dffunmap; flip-flop site = stored value'),
                flows=list(spec['flows']), analyses=list(spec['analyses']),
                yosys=dict(elaborate=E['ys'].short(), **{fl: v[2].get('yosys') for fl, v in flows.items()}),
                sources={os.path.relpath(p, spec['base']): sha256(p) for p in spec['sources']},
                files={os.path.relpath(p, spec['base']): sha256(p) for p in spec.get('files_read') or [] if p not in spec['sources']},
                liberty={_lib_key(p, spec): sha256(p) for p in spec['liberty']},
                selectors=dict(include=spec['include'], exclude=spec['exclude'],
                               sites_per_check={c['id']: {fl: d.get('sites') for fl, d in c.get('flows', {}).items()}
                                                for c in rep['checks'] if 'flows' in c}),
                blackboxes={fl: v[2]['blackbox_outputs'] for fl, v in flows.items()},
                validation=dict(spec['validation']), solver=dict(backend=spec['backend'].split(':')[0], time_s=spec['time_s']))
    p = lock_path(spec)
    changes = []
    lock = json.loads(json.dumps(lock, sort_keys=True, default=str))
    if os.path.isfile(p):
        try:
            old = json.load(open(p))
            for k in sorted(set(lock) | set(old)):
                if old.get(k) != lock.get(k):
                    changes.append(k)
        except ValueError:
            changes.append('(unreadable old lock)')
    with open(p, 'w') as f:
        json.dump(lock, f, indent=1, sort_keys=True, default=str)
    return dict(path=os.path.basename(p), changed_since_last_run=changes)


def _explain_missing_cell(spec, e):
    """GS023 for a cell that IS in the Liberty file but has no function GlitchSAT or Yosys can use (clock gate, ...)."""
    if e.code != 'GS023' or not spec['liberty']:
        return e
    import re
    m = re.search(r'module `([^`]+)`', e.msg)
    if not m:
        return e
    try:
        lib = _lib(list(spec['liberty']))
    except GSError:
        return e
    c = lib.cells.get(m.group(1)) if lib else None
    if c is None:
        return e
    why = c.why if getattr(c, 'why', None) else ('it has no logic function' if c.kind == 'none' else c.kind)
    icg = 'statetable' in str(why) or 'clock' in str(why) or 'dlclkp' in c.name
    return GSError('GS040', 'cell `%s` is in the Liberty file but cannot be modelled: %s' % (c.name, why),
                   help=('gated clocks are not modelled: synthesise without clock gating (no ICG cells) for the analysis'
                         if icg else 'if it is a physical-only cell, add its type to `design.physical_cells`; otherwise '
                                     'use a netlist without this cell'))


def _explain_mismatch(spec, E, R, s, e, ref_yosys=None):
    """GS050 help that fits the case; GS046 when the reference Yosys misreads a clear+preset Liberty flip-flop."""
    if e.code != 'GS050':
        return e
    if E['frontend'] == 'netlist':
        lib = _lib(list(spec['liberty']))
        used = {cv['type'] for cv in s['module']['cells'].values()}
        both = sorted(t for t in used if lib and t in lib.cells and lib.cells[t].kind == 'ff'
                      and lib.cells[t].ff.get('clear') is not None and lib.cells[t].ff.get('preset') is not None
                      and lib.cells[t].ff.get('cpv1') not in ('L', None))
        y = FL.yosys_for(spec)
        if both and y.vnum < (0, 71):
            return GSError('GS046', '%s reads the Liberty clear/preset rule of %s wrongly, so the reference for this netlist '
                           'is wrong (%s)' % (y.short(), ', '.join(both), e.msg),
                           help='install Yosys 0.71 or newer, or point GLITCHSAT_YOSYS at it: GlitchSAT uses the newest Yosys '
                                'it finds for gate-level netlists (more: glitchsat explain GS046)')
        e.help = ('the reference is Yosys\'s own reading of the same cells, so this is a difference between that reading and '
                  'the Liberty functions GlitchSAT uses, or in the generated wrapper; compare %s with the reference netlist '
                  'in .glitchsat/' % os.path.relpath(s['json'], spec['base']))
        return e
    if not spec['probes'] and not any('.' in (c.get('bad') or '') for c in spec['checks']):
        e.help = ('no probe is used, so this is a synthesis or wrapper mismatch: compare %s with the reference netlist '
                  '(check_<id>/reference/netlist.json); a custom flow that changes the logic also gives this'
                  % os.path.relpath(s['json'], spec['base']))
    return e
