"""Build step for `pip install .` at the repository root (metadata: pyproject.toml).

Besides the command-line package (product/src/faultbound_wt) the wheel carries the data package `glitchsat_data`:
a copy of the parts of this repository that GlitchSAT Studio and the module tools read at run time, in the same
folder layout as the repository (scripts/glitchsat.py, rtl/, reference/, results/, tools/<module>/, ...). The
Studio, `glitchsat-studio` and the own-design commands find it with importlib.resources when they do not run inside
a clone, so an installed GlitchSAT does not depend on the current folder.

The list below is the single place that says what is copied. Nothing is downloaded; the build works offline.
"""
import fnmatch
import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = os.path.dirname(os.path.abspath(__file__))

# folders and files of the repository copied into glitchsat_data (relative to the repository root)
DATA = [
    'scripts', 'rtl', 'reference', 'results', 'validation', 'ci', 'formal', 'tb', 'integrations', 'real_designs',
    'templates', 'tools',
    'docs/explainers', 'docs/report', 'docs/edu', 'docs/GLOSSARY.md', 'docs/NUMBERS.md', 'docs/EVIDENCE_LABELS.md',
    'research/README.md', 'research/c2/b2_scope', 'research/c2/e2_variance', 'research/c3/m1', 'research/c3/rep',
    'research/c6/p01',
    'Makefile', 'README.md', 'START.md', 'LICENSE', 'NOTICE.md', 'THIRD_PARTY.md',
]
# never copied (build output, caches, screenshots the test suites write, local project state)
SKIP = ['__pycache__', '*.pyc', '.pytest_cache', '.glitchsat', 'shots*', '*.egg-info', '.ruff_cache', '*_pre_*']
# local build and download folders of single modules (ignored by git; can be large)
SKIP_PATHS = {'tools/soc/work', 'tools/scale/bench/work', 'tools/masking/work', 'tools/real/opentitan_prims/work',
              'tools/real/opentitan_prims/labs/work', 'tools/real/opentitan_prims/src_clone', 'tools/bootloader/work',
              'tools/bootloader/third_party', 'tools/bootloader/to_report', 'tools/firmware/build'}


def _ignore(d, names):
    rel = os.path.relpath(d, HERE).replace(os.sep, '/')
    return {n for n in names
            if any(fnmatch.fnmatch(n, p) for p in SKIP) or (rel + '/' + n) in SKIP_PATHS}


def copy_data(dest):
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, '__init__.py'), 'w') as f:
        f.write('"""GlitchSAT project data (engine scripts, designs, recorded results, tools/<module>/), installed with\n'
                'the glitchsat package. Read by GlitchSAT Studio and the glitchsat command; nothing to import."""\n')
    with open(os.path.join(dest, '.glitchsat-project'), 'w') as f:
        f.write('GlitchSAT project data installed with the glitchsat package\n')
    for rel in DATA:
        src = os.path.join(HERE, rel)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dest, rel)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)


class BuildWithData(build_py):
    def run(self):
        super().run()
        if not self.editable_mode:
            copy_data(os.path.join(self.build_lib, 'glitchsat_data'))


setup(cmdclass={'build_py': BuildWithData})
