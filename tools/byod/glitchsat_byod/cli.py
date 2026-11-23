"""glitchsat: use GlitchSAT on your own chip design.

  glitchsat init [--from-tinytapeout DIR] [--yes]   questions -> a commented glitchsat.yaml
  glitchsat run [glitchsat.yaml] [--task T]          the analysis; results in .glitchsat/
  glitchsat explain [report.json | GSxxx]           plain-language summary of a result, or what an error code means
  glitchsat check [glitchsat.yaml]                   validate the project file and, with Yosys, every name in it
                                                     (clock, reset, inputs, signals in conditions); no analysis
  glitchsat doctor                                   what is installed and where (Yosys, engines, solvers)
  glitchsat templates [NAME]                         property templates with explanations
  glitchsat examples list | copy NAME [DIR]          the gallery
  glitchsat flows                                    synthesis flows
  glitchsat liberty FILE.lib [--cell C]              read a Liberty file and check every cell by truth table
  glitchsat import-sby FILE.sby | import-synfi fault_model.json    starting points from other tools

Exit codes: 0 no attack within the bound (or command done); 1 an attack was found (or the design fails without
faults); 2 undecided or incomplete; 3 input error (the message says what to fix); 4 internal error.
GlitchSAT makes no network connections.
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
EXAMPLES = os.path.join(PKG, 'examples')
TEMPLATES = os.path.join(PKG, 'templates')


def _err(e):
    print(e.render(), file=sys.stderr)
    return 3


def cmd_run(a):
    from .errors import GSError
    from .run import run_project
    from . import report as RP
    path = a.project or 'glitchsat.yaml'
    quiet = a.json_only
    if getattr(a, 'allow_outside', False):
        os.environ['GLITCHSAT_ALLOW_OUTSIDE'] = '1'

    def prog(msg, frac=None):
        print('  ... ' + msg, file=sys.stderr, flush=True)
    try:
        rep, spec = run_project(path, a.task, prog, only=a.only.split(',') if a.only else None, quick=a.quick)
    except GSError as e:
        return _err(e)
    names = spec.get('design_names', [])
    if a.redact or spec.get('redact'):
        rep, mapping = RP.redact(rep, names, redact_extra(spec))
        rep['redacted'] = dict(aliases=len(mapping), note='design names, file names, paths, secret values and constants in '
                               'conditions replaced by aliases; the alias table is not stored. glitchsat.lock and .glitchsat/ '
                               'are not redacted.')
        print('NOTE: --redact covers the printed report, report.json and report.txt only. The work folder %s and the lock '
              'file keep every real name: share only the report files, never a zip of the project folder.'
              % os.path.relpath(spec['work']), file=sys.stderr)
    rep['plain_findings'] = RP.plain_findings(rep)          # plain words, severity, how it was found (for every reader)
    for f in rep['plain_findings']:                          # "where", shown in context: the source lines, the hit marked
        w = f.get('where') or {}
        if w.get('file') and w.get('line') and not (a.redact or spec.get('redact')):
            cand = [s_ for s_ in spec['sources'] if os.path.basename(s_) == os.path.basename(w['file'])]
            try:
                src = open(cand[0], encoding='utf-8', errors='replace').read().splitlines() if cand else []
            except OSError:
                src = []
            n = int(w['line'])
            if 0 < n <= len(src):
                w['context'] = [dict(line=i + 1, text=src[i], hit=(i + 1 == n)) for i in range(max(0, n - 3), min(len(src), n + 2))]
            else:
                w['missing_note'] = (w.get('missing_note') or '') + ' The source file was not found to show the line.'
    if a.sarif:
        pfm = RP.plain_findings_module()
        if pfm:
            with open(a.sarif, 'w') as f:
                json.dump(pfm.to_sarif(rep['plain_findings'], 'glitchsat', rep.get('tool', {}).get('version', '') if isinstance(rep.get('tool'), dict) else ''), f, indent=1)
    out = spec['work']
    os.makedirs(out, exist_ok=True)
    jp = os.path.join(out, 'report.json')
    with open(jp, 'w') as f:
        f.write(RP.to_json(rep))
    txt = RP.plain(rep)
    with open(os.path.join(out, 'report.txt'), 'w') as f:
        f.write(txt)
    if a.json:
        with open(a.json, 'w') as f:
            f.write(RP.to_json(rep))
    if quiet:
        print(RP.to_json(rep))
    else:
        print(txt)
        print('Full result: %s (plain text: report.txt). Lock file: %s%s' % (os.path.relpath(jp), rep['lock']['path'],
              ('; changed since last run: ' + ', '.join(rep['lock']['changed_since_last_run'])) if rep['lock']['changed_since_last_run'] else ''))
    return rep['summary']['exit_code']


def redact_extra(spec):
    from .engine import repo_root
    from .flows import libs_dir
    files = list(spec['sources']) + list(spec['liberty']) + [b['stub'] for b in spec['blackboxes'] if b.get('stub')]
    files += [c['assertions'] for c in spec['checks'] if c.get('assertions')] + list(spec.get('files_read') or [])
    stem = os.path.splitext(os.path.basename(spec['path']))[0]
    words = [spec['name'], spec.get('task') or '', spec.get('top_resolved') or '', stem if stem != 'glitchsat' else '']
    words += [os.path.basename(d) for d in spec['include_dirs']] + list(spec['probes'].values())
    roots = [spec['base'], os.path.dirname(spec['base']), repo_root() or '', PKG, libs_dir(), os.path.expanduser('~')]
    roots += [os.path.dirname(f) for f in files]
    return dict(files=files, checks=[c['id'] for c in spec['checks']],
                secret_ports=[p for p in spec['secret']], roots=[r for r in roots if r and r != os.sep], words=[w for w in words if w])


def cmd_check(a):
    from .errors import GSError
    from . import project as PRJ
    try:
        spec, W = PRJ.load(a.project or 'glitchsat.yaml', a.task)
    except GSError as e:
        return _err(e)
    name = os.path.basename(spec['path'])
    head = '%s: file format valid. %d check(s), flows %s, horizon %d cycles, up to %d faults.' % (
        name, len(spec['checks']), ', '.join(spec['flows']), spec['horizon'], spec['kmax'])
    if spec.get('yosys_script'):
        head += '\nThis project runs its own Yosys commands (flow `custom`); each was checked against the allow-list:'
        from .flows import user_script
        head += ''.join('\n    ' + c for c in user_script(spec))
    from .flows import find_yosys
    try:
        find_yosys()
    except GSError:
        print(head)
        print('Names NOT checked: Yosys was not found, so the design could not be read. The clock, reset, inputs and the '
              'signals in conditions are checked when Yosys is installed (`glitchsat check` again, or `glitchsat run`).')
        for w in W:
            print(w.render())
        return 2
    from .run import check_names
    try:
        r = check_names(spec, W)
    except GSError as e:
        print(head)
        return _err(e)
    print(head)
    print('Names checked against the design read by %s: top `%s` (%d inputs, %d outputs), clock %s, reset %s, '
          '%d condition(s) resolved.' % (r['yosys'], r['top'], r['inputs'], r['outputs'], '`%s`' % r['clock'] if r['clock'] else 'none',
                                         '`%s`' % r['reset'] if r['reset'] else 'none', r['conditions']))
    for w in W:
        print(w.render())
    return 0


def cmd_doctor(a):
    from .engine import doctor
    lines, ok = doctor()
    for ln in lines:
        print(ln)
    print('Ready.' if ok else 'Not ready: see the MISSING lines above.')
    return 0 if ok else 3


def cmd_explain(a):
    from .errors import explain
    from . import report as RP
    t = a.what or os.path.join('.glitchsat', 'default', 'report.json')
    if t.upper().startswith('GS') and not os.path.exists(t):
        print(explain(t))
        return 0
    if os.path.isfile(t) and t.endswith(('.yaml', '.yml')):
        stem = os.path.splitext(os.path.basename(t))[0]
        t = os.path.join(os.path.dirname(os.path.abspath(t)), '.glitchsat', *([] if stem == 'glitchsat' else [stem]),
                         'default', 'report.json')
    if not os.path.isfile(t):
        print('error[GS003]: no result at %s\n  = help: run `glitchsat run` first, or give the report.json path' % t, file=sys.stderr)
        return 3
    print(RP.plain(json.load(open(t))))
    return 0


def cmd_templates(a):
    from . import templates as TPL
    if a.name:
        p = os.path.join(TEMPLATES, a.name + '.yaml')
        if not os.path.isfile(p):
            print('error[GS002]: no template %s\n  = help: templates: %s' % (a.name, ', '.join(TPL.NAMES)), file=sys.stderr)
            return 3
        print(open(p).read())
        return 0
    for n in TPL.NAMES:
        print('%-24s %s' % (n, TPL.PLAIN[n]))
    print('\nShow one: glitchsat templates NAME   (a YAML snippet to paste under `checks:`)')
    return 0


def cmd_examples(a):
    items = sorted(d for d in os.listdir(EXAMPLES) if os.path.isdir(os.path.join(EXAMPLES, d)))
    if a.action == 'list' or not a.action:
        for d in items:
            rd = os.path.join(EXAMPLES, d, 'README.md')
            first = ''
            if os.path.isfile(rd):
                first = next((l.strip('# \n') for l in open(rd) if l.strip()), '')
            print('%-18s %s' % (d, first))
        return 0
    if a.action == 'copy':
        if a.name not in items:
            print('error[GS003]: no example %s\n  = help: examples: %s' % (a.name, ', '.join(items)), file=sys.stderr)
            return 3
        dest = a.dest or a.name
        if os.path.exists(dest):
            print('error[GS003]: %s already exists\n  = help: give another folder: glitchsat examples copy %s NEWDIR' % (dest, a.name), file=sys.stderr)
            return 3
        src = os.path.join(EXAMPLES, a.name)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns('.glitchsat', '*.lock', 'expected_*', 'saved'))
        fixed = _fix_outside_paths(src, dest)
        for f in fixed:
            print('  path %s points outside the example; written as %s' % f)
        print('Copied to %s. Next: cd %s && glitchsat run' % (dest, dest))
        return 0
    return 3


def _fix_outside_paths(src, dest):
    """A copied example must still find its files: relative paths in its project files that leave the example folder
    are rewritten as absolute paths (into the installed gallery)."""
    import re
    out = []
    rs = os.path.realpath(src)
    for fn in os.listdir(dest):
        if not fn.endswith(('.yaml', '.yml')):
            continue
        p = os.path.join(dest, fn)
        text = open(p).read()

        def sub(m):
            rel = m.group(2)
            full = os.path.realpath(os.path.join(rs, rel))
            if not (full == rs or full.startswith(rs + os.sep)) and os.path.exists(full):
                out.append((rel, full))
                return m.group(1) + full
            return m.group(0)
        new = re.sub(r'''(^\s*-\s*|[\[,]\s*|:\s*)((?:\.\./)+[^\s,\]'"#]+)''', sub, text, flags=re.M)
        if new != text:
            open(p, 'w').write(new)
    return out


def cmd_flows(a):
    from . import flows as FL
    for k, v in FL.FLOWS.items():
        print('%-12s %s' % (k, v['desc']))
    print('\nLiberty folder for the named libraries: %s (fetch: sh scripts/fetch_libs.sh)' % FL.libs_dir())
    return 0


def cmd_liberty(a):
    from . import liberty as LIB
    try:
        lib = LIB.load(a.file)
    except LIB.LibertyError as e:
        print('error[GS043]: %s' % e, file=sys.stderr)
        return 3
    cells = [a.cell] if a.cell else sorted(lib.cells)
    res = LIB.verify_library(lib, cells)
    ok = sum(1 for v in res.values() if v['ok'])
    bad = [k for k, v in res.items() if v['ok'] is False]
    s = lib.summary()
    print('%s: %d cells; %s' % (s['library'], s['cells'], ', '.join('%s %d' % kv for kv in sorted(s['kinds'].items()))))
    print('truth-table check: %d passed, %d failed, %d not modelled' % (ok, len(bad), len(res) - ok - len(bad)))
    if a.cell:
        print(json.dumps(lib.cells[a.cell].to_json(), indent=1))
        print(res[a.cell])
    for k in bad:
        print('FAILED %s: %s' % (k, res[k]['detail']))
    if a.verbose:
        for k, v in res.items():
            if v['ok'] is None:
                print('not modelled %s: %s' % (k, v['detail']))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='glitchsat', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    from . import __version__
    ap.add_argument('--version', action='version', version='glitchsat (bring your own design) %s' % __version__)
    sp = ap.add_subparsers(dest='cmd', required=True, metavar='COMMAND')
    r = sp.add_parser('run', help='run the analysis of a project')
    r.add_argument('project', nargs='?'); r.add_argument('--task'); r.add_argument('--only', help='comma list: validate,min_faults,attack_surface,merge_lint,survival,unbounded')
    r.add_argument('--json', help='also write the result here'); r.add_argument('--json-only', action='store_true')
    r.add_argument('--redact', action='store_true', help='replace design names by aliases in the reports')
    r.add_argument('--allow-outside', action='store_true', help='allow design sources outside the project folder')
    r.add_argument('--sarif', metavar='FILE', help='also write the plain-words findings as SARIF 2.1.0 (with the how-we-found-it steps as a code flow)')
    r.add_argument('--quick', action='store_true', help='skip the unbounded proof')
    c = sp.add_parser('check', help='validate the project file and the names in it (no analysis)'); c.add_argument('project', nargs='?'); c.add_argument('--task')
    e = sp.add_parser('explain', help='plain summary of a result, or the meaning of an error code'); e.add_argument('what', nargs='?')
    t = sp.add_parser('templates', help='property templates'); t.add_argument('name', nargs='?')
    x = sp.add_parser('examples', help='example gallery'); x.add_argument('action', nargs='?', choices=['list', 'copy'])
    x.add_argument('name', nargs='?'); x.add_argument('dest', nargs='?')
    sp.add_parser('flows', help='synthesis flows')
    sp.add_parser('doctor', help='what is installed and where (Yosys, engines, solvers)')
    lb = sp.add_parser('liberty', help='read and check a Liberty file'); lb.add_argument('file'); lb.add_argument('--cell'); lb.add_argument('-v', '--verbose', action='store_true')
    i = sp.add_parser('init', help='write glitchsat.yaml by answering questions')
    i.add_argument('--from-tinytapeout', metavar='DIR'); i.add_argument('--yes', action='store_true', help='accept every suggestion')
    i.add_argument('--sources', nargs='*'); i.add_argument('--top'); i.add_argument('--out', default='glitchsat.yaml')
    i.add_argument('--template'); i.add_argument('--force', action='store_true')
    s1 = sp.add_parser('import-sby', help='starting glitchsat.yaml from a SymbiYosys .sby file'); s1.add_argument('file'); s1.add_argument('--out', default='glitchsat.yaml')
    s2 = sp.add_parser('import-synfi', help='starting glitchsat.yaml from a SYNFI fault_model.json'); s2.add_argument('file'); s2.add_argument('--out', default='glitchsat.yaml')
    s2.add_argument('--sources', nargs='*', default=[])
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'run': return cmd_run(a)
        if a.cmd == 'check': return cmd_check(a)
        if a.cmd == 'explain': return cmd_explain(a)
        if a.cmd == 'templates': return cmd_templates(a)
        if a.cmd == 'examples': return cmd_examples(a)
        if a.cmd == 'flows': return cmd_flows(a)
        if a.cmd == 'doctor': return cmd_doctor(a)
        if a.cmd == 'liberty': return cmd_liberty(a)
        if a.cmd == 'init':
            from . import init as INIT
            return INIT.main(a)
        if a.cmd in ('import-sby', 'import-synfi'):
            from . import importers as IM
            return IM.main(a)
    except KeyboardInterrupt:
        print('stopped', file=sys.stderr)
        return 2
    except Exception as ex:                      # noqa: BLE001
        from .errors import GSError
        if isinstance(ex, GSError):
            return _err(ex)
        import traceback
        traceback.print_exc()
        print('internal error: %s: %s (please report it with the command you ran)' % (type(ex).__name__, ex), file=sys.stderr)
        return 4
    return 3


if __name__ == '__main__':
    sys.exit(main())
