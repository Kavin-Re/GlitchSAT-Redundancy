# Getting GlitchSAT into tool bundles

Status: notes for a maintainer. Nothing here has been submitted to either project. The descriptions of the two
projects come from reading their repositories on 2026-11-21 (OSS CAD Suite build repository at commit
`59e81b5`, 2026-11-17; IIC-OSIC-TOOLS at commit `f15ef6a`, 2026-11-12). Check them again before opening a request:
both projects change often.

## What a bundle has to provide

| need | why | notes |
|---|---|---|
| Python 3.11 or newer | `tomllib`, the package's `requires-python` | both bundles ship a new enough Python (below) |
| `z3-solver` Python bindings | `glitchsat analyze` (the solver) | the evidence commands (`margin`, `evidence`, `sarif`, `check` on recorded results, `validate-sarif`) need no z3 |
| Yosys on PATH | only for Verilog (`.v`) input and `--synth-sweep` | Yosys JSON netlists need no Yosys |
| `jsonschema` (optional) | `glitchsat validate-sarif` checks the schema; without it only the GitHub rules run | extra `sarif` |

Commands installed: `glitchsat`, `glitchsat-evidence`, `glitchsat-hook`, `glitchsat-evidence-hook`,
`glitchsat-studio` (plus the older aliases `faultbound-wt`, `faultbound-wt-hook`). A smoke test that needs no solver
and no network:

```
glitchsat --version
glitchsat evidence-example /tmp/gs-ex && glitchsat validate-sarif /tmp/gs-ex/glitchsat.sarif
```

A smoke test of the solver (needs z3, about 1 to 10 s):

```
EX="$(glitchsat example-path)"
glitchsat analyze "$EX/v2.json" --config "$EX/threat.toml" --max-flips 3 --exit-zero
```

### The z3 pin

The package has no hard z3 dependency. The solver is the optional extra `solver` = `z3-solver>=5.4.1,<6`
(`pip install "glitchsat[solver]"`); the range stays inside the tested major version 5 and does not cross the
untested 4 -> 5 change. The exact version of the recorded results, `z3-solver==5.4.1.0`, is pinned only in the
reproducibility lock file `ci/requirements-ci.txt`, which every cloud reproduction script installs from, and the
actual z3 version is recorded in the provenance block of every report. A bundle that ships other Python tools can
therefore co-install another 5.x z3, or ship GlitchSAT in its own virtual environment, the way IIC-OSIC-TOOLS does
for a few tools (below).

Wheels of `z3-solver` 5.4.1.0 on PyPI: Windows (3), manylinux_2_27 x86_64, **manylinux_2_38** aarch64 and riscv64,
macOS 13 x86_64 and arm64. On aarch64 with glibc older than 2.38 (for example Ubuntu 22.04 arm64, or an older arm64
build image) pip finds no wheel and builds z3 from the sdist (slow, needs a C++ toolchain); pick a z3 5.x release
with a matching wheel there, or build on a newer base image.

The verdict does not depend on the solver version (a different
version may take a different time or pick a different witness of the same minimum), but this has not been tested
across versions: run `pytest product/tests` with the bundle's z3 before claiming it.

## OSS CAD Suite (YosysHQ)

How it is built: `builder.py` in the `oss-cad-suite-build` repository reads Python rule files in `default/rules/`
(`SourceLocation(...)` for a source repository, `Target(...)` for what gets built) and runs a matching shell script
in `default/scripts/<target>.sh` inside Docker, per architecture (linux-x64, linux-arm64, darwin-x64,
darwin-arm64, windows-x64). Python 3.11 is built as its own target (`python3`), and Python tools are installed into
it by scripts that source `default/patches/python3_package.sh` and call `python3_package_pip_install` (pip with
`--target .../lib/python3.11/site-packages`). Examples to copy: `rules/pyhdl.py` + `scripts/pyhdl.sh` (Amaranth,
Migen from git), `rules/cocotb.py` + `scripts/cocotb.sh`, `rules/formal.py` (sby and friends).

What matters for GlitchSAT:

- The suite already builds the z3 **binary** (`rules/solvers.py`, target `z3`) but its script removes `lib/` and
  `include/`, so the z3 Python bindings are not in the suite. GlitchSAT would add the `z3-solver` wheel through pip,
  which brings its own copy of `libz3` (a large binary; check the wheel size for each platform). Ask the maintainers
  whether that is acceptable or whether they prefer building the bindings from the z3 source they already pin.
