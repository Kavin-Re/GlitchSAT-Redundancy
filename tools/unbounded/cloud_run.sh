#!/bin/sh
# cloud_run.sh: run the unbounded analysis with native SAT solvers (python-sat CaDiCaL, z3) and compare the verdicts
# with the stored pure-Python results (results/summary.json).
#
# Target machine: a cloud VM running Ubuntu 24.04 with pip access. Any Linux host with Python >= 3.9 also works.
# Requires ext/fastsat next to ext/unbounded (the stored results were produced with its minicdcl.py).
# Status: UNTESTED HERE. The cloud VM these files were written on has neither python-sat nor z3-solver, so the
# pysat/z3 adapters were exercised only against a stand-in module (tests/fake_pysat). This script is the real test.
#
#   one-time setup (Ubuntu 24.04 blocks system-wide pip, so use a venv):
#       sudo apt-get install -y python3-venv
#       python3 -m venv ~/gsat-venv && . ~/gsat-venv/bin/activate
#       pip install python-sat z3-solver pytest
#   run:
#       sh ext/unbounded/cloud_run.sh          (set GLITCHSAT_ROOT if ext/unbounded is not inside the repository)
#   options (environment variables):
#       KMAX=3          budgets 0..KMAX for the full comparison run (all three methods; the explicit one is slow above 3)
#       TIMEOUT=600     seconds per SAT method and cell (a timeout gives UNKNOWN, never a verdict)
#       SKIP_TESTS=1    do not run the test suite first
#       NO_Z3=1         skip the z3 runs
#
# Nothing in this script contains expected timings or verdicts; every number it prints is measured by the run itself.
# Results go to ext/unbounded/results/cloud_<timestamp>/ ; the stored results/ files are not overwritten.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=${GLITCHSAT_ROOT:-$(cd "$HERE/../.." && pwd)}
[ -f "$ROOT/scripts/glitchsat.py" ] || { echo "error: repository root not found at $ROOT (set GLITCHSAT_ROOT)" >&2; exit 3; }
export GLITCHSAT_ROOT="$ROOT"
PY=${PYTHON:-python3}
# hard dependency: the stored results/ were produced with ext/fastsat/scripts/minicdcl.py
$PY -c "import sys; sys.path.insert(0, '$HERE/src'); import sat; p, h, same = sat.minicdcl_info(); print('minicdcl:', p, h, 'matches results/' if same else 'DIFFERS from the version that produced results/')" \
  || { echo "error: ext/unbounded requires ext/fastsat (ext/fastsat/scripts/minicdcl.py next to ext/unbounded, or GLITCHSAT_MINICDCL_DIR)" >&2; exit 3; }
KMAX=${KMAX:-3}
TIMEOUT=${TIMEOUT:-600}
STAMP=$(date +%Y%m%dT%H%M%S)
OUT="$HERE/results/cloud_$STAMP"
mkdir -p "$OUT"
LOG="$OUT/run.log"
say() { echo "$@" | tee -a "$LOG"; }
# run a command, keep its output in the log, keep its exit code (plain sh has no pipefail), print the wall time
run() { t0=$(date +%s); "$@" > "$OUT/.last" 2>&1; rc=$?; cat "$OUT/.last" | tee -a "$LOG"; say "(exit $rc, $(( $(date +%s) - t0 )) s wall)"; return $rc; }

say "== environment"
say "date: $(date)   host: $(uname -srm)"
say "cpu: $(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | sed 's/^ //')   cores: $(nproc 2>/dev/null || echo ?)"
say "python: $($PY --version 2>&1)"
if ! $PY -c "import pysat.solvers" 2>/dev/null; then
  echo "error: python-sat is not installed in this Python: pip install python-sat" >&2; exit 3
fi
say "python-sat: $($PY -c 'import pysat; print(pysat.__version__)' 2>&1)"
BACKENDS="pysat:cadical153"
if [ -z "$NO_Z3" ]; then
  if $PY -c "import z3" 2>/dev/null; then
    say "z3-solver: $($PY -c 'import z3; print(z3.get_version_string())')"; BACKENDS="$BACKENDS z3"
  else
    echo "error: z3-solver is not installed: pip install z3-solver   (or NO_Z3=1)" >&2; exit 3
  fi
fi

status=0
if [ -z "$SKIP_TESTS" ]; then
  say "== 1. test suite (the real-backend tests run here instead of skipping)"
  run $PY -m pytest -q -rs "$HERE/tests" || status=1
fi

for B in $BACKENDS; do
  D="$OUT/$(echo "$B" | tr ':' '_')"
  say "== 2. all designs, k = 0..$KMAX, three power-up options, three methods, backend $B"
  run $PY "$HERE/src/unbounded.py" all --backend "$B" --kmax "$KMAX" --timeout "$TIMEOUT" --out-dir "$D" || status=1
done

say "== 3. verdict comparison with the stored pure-Python run"
SUMS="$HERE/results/summary.json"
for B in $BACKENDS; do SUMS="$SUMS $OUT/$(echo "$B" | tr ':' '_')/summary_$(echo "$B" | tr ':' '_').json"; done
run $PY "$HERE/src/unbounded.py" compare $SUMS || status=1

if [ $status = 0 ]; then say "CLOUD RUN PASSED (results in $OUT)"; else say "CLOUD RUN FAILED (see $LOG)"; fi
exit $status
