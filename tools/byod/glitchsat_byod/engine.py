"""Where the reused engines are. This module needs, besides Python, PyYAML and Yosys:

  engine       what it is used for                                  looked up as (first match wins)
  repository   scripts/glitchsat.py (netlist reader the engines share)  <repo>, then $GLITCHSAT_ROOT
  scale        minimum faults, attack lists, replay (gscale)          $GLITCHSAT_SCALE, <repo>/tools/scale, $GLITCHSAT_ROOT/tools/scale, ../scale
  fastsat      the built-in SAT encoding used by scale                $GLITCHSAT_FASTSAT, <repo>/tools/fastsat, ...
  unbounded    the proof for any number of cycles (k-induction, IC3)  $GLITCHSAT_UNBOUNDED, <repo>/tools/unbounded, ...
  checker      the merge lint (are redundant copies still separate?)  $GLITCHSAT_CHECKER, <repo>/tools/checker, ...

<repo> is the repository this folder sits in when it is landed as tools/byod (the first parent folder that holds
scripts/glitchsat.py). `../<name>` (a sibling folder) is the layout of a development work tree. When something is
missing, the error (GS021) lists every folder that was looked in; `glitchsat doctor` prints the whole set-up.
"""
import os
import sys

from .errors import GSError

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                     # .../byod (lands as tools/byod)

ENGINES = {   # name -> (file that must exist inside, environment variable)
    'scale': (os.path.join('scripts', 'gscale', '__init__.py'), 'GLITCHSAT_SCALE'),
    'fastsat': (os.path.join('scripts', 'glitchsat_sat.py'), 'GLITCHSAT_FASTSAT_DIR'),
    'unbounded': (os.path.join('src', 'ic3.py'), 'GLITCHSAT_UNBOUNDED'),
    'checker': (os.path.join('survival', 'cli.py'), 'GLITCHSAT_CHECKER'),
}


class EngineMissing(GSError, ImportError):
    """A GSError (so the command line prints a normal GS021 message) that old callers can still catch as ImportError."""


def _has(c, rel):
    return bool(c) and os.path.exists(os.path.join(c, rel))


def _repo_from_layout():
    d = PKG
    for _ in range(4):
        d = os.path.dirname(d)
        if _has(d, os.path.join('scripts', 'glitchsat.py')):
            return d
    return None


def repo_candidates():
    return [c for c in (_repo_from_layout(), os.environ.get('GLITCHSAT_ROOT')) if c]


def repo_root():
    for c in repo_candidates():
        if _has(c, os.path.join('scripts', 'glitchsat.py')):
            return os.path.abspath(c)
    return None


def need_repo():
    r = repo_root()
    if r is None:
        looked = [os.path.dirname(os.path.dirname(PKG)), os.environ.get('GLITCHSAT_ROOT') or '($GLITCHSAT_ROOT not set)']
        raise EngineMissing('GS021', 'the GlitchSAT repository (scripts/glitchsat.py) was not found',
                            note='looked in: ' + ', '.join(looked),
                            help='keep this folder at tools/byod inside the GlitchSAT repository, or set '
                                 'GLITCHSAT_ROOT=/path/to/the/repository; `glitchsat doctor` shows the whole set-up')
    return r


def tool_candidates(name):
    rel, env = ENGINES[name]
    root = _repo_from_layout()
    return [c for c in (os.environ.get(env),
                        os.path.join(root, 'tools', name) if root else None,
                        os.path.join(os.environ['GLITCHSAT_ROOT'], 'tools', name) if os.environ.get('GLITCHSAT_ROOT') else None,
                        os.path.join(os.path.dirname(PKG), name)) if c]


def tool_dir(name, rel=None, env=None):
    rel = rel or ENGINES[name][0]
    cands = tool_candidates(name)
    for c in cands:
        if _has(c, rel):
            return os.path.abspath(c)
    raise EngineMissing('GS021', 'the GlitchSAT engine `%s` was not found' % name,
                        note='looked for %s in: %s' % (rel, ', '.join(cands)),
                        help='land it with this folder as tools/%s in the repository (see README, "Landing"), or set %s'
                             % (name, ENGINES[name][1]))


_G = {}


def gscale():
    """The scaling engine package (tools/scale/scripts/gscale): Circuit, Problem, search, sim."""
    if 'g' not in _G:
        root = need_repo()
        os.environ['GLITCHSAT_ROOT'] = root          # read by fastsat and unbounded
        fs = tool_dir('fastsat')
        os.environ.setdefault('GLITCHSAT_FASTSAT', os.path.join(fs, 'scripts'))
        d = tool_dir('scale')
        p = os.path.join(d, 'scripts')
        if p not in sys.path:
            sys.path.insert(0, p)
        import gscale as g
        from gscale import circuit, search, sim, unroll, cnf, sat  # noqa: F401
        g.fastsat()
        _G['g'] = g
    return _G['g']


def unbounded_src():
    d = tool_dir('unbounded')
    p = os.path.join(d, 'src')
    if p not in sys.path:
        sys.path.insert(0, p)
    return p


def checker_dir():
    return tool_dir('checker')


def doctor():
    """Every requirement with where it was found (or what to do). Returns (lines, ok)."""
    import shutil
    L, ok = [], True
    L.append('Python %s' % sys.version.split()[0])
    try:
        import yaml  # noqa: F401
        L.append('PyYAML: yes')
    except ImportError:
        L.append('PyYAML: MISSING (pip install pyyaml)'); ok = False
    from . import flows as FL
    try:
        y = FL.find_yosys()
        L.append('Yosys: %s (%s)' % (y.short(), y.path))
    except GSError as e:
        L.append('Yosys: MISSING. Every input path (Verilog, SystemVerilog, gate-level netlist, Yosys JSON) needs it. %s' % e.help)
        ok = False
    try:
        y = FL.find_yosys(need_slang=True)
        L.append('Yosys with read_slang (SystemVerilog): %s (%s)' % (y.short(), y.path))
    except GSError:
        L.append('Yosys with read_slang (SystemVerilog): not found (only needed for .sv sources; Yosys 0.67 or newer)')
    r = repo_root()
    L.append('repository (scripts/glitchsat.py): %s' % (r or 'MISSING; looked in %s' % ', '.join(repo_candidates() or ['(no candidate)'])))
    ok = ok and bool(r)
    for n in ENGINES:
        try:
            L.append('engine %-11s %s' % (n + ':', tool_dir(n)))
        except GSError:
            L.append('engine %-11s MISSING; looked in %s' % (n + ':', ', '.join(tool_candidates(n))))
            ok = ok and n in ('unbounded', 'checker')
    L.append('solvers: cadical %s, kissat %s, z3 %s' % (shutil.which('cadical') or 'no', shutil.which('kissat') or 'no',
                                                        'yes' if _has_z3() else 'no'))
    L.append('Liberty folder: %s%s' % (FL.libs_dir(), '' if os.path.isdir(FL.libs_dir()) else ' (not fetched: sh scripts/fetch_libs.sh)'))
    return L, ok


def _has_z3():
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False
