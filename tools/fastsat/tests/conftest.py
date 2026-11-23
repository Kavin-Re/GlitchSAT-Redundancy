import os, sys
import pytest

TESTS = os.path.dirname(os.path.abspath(__file__))
FASTSAT = os.path.dirname(TESTS)
ROOT = os.environ.get('GLITCHSAT_ROOT') or os.path.normpath(os.path.join(FASTSAT, '..', '..'))
os.environ['GLITCHSAT_ROOT'] = ROOT
for p in (os.path.join(FASTSAT, 'scripts'), os.path.join(FASTSAT, 'bench'), TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope='session')
def root():
    if not os.path.isfile(os.path.join(ROOT, 'scripts', 'glitchsat.py')):
        pytest.skip('repository root not found; set GLITCHSAT_ROOT')
    return ROOT


@pytest.fixture(scope='session')
def proxies(tmp_path_factory):
    """S-box proxy netlists (bench/gen_sbox_proxy.py), generated once per test session."""
    import gen_sbox_proxy as g
    d = tmp_path_factory.mktemp('proxy')
    box = g.aes_sbox()
    out = {}
    import json
    for shared in (False, True):
        for kind in g.PARAMS:
            b = g.build(kind, box, shared)
            p = d / f'{b.top}.json'
            p.write_text(json.dumps(b.doc()))
            out[kind + ('s' if shared else '')] = (str(p), b.top, g.PARAMS[kind])
    return out
