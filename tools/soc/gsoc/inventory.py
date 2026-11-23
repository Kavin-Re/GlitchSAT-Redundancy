"""Whole-chip linear scans: countermeasure inventory with survival verdicts, and merge lint.

Nothing here is re-implemented: the scans are those of ext/checker (survival.intent_rtl, survival.stage_netlist,
survival.pipeline) and ext/surface (merge_lint), run on the whole-chip netlists of every flow.

  inventory   every hardened structure the checker recognises, from two sources:
                rtl-scan      declared in the RTL of the chip (instances with the same inputs, sparse state
                              codes, multi-bit booleans, x / x_n register pairs, alarm ports);
                netlist-scan  visible in the netlist alone (nets computing one function through disjoint logic,
                              complemented rails, registers with sparse reachable codes).
              Netlist-scan entries on a whole chip include incidental duplication (two unrelated places that
              happen to compute the same function); they are listed as "found by structure", not as intent.
  survival    each rtl-scan entry is followed through the flows (written -> keep -> flat): SURVIVED / WEAKENED /
              REMOVED / UNTRACKED, with the checker's evidence.
  merge lint  for every goal that names its decision register: do the redundant copies in front of that register
              still use separate logic in each flow? (ext/surface/scripts/merge_lint.py on the exported cone.)
"""
import json
import os
import re
import sys
import time

from . import SOC, EXT, frontend, chip as chipmod, run, slicer, gscale

G = gscale()
C = G.circuit


def _checker():
    p = os.environ.get('GLITCHSAT_CHECKER') or os.path.join(EXT, 'checker')
    if p not in sys.path:
        sys.path.insert(0, p)
    from survival import pipeline, intent_rtl, gnet, stage_netlist
    return pipeline, intent_rtl, gnet, stage_netlist


def _merge_lint():
    p = os.environ.get('GLITCHSAT_SURFACE') or os.path.join(EXT, 'surface', 'scripts')
    if p not in sys.path:
        sys.path.insert(0, p)
    import merge_lint
    return merge_lint


def rtl_files(netlist_path):
    """Source files named by the `src` attributes of the netlist: the RTL that actually ended up in the chip.
    Returns (files, {file: set of line numbers that left a trace in the netlist})."""
    with open(netlist_path) as f:
        doc = json.load(f)
    lines = {}
    rx = re.compile(r'^(.*\.s?v):(\d+)')
    for m in doc['modules'].values():
        for group in (m['cells'], m['netnames']):
            for x in group.values():
                for part in str((x.get('attributes') or {}).get('src', '')).split('|'):
                    mm = rx.match(part)
                    if mm:
                        fn = mm.group(1) if os.path.isabs(mm.group(1)) else os.path.join(SOC, mm.group(1))
                        lines.setdefault(os.path.normpath(fn), set()).add(int(mm.group(2)))
    files = sorted(fn for fn in lines if os.path.isfile(fn))
    return files, lines


def module_in_chip(where, lines):
    """True when the module that contains the declaration `file:line` left at least one cell or net in the netlist
    (a file can hold modules that this chip variant does not instantiate)."""
    try:
        fn, ln = where.rsplit(':', 1)
        ln = int(ln)
        fn = os.path.normpath(fn if os.path.isabs(fn) else os.path.join(SOC, fn))
        text = open(fn, errors='replace').read().split('\n')
    except (ValueError, OSError):
        return True
    lo, hi = 1, len(text)
    for i in range(ln - 1, -1, -1):
        if re.match(r'\s*(\(\*.*\*\)\s*)?module\b', text[i]):
            lo = i + 1; break
    for i in range(ln - 1, len(text)):
        if re.match(r'\s*endmodule\b', text[i]):
            hi = i + 1; break
    return any(lo <= x <= hi for x in lines.get(fn, ()))


def checker_view(netlist_path, top):
    """The checker reads gates and flops only. A netlist with black boxes (large memories, clock-gate latches) is
    copied with each black box removed and its output bits turned into an input port `blackbox_out`, which is the
    same free-value treatment the loader applies. Returns the path to use (the original when nothing changes)."""
    with open(netlist_path) as f:
        doc = json.load(f)
    m = doc['modules'][top]
    drop, outs = [], []
    for cn, cell in m['cells'].items():
        t = cell.get('type')
        if t == '$scopeinfo' or t in chipmod._GATES or chipmod.flop_kind(t)[0]:
            continue
        drop.append(cn)
        dirs = cell.get('port_directions') or {}
        for p, v in (cell.get('connections') or {}).items():
            if dirs.get(p) == 'output':
                outs += [b for b in v if isinstance(b, int)]
    if not drop:
        return netlist_path
    for cn in drop:
        del m['cells'][cn]
    m['ports']['blackbox_out'] = dict(direction='input', bits=outs)
    m['netnames']['blackbox_out'] = dict(bits=outs, attributes={}, hide_name=0)
    out = netlist_path[:-5] + '.checker_view.json'
    with open(out, 'w') as f:
        json.dump({'modules': {top: m}}, f)
    return out


