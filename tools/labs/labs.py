"""GlitchSAT Labs command line (own code, Apache-2.0).

  python3 tools/labs/labs.py list              every Labs module: status, last run, findings per label
  python3 tools/labs/labs.py run <module>      run the module's example, write its labs-result/1 file, print findings
  python3 tools/labs/labs.py show <module>     print the findings of the last run (no new run)

Planned wiring: the `glitchsat` launcher gets a `labs` sub-command that calls main() here, so that
`glitchsat labs list` and `glitchsat labs run masking` work (see tools/labs/README.md, "Command line").

Labs modules are EXPERIMENTAL: try them, do not rely on them.
"""
import json
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import labs_result as LR  # noqa: E402

EXT = os.environ.get('GLITCHSAT_EXT', os.path.dirname(HERE))


def _first(*cands):
    """The first folder that exists (else the first candidate): modules sit side by side as tools/<module> in the
    repository and as ext/<module> (real/ beside ext/) in the development tree."""
    for c in cands:
        if c and os.path.isdir(c):
            return c
    return cands[0]


REAL = os.environ.get('GLITCHSAT_REAL') or _first(os.path.join(EXT, 'real'), os.path.join(os.path.dirname(EXT), 'real'))
def _by_hash(base, h):
    """The sub-folder of base whose name has this hash (sha256 of the lower-case name, first 16 hex digits): the
    development folder of the bootloader study is named after the bootloader, which public files do not name."""
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return None
    for n in names:
        if hashlib.sha256(n.lower().encode()).hexdigest()[:16] == h and os.path.isdir(os.path.join(base, n)):
            return os.path.join(base, n)
    return None


BOOT = _first(os.path.join(EXT, 'bootloader'), _by_hash(EXT, '2c5b41081632e17c'))

# id -> where the module lives. Paths are absolute at run time; README paths are relative to the module folder.
MODULES = {
    'masking': dict(title='Side-channel masking survival', status='EXPERIMENTAL', folder=os.path.join(EXT, 'masking'),
                    runner='scripts/run_labs.py', result='results/labs_result.json',
                    question='Does a masked circuit still hide its secret from someone who measures one wire, with and '
                             'without glitches, and does that stay true after synthesis?'),
    'bootloader': dict(title='Bootloader fault hardening', status='EXPERIMENTAL', folder=BOOT,
                    runner='scripts/run_labs.py', result='results/labs_result.json', withheld=True,
                    question="Experimental analysis of a real bootloader's fault hardening; details withheld pending "
                             'responsible disclosure.'),
    'opentitan_prims': dict(title='OpenTitan hardening primitives', status='EXPERIMENTAL',
                            folder=os.path.join(REAL, 'opentitan_prims'), runner='labs/run_labs.py',
                            result='labs/results/labs_result.json',
                            question="Do OpenTitan's built-in fault countermeasures still need several bit flips to break "
                                     'after open-source synthesis, and are the redundant parts still there?'),
    'consttime': dict(title='Constant-time firmware checks', status='PLANNED', folder=os.path.join(EXT, 'consttime'),
                      question='Does the time a firmware routine takes (or the memory it touches) depend on a secret, '
                               'after the compiler has optimised it?'),
    'secretflow': dict(title='Secret-flow checks', status='PLANNED', folder=os.path.join(EXT, 'secretflow'),
                       question='Can a secret (a key) reach an output the attacker can see, for example a debug port, '
                                'under the rule "src =/=> dst when ... unless ..." of the project file?'),
}


def _shown(p):
    """A path as shown in a printed command: relative to the current folder when below it, else the file name."""
    p = os.path.abspath(p)
    try:
        r = os.path.relpath(p)
    except ValueError:
        return os.path.basename(p)
    return r if not r.startswith('..') else os.path.basename(p)


def result(mid):
    m = MODULES[mid]
    if 'result' not in m:
        return None
    p = os.path.join(m['folder'], m['result'])
    if not os.path.exists(p):
        return None
    try:
        d = json.load(open(p))
    except ValueError:
        return None
    return d if not LR.validate(d) else None


def summary(mid):
    """Plain dict for the list command and the Studio Labs tab."""
    m = MODULES[mid]
    d = result(mid)
    counts = {}
    for f in (d or {}).get('findings', []):
        counts[f['label']] = counts.get(f['label'], 0) + 1
    return dict(id=mid, title=m['title'], status=m['status'], question=m['question'],
                readme=os.path.join(m['folder'], m.get('readme', 'README.md')) if m['status'] != 'PLANNED'
                else os.path.join(HERE, 'README.md'),
                last_run=(d or {}).get('run', {}).get('started'), ok=(d or {}).get('run', {}).get('ok'),
                counts=counts, findings=(d or {}).get('findings', []), caveats=(d or {}).get('caveats', []),
                withheld=bool(m.get('withheld')), run_cmd='python3 %s run %s' % (_shown(__file__), mid),
                example=(d or {}).get('example'))


def cmd_list():
    print('GlitchSAT Labs - experiments in progress: try them, do not rely on them.\n')
    print('%-16s %-13s %-26s %s' % ('module', 'status', 'last run', 'findings'))
    for mid in MODULES:
        s = summary(mid)
        c = ', '.join('%d %s' % (v, k) for k, v in sorted(s['counts'].items())) or '-'
        print('%-16s %-13s %-26s %s' % (mid, s['status'], s['last_run'] or ('no code yet' if s['status'] == 'PLANNED' else 'never'), c))
    return 0


def cmd_show(mid):
    s = summary(mid)
    print('%s [%s]\n%s\n' % (s['title'], s['status'], s['question']))
    if s['status'] == 'PLANNED':
        print('Planned: no code yet. See %s' % s['readme'])
        return 0
    if not s['findings']:
        print('No result yet: run  labs.py run %s' % mid)
        return 2
    for f in s['findings']:
        print(' [EXPERIMENTAL, %s] %s' % (f['label'], f['text']))
    print('\nLimits:')
    for c in s['caveats']:
        print(' - ' + c)
    print('\nMore: %s' % s['readme'])
    return 0


def cmd_run(mid):
    m = MODULES[mid]
    if m['status'] == 'PLANNED':
        print('%s is planned; there is no code to run yet.' % mid)
        return 2
    runner = os.path.join(m['folder'], m['runner'])
    try:
        r = subprocess.run([sys.executable, runner], timeout=570)
    except subprocess.TimeoutExpired:
        print('%s: stopped after 570 s (no result written)' % mid)
        return 3
    print()
    cmd_show(mid)
    return r.returncode


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ('-h', '--help') or a[0] not in ('list', 'run', 'show'):
        print(__doc__)
        return 0 if a and a[0] in ('-h', '--help') else 1
    if a[0] == 'list':
        return cmd_list()
    if len(a) < 2 or a[1] not in MODULES:
        print('module must be one of: %s' % ', '.join(MODULES))
        return 1
    return cmd_run(a[1]) if a[0] == 'run' else cmd_show(a[1])


if __name__ == '__main__':
    sys.exit(main())
