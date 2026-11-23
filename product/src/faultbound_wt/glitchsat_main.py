"""`glitchsat`: one command for every GlitchSAT tool.

  glitchsat run | init | check | explain | doctor | templates | examples | flows | liberty | import-sby | import-synfi
        your own design: the project file glitchsat.yaml (the own-design tool, glitchsat_byod)
  glitchsat studio [--port N] [--no-browser]
        GlitchSAT Studio, the local app (same as glitchsat-studio)
  glitchsat analyze | example-path | margin | evidence | sarif | validate-sarif | evidence-example
        the netlist engine and the evidence tools
  glitchsat check --targets glitchsat.toml   (also: glitchsat check-targets ...)
        the CI check over a targets file

`check` has one meaning per form, never a guess: with `--targets` it is the CI check over a targets file (as in the
GitHub Action and the pre-commit hook); without it, it validates a project file (glitchsat.yaml) and the names in it.
"""
import os
import sys

OWN = ('run', 'init', 'check', 'explain', 'doctor', 'templates', 'examples', 'flows', 'liberty', 'import-sby',
       'import-synfi')
TARGETS_CHECK = 'check-targets'


def _is_targets_check(args):
    return any(a == '--targets' or a.startswith('--targets=') for a in args)


def _data_root():
    """The project data installed with the package (glitchsat_data, from `pip install .` at the repository root)."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(here, 'glitchsat_data')
    if os.path.isfile(os.path.join(d, 'scripts', 'glitchsat.py')):
        return d
    try:
        from importlib import resources
        p = resources.files('glitchsat_data')
        if p.joinpath('scripts', 'glitchsat.py').is_file():
            return str(p)
    except Exception:   # noqa: BLE001  (not installed)
        pass
    return None


def _own_design_main():
    """The own-design tool's main(): installed as a package, tools/byod of a repository checkout, or the copy in
    the installed project data (glitchsat_data)."""
    try:
        from glitchsat_byod.cli import main
        return main
    except ImportError:
        pass
    cands = []
    if os.environ.get('GLITCHSAT_ROOT'):
        cands.append(os.path.join(os.environ['GLITCHSAT_ROOT'], 'tools', 'byod'))
    d = os.path.abspath(os.getcwd())
    while True:
        cands.append(os.path.join(d, 'tools', 'byod'))
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    data = _data_root()
    if data:
        cands.append(os.path.join(data, 'tools', 'byod'))
    for c in cands:
        if os.path.isfile(os.path.join(c, 'glitchsat_byod', 'cli.py')):
            if data and c.startswith(data) and not os.environ.get('GLITCHSAT_ROOT'):
                os.environ['GLITCHSAT_ROOT'] = data     # the engines it uses are in the same installed copy
            sys.path.insert(0, c)
            from glitchsat_byod.cli import main
            return main
    return None


def usage():
    return __doc__.strip()


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ('-h', '--help', 'help'):
        print(usage())
        return 0 if args else 3
    cmd, rest = args[0], args[1:]
    if cmd in ('--version', '-V'):
        from . import __version__
        print('glitchsat %s' % __version__)
        return 0
    if cmd == 'studio':
        from . import studio_launcher
        return studio_launcher.main(rest)
    if cmd == TARGETS_CHECK or (cmd == 'check' and _is_targets_check(rest)):
        from . import cli
        return cli.main(['check'] + rest)
    if cmd in OWN:
        m = _own_design_main()
        if m is None:
            print('glitchsat %s: the own-design tool (glitchsat_byod) is not installed here; install GlitchSAT with it, '
                  'or run inside a repository checkout (tools/byod).' % cmd, file=sys.stderr)
            return 3
        return m([cmd] + rest)
    from . import cli
    return cli.main(args)


if __name__ == '__main__':
    sys.exit(main())