def export_engine_json(circ, keep, goal_bits, path, top='decision_cone', aliases=None):
    """The part `keep` of a Circuit as a Yosys JSON netlist in the engine's own format (five gate types and
    $_DFF_P_), with one output port `boot_word` holding the decision bits. Flops outside `keep` become inputs."""
    cells, names = {}, {}
    T = {C.AND: '$_AND_', C.OR: '$_OR_', C.XOR: '$_XOR_', C.NOT: '$_NOT_', C.MUX: '$_MUX_'}
    ins = []
    k = 0
    for b in sorted(keep):
        if b in circ.gates:
            op, fi = circ.gates[b]
            if op == C.MUX: con = {'S': [fi[0]], 'B': [fi[1]], 'A': [fi[2]], 'Y': [b]}
            elif op == C.NOT: con = {'A': [fi[0]], 'Y': [b]}
            else: con = {'A': [fi[0]], 'B': [fi[1]], 'Y': [b]}
            cells['g%d' % k] = dict(type=T[op], connections=con, port_directions={p: ('output' if p == 'Y' else 'input') for p in con})
            k += 1
            for f in fi:
                if isinstance(f, int) and f not in keep and f not in ins: ins.append(f)
        else:
            if b not in ins: ins.append(b)
        names[circ.name(b)] = dict(bits=[b], attributes={}, hide_name=0)
        for a in (aliases or {}).get(b, ()):
            names.setdefault(a, dict(bits=[b], attributes={}, hide_name=0))
    for b in ins:
        names.setdefault(circ.name(b), dict(bits=[b], attributes={}, hide_name=0))
    ports = {'clk': dict(direction='input', bits=[max(list(keep) + ins + [1]) + 1])}
    groups = {}
    for b in ins:
        if b in circ.inputs and not circ.inputs[b][0].startswith('$'):
            groups.setdefault(circ.inputs[b][0], []).append(b)
        else:
            groups.setdefault('state', []).append(b)        # flop outputs and free values feeding the cone
    for p, bits in groups.items():
        ports[p if p != 'clk' else 'clk_in'] = dict(direction='input', bits=bits)
    ports['boot_word'] = dict(direction='output', bits=list(goal_bits))
    doc = dict(creator='gsoc export', modules={top: dict(attributes={}, ports=ports, cells=cells, netnames=names)})
    with open(path, 'w') as f:
        json.dump(doc, f)
    return path


def decision_lint(sess, goal, workdir):
    """Merge lint on the logic in front of the goal's decision register (goal['decision'] = register name)."""
    ML = _merge_lint()
    ch = sess.chip
    reg = ch.word(goal['decision'])
    circ = ch.circ
    dnets = []
    for q in reg:
        if q not in circ.flops:
            raise chipmod.ChipError('%s is not a register in this netlist' % goal['decision'])
        dnets.append(circ.flops[q][0])
    keep = set()
    stack = [d for d in dnets if isinstance(d, int)]
    while stack:
        b = stack.pop()
        if b in keep or b not in circ.gates:
            continue
        keep.add(b)
        stack.extend(f for f in circ.gates[b][1] if isinstance(f, int))
    path = os.path.join(workdir, '%s.%s.decision.json' % (ch.name, goal['id']))
    export_engine_json(circ, keep, dnets, path, aliases=ch.aliases)
    nl = ML.load(path, 'decision_cone')
    r = ML.lint(nl, goal_out='boot_word', copy_re=goal.get('copy_re', ML.DEFAULT_COPY_RE), netlist_path=path)
    keepk = ('mode', 'verdict', 'findings', 'identical_copies', 'structural_groups', 'runtime_s')
    out = {k: r.get(k) for k in keepk}
    out['copies'] = {lab: dict(cone_size=v.get('cone_size'), decision_bits=v.get('decision_bits')) for lab, v in (r.get('copies') or {}).items()}
    out['single_points'] = [dict(net=s['net'], kind=s['kind'], copies=s['copies']) for s in (r.get('single_points') or [])][:20]
    out['single_point_count'] = len(r.get('single_points') or [])
    out['shared_net_count'] = len(r.get('shared_nets') or [])
    out['decision_register'] = goal['decision']
    out['cone_gates'] = len(keep)
    return out


