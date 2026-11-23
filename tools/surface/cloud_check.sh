#!/usr/bin/env bash
# Cloud check for ext/surface: runs the tests (the z3 ones too, when z3 is installed) and compares the z3
# enumeration of minimum attacks with the exhaustive simulator, attack set by attack set.
# Usage: bash ext/surface/cloud_check.sh [--slow]     (from anywhere; needs python3, numpy, pytest; z3-solver for parts 2-3)
# Exit: 0 = CLOUD CHECK PASSED (everything ran), 1 = CLOUD CHECK FAILED, 2 = CLOUD CHECK INCOMPLETE (z3 missing:
# the z3 parts did not run, so this is NOT a full pass), 3 = setup error.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export GLITCHSAT_ROOT="${GLITCHSAT_ROOT:-$(cd "$HERE/../.." && pwd)}"
PY="${PYTHON:-python3}"
SLOW=""
if [ "${1:-}" = "--slow" ]; then SLOW="--slow"; export GLITCHSAT_SLOW=1; fi
echo "repository: $GLITCHSAT_ROOT"
if [ ! -f "$GLITCHSAT_ROOT/scripts/glitchsat.py" ]; then echo "scripts/glitchsat.py not found: set GLITCHSAT_ROOT to the repository root"; exit 3; fi
if ! "$PY" -c "import numpy, pytest" 2>/dev/null; then echo "need numpy and pytest: pip install numpy pytest"; exit 3; fi
if "$PY" -c "import z3" 2>/dev/null; then HAVE_Z3=1; echo "z3: $("$PY" -c 'import z3; print(z3.get_version_string())')"; else HAVE_Z3=0; echo "z3: not installed (pip install z3-solver); the z3 tests will be skipped"; fi
TMP="$(mktemp -d "${TMPDIR:-/tmp}/surface_check.XXXXXX")" || exit 3
trap 'rm -rf "$TMP"' EXIT
status=0
echo "== 1. tests"
"$PY" -m pytest -q "$HERE/tests" || status=1
if [ "$HAVE_Z3" = 1 ]; then
  echo "== 2. z3 enumeration vs exhaustive simulator"
  "$PY" "$HERE/scripts/compare_methods.py" $SLOW || status=1
  echo "== 3. timing of the z3 path on V2 stored (6 cycles, k<=3)"
  "$PY" "$HERE/scripts/attack_surface.py" "$GLITCHSAT_ROOT/reference/spike_netlists/v2.json" --top v2 --cycles 6 --method sat > "$TMP/surface_sat_v2.txt" || status=1
  head -3 "$TMP/surface_sat_v2.txt"
else
  echo "== 2./3. NOT RUN: z3 not installed"
fi
echo "== 4. lint on the reference netlists"
for d in v1 v2; do "$PY" "$HERE/scripts/merge_lint.py" "$GLITCHSAT_ROOT/reference/spike_netlists/$d.json" --top $d > "$TMP/surface_lint_$d.txt" || status=1; head -3 "$TMP/surface_lint_$d.txt"; done
if [ $status != 0 ]; then echo "CLOUD CHECK FAILED"; exit 1; fi
if [ "$HAVE_Z3" = 0 ]; then echo "CLOUD CHECK INCOMPLETE (z3 missing): parts 2-3 did not run; install z3-solver and re-run"; exit 2; fi
echo "CLOUD CHECK PASSED"
exit 0
