import json, os, sys
import pytest

TESTS = os.path.dirname(os.path.abspath(__file__))
SCALE = os.path.dirname(TESTS)
EXT = os.path.dirname(SCALE)
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(EXT, '..'))
if not os.path.isfile(os.path.join(ROOT, 'scripts', 'glitchsat.py')):
    for cand in (os.path.normpath(os.path.join(EXT, '..', 'work', 'glitchsat')),):   # development work tree
        if os.path.isfile(os.path.join(cand, 'scripts', 'glitchsat.py')): ROOT = cand
os.environ['GLITCHSAT_ROOT'] = ROOT
FASTSAT = os.environ.get('GLITCHSAT_FASTSAT') or os.path.join(EXT, 'fastsat', 'scripts')
os.environ['GLITCHSAT_FASTSAT'] = FASTSAT
for p in (os.path.join(SCALE, 'scripts'), TESTS, os.path.join(os.path.dirname(FASTSAT), 'bench'), os.path.join(os.path.dirname(FASTSAT), 'tests')):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope='session')
def root():
    if not os.path.isfile(os.path.join(ROOT, 'scripts', 'glitchsat.py')):
        pytest.skip('repository root not found; set GLITCHSAT_ROOT')
    return ROOT


@pytest.fixture(scope='session')
def fs(root):
    import gscale
    return gscale.fastsat()


@pytest.fixture(scope='session')
def proxies(tmp_path_factory, fs):
    """S-box proxy netlists of ext/fastsat (mux trees and shared muxes): name -> (path, top, params)."""
    import gen_sbox_proxy as g
    d = tmp_path_factory.mktemp('proxy'); box = g.aes_sbox(); out = {}
    for shared in (False, True):
        for kind in g.PARAMS:
            b = g.build(kind, box, shared)
            p = d / (b.top + '.json'); p.write_text(json.dumps(b.doc()))
            out[kind + ('s' if shared else '')] = (str(p), b.top, g.PARAMS[kind])
    return out


@pytest.fixture(scope='session')
def proxy_problem(proxies, fs):
    from gscale import circuit

    def make(name):
        path, top, pr = proxies[name]
        nl = fs.gs.Netlist(path, top)
        return circuit.engine_problem(nl, pr['cycles'], pr['goal_out'], pr['goal_value'], 'sig', pr['key'])
    return make
