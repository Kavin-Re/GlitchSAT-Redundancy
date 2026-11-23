#!/bin/sh
# cloud_bench.sh: run the SAT backend with a native solver (PySAT CaDiCaL) on every benchmark design for k = 1..3,
# run the z3 engine (scripts/glitchsat.py check) on the same cells, and print an agreement/timing table.
#
# Target machine: a cloud VM running Ubuntu 24.04 with pip access (python-sat and z3-solver from PyPI). It is meant to be
# run there, not on a personal machine: it installs nothing itself, but the setup below does, and the run takes a while.
#
#   one-time setup (Ubuntu 24.04 blocks system-wide pip, so use a venv):
#                     sudo apt-get install -y python3-venv yosys     (yosys is needed only for the real R20 netlists)
#                     python3 -m venv ~/gsat-venv && . ~/gsat-venv/bin/activate
#                     pip install python-sat z3-solver pytest numpy
#   run:              sh ext/fastsat/cloud_bench.sh                  (set GLITCHSAT_ROOT if ext/fastsat is not inside the repository)
#   options (environment variables):
#     BACKEND=cadical        PySAT solver name (cadical, cadical195, cadical153, glucose4, glucose42, minisat22, ...)
#                            or dimacs:<binary> for a solver binary on PATH (e.g. dimacs:kissat, dimacs:cadical), or py
#     TIMEOUT=300            seconds per SAT check
#     Z3_TIMEOUT=300         seconds per z3 check (a z3 timeout is shown as a timeout, never as a verdict)
#     SETS="core r20 proxy"  design sets (see ext/fastsat/bench/bench.py); add "repo" for all ~120 repository netlists
#     SKIP_TESTS=1           do not run the test-suite first
#     NO_Z3=1                run without z3 (no agreement table); by default a missing z3-solver is an error
#
# Nothing in this script contains expected timings. Every number it prints is measured by the run itself.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=${GLITCHSAT_ROOT:-$(cd "$HERE/../.." && pwd)}
[ -f "$ROOT/scripts/glitchsat.py" ] || { echo "error: repository root not found at $ROOT (set GLITCHSAT_ROOT)" >&2; exit 3; }
export GLITCHSAT_ROOT="$ROOT"
PY=${PYTHON:-python3}
BACKEND=${BACKEND:-cadical}
TIMEOUT=${TIMEOUT:-300}
Z3_TIMEOUT=${Z3_TIMEOUT:-300}
SETS=${SETS:-core r20 proxy}
STAMP=$(date +%Y%m%dT%H%M%S)
RES="$HERE/bench/results"
WORK="$HERE/bench/work"
mkdir -p "$RES" "$WORK/r20"
LOG="$RES/native_$STAMP.txt"

say() { echo "$@" | tee -a "$LOG"; }

say "== environment"
say "date: $(date)   host: $(uname -srm)"
say "cpu: $(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | sed 's/^ //')   cores: $(nproc 2>/dev/null || echo ?)"
say "python: $($PY --version 2>&1)"
case "$BACKEND" in
  py|dimacs:*) ;;
  *) if ! $PY -c "import pysat" 2>/dev/null; then
       echo "error: python-sat is not installed in this Python. Run: pip install python-sat   (or BACKEND=py for the slow bundled solver)" >&2; exit 3
     fi
     say "python-sat: $($PY -c 'import pysat; print(pysat.__version__)' 2>&1)" ;;
esac
Z3FLAG=""
if $PY -c "import z3" 2>/dev/null; then
  say "z3-solver: $($PY -c 'import z3; print(z3.get_version_string())')"; Z3FLAG="--z3 --z3-timeout $Z3_TIMEOUT"
elif [ -n "$NO_Z3" ]; then
  say "z3-solver: NOT installed, NO_Z3=1 -> no comparison with the z3 engine in this run"
else
  echo "error: z3-solver is not installed in this Python, so the agreement/timing table against z3 cannot be made." >&2
  echo "       pip install z3-solver   (or NO_Z3=1 to run the SAT side only)" >&2; exit 3
fi

