"""gscale: scaling layer for the GlitchSAT bounded fault-injection check (see ../../README.md)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
__version__ = '0.1.0'


def _find(rel, env, tries):
    cands = []
    if os.environ.get(env):
        cands.append(os.environ[env])
    cands += tries
    for c in cands:
        if os.path.isfile(os.path.join(c, rel)):
            return os.path.normpath(c)
    raise ImportError('%s not found (set %s; tried %s)' % (rel, env, ', '.join(cands)))


def fastsat():
    """The direct-CNF backend module (ext/fastsat/scripts/glitchsat_sat.py): Encoding, totalizer, solver backends.
    Located through $GLITCHSAT_FASTSAT or next to this folder (<repo>/ext/fastsat/scripts)."""
    d = _find('glitchsat_sat.py', 'GLITCHSAT_FASTSAT',
              [os.path.join(HERE, '..', '..', '..', 'fastsat', 'scripts')])
    if d not in sys.path:
        sys.path.insert(0, d)
    import glitchsat_sat
    return glitchsat_sat
