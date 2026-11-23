#!/bin/sh
# Re-synthesis check for the fixes written by `glitchsat harden` (the part that needs Yosys).
#
# Target: a fresh cloud VM with Ubuntu 24.04 (apt Yosys 0.33, pip z3-solver pinned by ci/requirements-ci.txt). Run from anywhere:
#     GLITCHSAT_ROOT=/path/to/glitchsat sh ext/harden/cloud/run_cloud.sh            # full grid (3 x 192 netlists per design)
#     QUICK=1 GLITCHSAT_ROOT=/path/to/glitchsat sh ext/harden/cloud/run_cloud.sh    # 16 configurations per design, minutes
# Environment: GLITCHSAT_ROOT (repository root, default two levels above ext/harden), OUT (default ext/harden/cloud_out),
#              WORKERS (parallel jobs, default nproc), NO_Z3=1 (skip the z3 cross-check), NO_INSTALL=1 (tools already there).
#
# What it does, in order:
#   1. installs yosys (apt) and numpy plus $ROOT/ci/requirements-ci.txt (pip, in a venv: z3-solver==5.4.1.0, the
#      version the repository's results were recorded with, and pytest), and records the versions and `pip freeze`
#   2. runs the test suite (pytest)
#   3. calibration: synthesises the repository rtl/v2.v with scripts/synth.sh (plain flow) and checks that the simulator
#      gives the recorded apt 0.33 value (2 flips, research/c2/e2_variance/E2_REPORT.md section 2)
#   4. for every results/designs/*.spec.json: the before design (repository RTL and harden's description of it) and the
#      hardened design, each synthesised with the 96 configurations of research/c2/e2_variance x copy-separation guard
#      off/on, every netlist re-verified by exhaustive simulation (every number of cycles, up to the goal); with z3, the
#      plain-flow default-ABC netlists are also checked by scripts/glitchsat.py (6 cycles)
#   5. writes $OUT/resynth_summary.md, $OUT/resynth_rows.csv, $OUT/env.txt, $OUT/calibration.txt and $OUT.tar.gz
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
ROOT=${GLITCHSAT_ROOT:-$(cd "$HERE/../.." && pwd)}
OUT=${OUT:-$HERE/cloud_out}
WORKERS=${WORKERS:-$(nproc)}
[ -f "$ROOT/scripts/glitchsat.py" ] || { echo "run_cloud.sh: repository not found at $ROOT; set GLITCHSAT_ROOT" >&2; exit 3; }
export GLITCHSAT_ROOT="$ROOT"
mkdir -p "$OUT"

# 1. tools
if [ "${NO_INSTALL:-0}" != 1 ]; then
  SUDO=""; [ "$(id -u)" = 0 ] || SUDO=sudo
  $SUDO apt-get update -q
  $SUDO apt-get install -y -q yosys python3-venv python3-pip
  python3 -m venv "$HERE/.venv"
  . "$HERE/.venv/bin/activate"
  [ -f "$ROOT/ci/requirements-ci.txt" ] || { echo "run_cloud.sh: $ROOT/ci/requirements-ci.txt not found" >&2; exit 3; }
  python3 -m pip install -q numpy -r "$ROOT/ci/requirements-ci.txt"
fi
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "os: $(. /etc/os-release && echo "$PRETTY_NAME")"
  echo "yosys: $(yosys -V)"
  echo "python: $(python3 -V 2>&1)"
  python3 -c "import numpy; print('numpy:', numpy.__version__)"
  python3 -c "import z3; print('z3:', z3.get_version_string())" 2>/dev/null || echo "z3: not installed"
  echo "cpus: $(nproc)"
  echo "pip freeze:"
  python3 -m pip freeze 2>/dev/null | sed 's/^/  /'
} | tee "$OUT/env.txt"

# 2. tests
cd "$HERE"
python3 -m pytest -q tests 2>&1 | tee "$OUT/pytest.txt" | tail -3

# 3. calibration against a recorded value
CAL="$OUT/calibration"
mkdir -p "$CAL"
sh "$ROOT/scripts/synth.sh" "$ROOT/rtl/v2.v" v2 "$CAL/v2_plain.json" plain
PYTHONPATH="$HERE" python3 -m harden check "$CAL/v2_plain.json" --top v2 --kmax 3 --cycles 6 | tee "$OUT/calibration.txt"
grep -q 'minimum flips: 2' "$OUT/calibration.txt" && echo "calibration: matches the recorded apt 0.33 value (2)" | tee -a "$OUT/calibration.txt" \
  || echo "calibration: DIFFERS from the recorded apt 0.33 value (2); read the rows below with that in mind" | tee -a "$OUT/calibration.txt"

# 4. re-synthesis grid
Z3FLAG="--z3"; [ "${NO_Z3:-0}" = 1 ] && Z3FLAG=""
QFLAG=""; [ "${QUICK:-0}" = 1 ] && QFLAG="--quick"
PYTHONPATH="$HERE" python3 -m harden resynth --specs "$HERE/results/designs" --out "$OUT" --root "$ROOT" --workers "$WORKERS" $Z3FLAG $QFLAG \
  2>&1 | tee "$OUT/resynth.log" | grep -v '^\[' || true

# 5. bundle
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo "done: $OUT/resynth_summary.md ($OUT.tar.gz)"