# ---- R20 designs: synthesise with the repository flow when yosys is available (netlists are not stored in the repo)
D="$ROOT/research/c3/r20/designs"
if command -v yosys >/dev/null 2>&1; then
  say "yosys: $(yosys -V 2>&1 | head -1)"
  mk() {  # stem top file...
    stem=$1; top=$2; shift 2
    cat "$@" > "$WORK/r20/$stem.v"
    if sh "$ROOT/scripts/synth.sh" "$WORK/r20/$stem.v" "$top" "$WORK/r20/$stem.json" plain >>"$LOG" 2>&1; then
      say "  synthesised $stem ($top): $($PY -c "
import json,sys
m=json.load(open(sys.argv[1]))['modules'][sys.argv[2]]['cells'].values()
f=sum(1 for c in m if c['type']=='\$_DFF_P_'); g=sum(1 for c in m if c['type'] not in ('\$_DFF_P_','\$scopeinfo'))
print(g,'gates,',f,'flops')" "$WORK/r20/$stem.json" "$top")"
    else
      say "  synthesis of $stem FAILED (see $LOG); design skipped"; rm -f "$WORK/r20/$stem.json"
    fi
  }
  say "== R20 netlists (R20_REPORT.md recorded: sbox_unprot 1012/16, sbox_par 2040/17, sbox_par2 2040/25, sbox_dmr 2040/32, crc 40/9, crc_tmr 44/11, uart 368/34 with Yosys 0.33; other Yosys versions can give other counts)"
  mk sbox_unprot sbox_unprot "$D/aes_sbox/aes_sbox.v" "$D/wrappers/w_sbox_unprot.v"
  mk sbox_par    sbox_par    "$D/aes_sbox/aes_sbox.v" "$D/wrappers/w_sbox_par.v"
  mk sbox_par2   sbox_par2   "$D/aes_sbox/aes_sbox.v" "$D/wrappers/w_sbox_par2.v"
  mk sbox_dmr    sbox_dmr    "$D/aes_sbox/aes_sbox.v" "$D/wrappers/w_sbox_dmr.v"
  mk crc_plain   bootcrc     "$D/verilog_lfsr/lfsr.v" "$D/wrappers/w_crc.v"
  mk crc_tmr     bootcrc_tmr "$D/verilog_lfsr/lfsr.v" "$D/wrappers/w_crc_tmr.v"
  mk uart        uartw       "$D/verilog_uart_tx/uart_tx.v" "$D/wrappers/w_uart.v"
else
  say "yosys: NOT on PATH -> the R20 netlists (incl. the 2040-gate sbox_dmr target) cannot be built; only stored netlists and the S-box PROXIES are run."
  say "       sudo apt install yosys   then re-run to cover the real target."
fi

# ---- tests (quick confidence that the backend and the native solver agree with the exhaustive reference here)
if [ -z "$SKIP_TESTS" ] && $PY -c "import pytest" 2>/dev/null; then
  say "== test-suite (ext/fastsat/tests)"
  ( cd "$HERE" && $PY -m pytest -q tests 2>&1 | tail -3 ) | tee -a "$LOG"
  case "$BACKEND" in py|dimacs:*) ;; *)
    say "== exhaustive cross-check with the native solver (bench/verify_all.py --quick --backend $BACKEND)"
    ( cd "$HERE/bench" && $PY verify_all.py --quick --backend "$BACKEND" --out "$RES/verify_native_$STAMP.json" 2>&1 | tail -6 ) | tee -a "$LOG" ;;
  esac
fi

# ---- the benchmark table
say "== benchmark: backend $BACKEND, k = 1 2 3, timeout ${TIMEOUT}s  (columns 'k<=j s': one solver instance, budgets as assumptions;"
say "   'check k=K s': a fresh check per budget incl. CNF build and minimisation, the figure comparable with the z3 column)"
set +e
( cd "$HERE/bench" && $PY bench.py --set $SETS --backend "$BACKEND" --k 1 2 3 --timeout "$TIMEOUT" --per-k $Z3FLAG \
    --r20-dir "$WORK/r20" --out "$RES/native_$STAMP.json" ) 2>&1 | tee -a "$LOG"
say "== same designs without fault collapsing (every time-relevant site keeps its own variable)"
( cd "$HERE/bench" && $PY bench.py --set $SETS --backend "$BACKEND" --k 1 2 3 --timeout "$TIMEOUT" --no-collapse \
    --r20-dir "$WORK/r20" --out "$RES/native_${STAMP}_nocollapse.json" ) 2>&1 | tee -a "$LOG"
say "== summary: the agreement/timing table against z3 is the second table of the first benchmark above"
if [ -n "$Z3FLAG" ]; then say "$(grep -h '^agreement with z3' "$LOG" | head -1)"; fi
say "results: $LOG  and  $RES/native_$STAMP*.json"
if grep -q '^agreement with z3: [0-9]* equal, [1-9][0-9]* DIFFERENT' "$LOG"; then echo "DISAGREEMENT with the z3 engine: see the table above" >&2; exit 1; fi
