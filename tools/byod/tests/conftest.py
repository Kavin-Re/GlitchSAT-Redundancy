import os
import shutil
import sys
import textwrap

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)

from glitchsat_byod.flows import libs_dir, KNOWN_LIBS   # noqa: E402

DESIGNS = os.path.join(HERE, 'designs')
EXAMPLES = os.path.join(PKG, 'examples')


def have_yosys():
    return bool(shutil.which('yosys'))


def have_lib(name):
    return os.path.isfile(os.path.join(libs_dir(), KNOWN_LIBS[name]))


needs_yosys = pytest.mark.skipif(not have_yosys(), reason='Yosys not installed')


def copy_example(name, dest):
    """Copy a gallery example to dest (without its work folder, saved runs and lock files) and return the copy's folder.
    Tests always run examples from a copy, so running the tests never changes the files of the gallery."""
    out = os.path.join(str(dest), name)
    shutil.copytree(os.path.join(EXAMPLES, name), out, ignore=shutil.ignore_patterns('.glitchsat', 'saved', '*.lock'))
    return out


@pytest.fixture
def example(tmp_path):
    """example(name) -> folder of a fresh temp copy of a gallery example."""
    return lambda name: copy_example(name, tmp_path)


@pytest.fixture
def project(tmp_path):
    """project(yaml_text, files={name: text}, copy=[design files]) -> path of glitchsat.yaml in a temp folder."""
    def make(text, files=None, copy=()):
        for f in copy:
            shutil.copy(os.path.join(DESIGNS, f), tmp_path / f)
        for n, t in (files or {}).items():
            (tmp_path / n).write_text(textwrap.dedent(t))
        p = tmp_path / 'glitchsat.yaml'
        p.write_text(textwrap.dedent(text))
        return str(p)
    return make
