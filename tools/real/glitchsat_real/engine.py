"""Access to the GlitchSAT engine (read-only repository) and the ext/ modules, without modifying either.

GLITCHSAT_ROOT (default: the repository found above this folder) holds scripts/glitchsat.py; GLITCHSAT_EXT (default:
the ext/ folder next to real/) holds fastsat/, surface/, unbounded/, harden/."""
import json
import os
import sys
import tempfile

def _find_repo(start):
    """The GlitchSAT repository: $GLITCHSAT_ROOT, else the first folder above `start` that holds scripts/glitchsat.py
    (directly, or as work/glitchsat/ in a development work tree). Never a fixed machine path."""
    if os.environ.get('GLITCHSAT_ROOT'):
        return os.environ['GLITCHSAT_ROOT']
    d = os.path.abspath(start)
    while True:
        for c in (d, os.path.join(d, 'work', 'glitchsat')):
            if os.path.isfile(os.path.join(c, 'scripts', 'glitchsat.py')):
                return c
        up = os.path.dirname(d)
        if up == d:
            return os.path.join(os.path.dirname(os.path.abspath(start)), 'glitchsat')
        d = up


_REAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = _find_repo(_REAL)
EXT = os.environ.get('GLITCHSAT_EXT') or (lambda _d: _d if os.path.isdir(os.path.join(_d, 'fastsat')) else os.path.join(_d, 'ext'))(os.path.dirname(_REAL))
os.environ.setdefault('GLITCHSAT_ROOT', ROOT)
for p in (os.path.join(ROOT, 'scripts'), os.path.join(EXT, 'fastsat', 'scripts'), os.path.join(EXT, 'surface', 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

import glitchsat as gs          # noqa: E402  (z3 is imported lazily inside the engine)


def fastsat():
    import glitchsat_sat
    return glitchsat_sat


def netlist_from_doc(doc, top):
    """glitchsat.Netlist from an in-memory Yosys JSON document (the engine's parser reads a file)."""
    fd, path = tempfile.mkstemp(suffix='.json')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(doc, f)
        return gs.Netlist(path, top)
    finally:
        os.unlink(path)
