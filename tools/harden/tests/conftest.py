import os, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
sys.path.insert(0, TOP)
sys.dont_write_bytecode = True          # never write into the read-only repository when importing from it
if 'GLITCHSAT_ROOT' not in os.environ:
    for cand in (os.path.join(TOP, '..', '..', 'work', 'glitchsat'), os.path.join(TOP, '..', '..')):
        if os.path.isfile(os.path.join(cand, 'scripts', 'glitchsat.py')):
            os.environ['GLITCHSAT_ROOT'] = os.path.abspath(cand)
            break
ROOT = os.environ.get('GLITCHSAT_ROOT', '')
SURFACE = os.environ.get('GLITCHSAT_SURFACE') or os.path.abspath(os.path.join(TOP, '..', 'surface', 'scripts'))


def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: long exhaustive runs; run with GLITCHSAT_SLOW=1')


def pytest_collection_modifyitems(config, items):
    if os.environ.get('GLITCHSAT_SLOW') == '1':
        return
    skip = pytest.mark.skip(reason='slow; set GLITCHSAT_SLOW=1')
    for it in items:
        if 'slow' in it.keywords:
            it.add_marker(skip)


@pytest.fixture
def repo():
    if not os.path.isfile(os.path.join(ROOT, 'scripts', 'glitchsat.py')):
        pytest.skip('repository root not found: set GLITCHSAT_ROOT')
    return lambda rel: os.path.join(ROOT, rel)


@pytest.fixture
def surface():
    if not os.path.isfile(os.path.join(SURFACE, 'attack_surface.py')):
        pytest.skip('ext/surface not found: set GLITCHSAT_SURFACE=<dir with attack_surface.py>')
    if SURFACE not in sys.path:
        sys.path.insert(0, SURFACE)
    return SURFACE
