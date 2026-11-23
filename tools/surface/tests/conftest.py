import os, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), 'scripts')
if 'GLITCHSAT_ROOT' not in os.environ:
    cand = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
    if os.path.isfile(os.path.join(cand, 'scripts', 'glitchsat.py')):
        os.environ['GLITCHSAT_ROOT'] = cand
sys.path.insert(0, SCRIPTS)
ROOT = os.environ.get('GLITCHSAT_ROOT', '')


def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: long exhaustive runs (about a minute); run with GLITCHSAT_SLOW=1')


def pytest_collection_modifyitems(config, items):
    if os.environ.get('GLITCHSAT_SLOW') == '1':
        return
    skip = pytest.mark.skip(reason='slow; set GLITCHSAT_SLOW=1')
    for it in items:
        if 'slow' in it.keywords:
            it.add_marker(skip)


@pytest.fixture
def path():
    if not os.path.isfile(os.path.join(ROOT, 'scripts', 'glitchsat.py')):
        pytest.skip('repository root not found: set GLITCHSAT_ROOT')
    return lambda rel: os.path.join(ROOT, rel)