def run_inventory(cfg, variant, force=False, max_netlist_scan=60):
    path = os.path.join(run.RUNS, '%s.%s.inventory.json' % (cfg['name'], variant or 'default'))
    if os.path.exists(path) and not force:
        return run._load(path)
    pipeline, intent_rtl, gnet, stage_netlist = _checker()
    flows = list(cfg.get('flows') or ['flat'])
    work = os.path.join(run.WORK, cfg['name'])
    nets = {fl: frontend.run(cfg, fl, work, run.src_root(cfg), variant)['netlist'] for fl in flows}
    t0 = time.time()
    files, src_lines = rtl_files(nets[flows[0]])
    top = frontend.top_of(cfg, variant)
    nets = {fl: checker_view(p, top) for fl, p in nets.items()}
    pcfg = dict(name=cfg['name'], top=None, intent=dict(rtl=files, reference='given'),
                stages=[dict(name=fl, netlist=nets[fl], reference=(i == 0)) for i, fl in enumerate(flows)])
    rep = pipeline.run(pcfg, base=SOC, workdir=os.path.join(work, 'survival_' + (variant or 'default')),
                       want_margin=False, log=lambda *a, **k: None)
    survival_s = round(time.time() - t0, 1)
    cms = []
    skipped = 0
    for c in rep['countermeasures']:
        if c.get('where') and not module_in_chip(c['where'], src_lines):
            skipped += 1
            continue
        cms.append(dict(id=c['id'], kind=c['kind'], title=c.get('title'), origin=c['origin'],
                        where=os.path.relpath(c['where'], SOC) if c.get('where') and os.path.isabs(c['where'].split(':')[0]) else c.get('where'),
                        module=(c.get('intent') or {}).get('module'), verdict=c.get('verdict'), broken_at=c.get('broken_at'),
                        stages=[dict(stage=s['stage'], verdict=s['verdict'], evidence=[str(e)[:300] for e in (s.get('evidence') or [])[:4]],
                                     cause=(s.get('cause') or '')[:400], label=s.get('label')) for s in c.get('stages') or []]))
    rv = cfg.get('reviewed') or {}
    for c in cms:
        for pat, note in rv.items():
            if pat in c['id']:
                c['reviewed'] = note
    # netlist scan per flow
    scans = {}
    for fl in flows:
        t1 = time.time()
        g = gnet.load(nets[fl], top)
        found = stage_netlist.detect(g)
        rows = []
        for cm in found:
            i = cm.intent
            rows.append(dict(id=cm.id, kind=cm.kind, title=cm.title(), nets=(i.get('nets') or [])[:6],
                             register=i.get('register'), codes=len(i.get('codes') or []) or None,
                             min_distance=i.get('min_distance')))
        kinds = {}
        for r in rows: kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
        scans[fl] = dict(found=len(rows), by_kind=kinds, items=rows[:max_netlist_scan], seconds=round(time.time() - t1, 1),
                         cells=g.stats().get('cells'))
        del g
    # merge lint per goal with a decision register
    lint = {}
    for g_ in run.goals_of(cfg, variant):
        if not g_.get('decision') or (g_.get('variants_decision') and variant not in g_['variants_decision']):
            continue
        for fl in flows:
            s = run.Session(cfg, variant, fl)
            try:
                lint.setdefault(g_['id'], {})[fl] = decision_lint(s, g_, work)
            except (chipmod.ChipError, ValueError) as e:
                lint.setdefault(g_['id'], {})[fl] = dict(verdict='not_run', findings=[str(e)])
    counts = {}
    for c in cms: counts[c['verdict']] = counts.get(c['verdict'], 0) + 1
    by_kind = {}
    for c in cms: by_kind[c['kind']] = by_kind.get(c['kind'], 0) + 1
    rec = dict(schema='glitchsat-soc-inventory/1', chip=cfg['name'], variant=variant, flows=flows, label='MEASURED',
               rtl_files_scanned=len(files), rtl_scan=dict(found=len(cms), by_kind=by_kind, verdicts=counts, items=cms,
                                                           seconds=survival_s, stages=[s['name'] for s in rep['stages']]),
               netlist_scan=scans, merge_lint=lint,
               reviewed=sum(1 for c in cms if c.get('reviewed')), declared_in_modules_not_in_this_chip=skipped,
               note='rtl-scan entries are declared intent; netlist-scan entries are structure only and include '
                    'incidental duplication. A SURVIVED verdict says the structure is intact, not that the chip is secure.')
    run._save(path, rec)
    return rec


def format_text(r):
    L = ['%s / %s: %d RTL files scanned' % (r['chip'], r['variant'], r['rtl_files_scanned'])]
    rs = r['rtl_scan']
    L.append('  countermeasures declared in RTL: %d  %s  verdicts over flows %s: %s' % (rs['found'], rs['by_kind'], '->'.join(r['flows']), rs['verdicts']))
    for c in rs['items'][:40]:
        L.append('    %-9s %-58s %s%s' % (c['verdict'], (c['title'] or c['id'])[:58], ' '.join('%s=%s' % (s['stage'], s['verdict']) for s in c['stages']),
                                         '   [reviewed]' if c.get('reviewed') else ''))
    for fl, s in r['netlist_scan'].items():
        L.append('  found by structure in flow %s: %d %s (%.1f s)' % (fl, s['found'], s['by_kind'], s['seconds']))
    for gid, d in r['merge_lint'].items():
        for fl, x in d.items():
            L.append('  merge lint %s / %s: %s (%s single point(s))' % (gid, fl, x.get('verdict'), x.get('single_point_count')))
    return '\n'.join(L)
