#!/bin/sh
# Re-run every validation and rebuild results/RESULTS.md.
#   GLITCHSAT_ROOT=/path/to/glitchsat sh validation/run_all.sh [NAME=/path/to/yosys ...]
# With no argument the Yosys found on PATH is used as build "apt0.33" if it reports version 0.33, else as "local".
set -e
cd "$(dirname "$0")"
BUILDS=""
for b in "$@"; do BUILDS="$BUILDS --build $b"; done
if [ -z "$BUILDS" ] && command -v yosys >/dev/null 2>&1; then
  case "$(yosys -V)" in *"Yosys 0.33"*) BUILDS="--build apt0.33=$(command -v yosys)" ;; *) BUILDS="--build local=$(command -v yosys)" ;; esac
fi
if [ -n "$BUILDS" ]; then python3 e2_matrix.py $BUILDS --designs v1,v2 >/dev/null; python3 stored_netlists.py >/dev/null
else echo "Yosys not found: synthesis validations NOT RUN (their sections keep the last stored results, if any)"; fi
python3 placement.py >/dev/null
python3 firmware.py >/dev/null
python3 real_designs.py >/dev/null || echo "real designs: NOT RUN"
python3 make_results.py
