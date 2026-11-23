"""This test folder is an overlay on the repository's product/ package. Run alone (without the package importable),
it explains how to run it instead of failing on import: `python3 run_tests.py` in the overlay folder builds the tree."""
import importlib.util

import pytest


def pytest_ignore_collect(collection_path, config):
    if importlib.util.find_spec('faultbound_wt') is None and collection_path.name.startswith('test_'):
        return True
    return None


def pytest_collection_modifyitems(session, config, items):
    if importlib.util.find_spec('faultbound_wt') is None and not items:
        items.append(pytest.Function.from_parent(session, name='package_missing', callobj=_missing))   # pragma: no cover


def _missing():
    pytest.skip('the repository package faultbound_wt is not importable: run `python3 run_tests.py` in the overlay folder')