- Cross-installing with pip for another architecture inside the build container must pick the wheel of the target
  platform, not of the build host. The existing helper sets `_PYTHON_HOST_PLATFORM` for this; a binary wheel such as
  `z3-solver` should be checked on every architecture (pip `--platform` / `--only-binary` may be needed).
- Yosys from the suite is on PATH after `source environment`, so Verilog input works without anything extra.

A draft rule, not tested (the target name and the pip spec are the parts to agree with the maintainers):

```python
# default/rules/glitchsat.py
from src.base import SourceLocation, Target

SourceLocation(
	name = 'glitchsat',
	vcs = 'git',
	location = 'https://github.com/Kavin-Re/GlitchSAT-Redundancy',
	revision = 'origin/main',          # better: a release tag
	license_file = 'LICENSE',
)

Target(
	name = 'glitchsat',
	sources = [ 'glitchsat' ],
	dependencies = [ 'python3', 'python3-native' ],
	resources = [ 'python3' ],
	patches = [ 'python3_package.sh' ],
)
```

```sh
# default/scripts/glitchsat.sh
source ${PATCHES_DIR}/python3_package.sh
python3_package_setup
python3_package_pip_install "./glitchsat/product[solver]"
# console scripts land in site-packages/bin with --target; pyhdl.sh moves them the same way
mv ${OUTPUT_DIR}${INSTALL_PREFIX}/lib/python3.11/site-packages/bin ${OUTPUT_DIR}${INSTALL_PREFIX}/.
```

How to ask: the README of the build repository describes building it yourself and says to "create an issue" for
problems; it names no process for proposing a new tool. Open an issue first (what the tool does, size, licence
Apache-2.0, the smoke tests above), then offer the rule as a pull request if they agree.

## IIC-OSIC-TOOLS

How it is built: a Docker image on `ubuntu:noble` (Python 3.12), assembled by `_build/build-*.sh` and
`docker-bake.hcl`. Tools built from source are listed with repository and commit in `_build/tool_metadata.yml` and
have an image directory in `_build/images/<tool>/`. Python packages are installed with pip in two places:
`_build/images/base/scripts/70_install_from_pip.sh` (support libraries, unpinned) and
`_build/images/iic-osic-tools/skel/headless/scripts/install_eda.sh` (EDA packages, each pinned with `==`, for
example `cocotb==2.1.0`, `fault-dft==0.9.4`, `pyverilog==1.3.0`). A few tools get their own virtual environment
under `/foss/tools/<name>/` when their dependencies clash. Image tests live in `_tests/NN/`; `_tests/03/pkgs.py`
checks that Python packages import.

What matters for GlitchSAT:

- The image ships Yosys (with sby, eqy, mcy) and the z3 C library from Ubuntu (`libz3-4`), but no `z3-solver`
  Python package was found in the pip lists. Adding `glitchsat[solver]==X.Y.Z` to the pinned list in
  `install_eda.sh` pulls in a 5.x `z3-solver` within the extra's range (above), which leaves room for another
  package's z3 5.x; a separate environment (`/foss/tools/glitchsat`) remains the fallback.
- The package must be on PyPI first: every entry in the pinned list is a PyPI release. The release workflow
  (`.github/workflows/release.yml`) exists but has not been run.
- A test for `_tests/`: `glitchsat --version`, the `evidence-example` + `validate-sarif` smoke test, and the solver
  smoke test on the bundled `v2.json`.

How to ask: the README's "Installed Tools" section ends with "If something useful is missing, please let us
know!", and its support section asks for GitHub issues and welcomes pull requests. Open an issue proposing the
package (one line for the tool list: "glitchsat: bounded fault-injection (bit-flip) analysis of Yosys netlists and
fault-margin evidence reports"), with the pinned version and the smoke tests.

## Before either request

- Publish a tagged release on PyPI (trusted publishing is set up in `release.yml`, not yet run).
- Run the test suite with the bundle's Python and z3 (the solver range above is already bundle-friendly).
- Keep the plain statement in the tool description: bounded results about modelled bit flips; the attack-potential
  figure is an estimate that supports, and never replaces, lab evaluation.
