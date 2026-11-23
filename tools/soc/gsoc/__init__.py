"""gsoc: GlitchSAT on whole chips (see ../README.md).

Reuses, without changing them: ext/scale (gscale: Circuit, Problem, unrolling, site reduction, module summaries,
interval search), ext/fastsat (CNF, solver backends), ext/checker (countermeasure detection), ext/surface (merge
lint) and scripts/glitchsat.py of the repository.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOC = os.path.normpath(os.path.join(HERE, '..'))
EXT = os.path.normpath(os.path.join(SOC, '..'))
__version__ = '0.1.0'


def _first(cands, probe):
    for c in cands:
        if c and os.path.exists(os.path.join(c, probe)):
            return os.path.normpath(c)
    return None


def setup_paths():
    """Make gscale, the fastsat backend and the repository engine importable. Environment variables win:
    GLITCHSAT_ROOT (repository root), GLITCHSAT_SCALE (ext/scale), GLITCHSAT_FASTSAT (ext/fastsat/scripts)."""
    root = _first([os.environ.get('GLITCHSAT_ROOT'), os.path.join(EXT, '..'),
                   os.path.join(EXT, '..', 'work', 'glitchsat')], os.path.join('scripts', 'glitchsat.py'))
    if root is None:
        raise ImportError('scripts/glitchsat.py not found: set GLITCHSAT_ROOT to the repository root')
    os.environ['GLITCHSAT_ROOT'] = root
    scale = _first([os.environ.get('GLITCHSAT_SCALE'), os.path.join(EXT, 'scale')],
                   os.path.join('scripts', 'gscale', '__init__.py'))
    if scale is None:
        raise ImportError('ext/scale not found: set GLITCHSAT_SCALE')
    fast = _first([os.environ.get('GLITCHSAT_FASTSAT'), os.path.join(EXT, 'fastsat', 'scripts')], 'glitchsat_sat.py')
    if fast:
        os.environ.setdefault('GLITCHSAT_FASTSAT', fast)
    p = os.path.join(scale, 'scripts')
    if p not in sys.path:
        sys.path.insert(0, p)
    return root


def gscale():
    setup_paths()
    import gscale as g
    import gscale.circuit, gscale.search, gscale.sim, gscale.unroll, gscale.modular, gscale.spec  # noqa: F401
    return g
