import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'src'))
sys.path.insert(0, HERE)
import sat

ROOT = sat.find_repo_root()


def pytest_collection_modifyitems(config, items):
    import pytest
    if ROOT is None:
        skip = pytest.mark.skip(reason='repository root not found (scripts/glitchsat.py); set GLITCHSAT_ROOT')
        for it in items:
            it.add_marker(skip)
        return
    try:
        sat.load_minicdcl()
    except sat.BackendError as e:
        # Hard dependency: ext/unbounded is not usable (and its stored results cannot be reproduced) without
        # ext/fastsat. Fail loudly instead of skipping, unless explicitly allowed.
        if os.environ.get('GLITCHSAT_ALLOW_NO_FASTSAT') != '1':
            pytest.exit('ext/unbounded requires ext/fastsat: ' + str(e) +
                        ' (set GLITCHSAT_ALLOW_NO_FASTSAT=1 to skip the SAT tests instead)', returncode=3)
        skip = pytest.mark.skip(reason=str(e))
        for it in items:
            if 'needs_sat' in it.keywords:
                it.add_marker(skip)


def pytest_configure(config):
    config.addinivalue_line('markers', 'needs_sat: needs the pure Python SAT solver (ext/fastsat/scripts/minicdcl.py)')
