#!/usr/bin/env bash
# Regenerate TRUE SDF timing for the placed V1/V2 netlists with OpenSTA, and drop <design>.sdf next to
# each netlist so run_vlab.py picks it up automatically (delay model flips ASSUMED -> SOURCED(sdf)).
#
# Runs on a cloud VM (or any Linux machine) with OpenSTA (or OpenROAD, which bundles `sta`) and the sky130
# PDK installed. Not run on the VM that produced the stored results (no EDA tool was installed there).
#
#   LIB=/path/to/sky130_fd_sc_hd__tt_025C_1v80.lib  ./regen_sdf.sh
#
set -euo pipefail
STA="${STA:-sta}"                                    # or: openroad -exit, with `sta` commands
LIB="${LIB:?set LIB to the sky130_fd_sc_hd typical-corner .lib (from the PDK; not in the repo)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# repository root: $GLITCHSAT_ROOT ($GLITCHSAT_REPO is an older alias), else the checkout this script sits in
# (<repo>/ext/vlab/eda -> three levels up)
REPO="${GLITCHSAT_ROOT:-${GLITCHSAT_REPO:-$(cd "$HERE/../../.." && pwd)}}"
[ -d "$REPO/layout/v_designs" ] || { echo "GlitchSAT checkout not found at $REPO: set GLITCHSAT_ROOT" >&2; exit 3; }

for d in v1 v2; do
  NL="$REPO/layout/v_designs/out_patched/${d}_pnr.v"
  OUTDIR="$REPO/layout/v_designs/out_patched"
  echo "== $d : $NL"
  DESIGN="$d" NETLIST="$NL" LIB="$LIB" \
    SDF="$OUTDIR/${d}.sdf" REPORT="$OUTDIR/${d}_sta.rpt" \
    "$STA" -no_init -exit "$HERE/regen_sdf.tcl"
done

echo
echo "Now re-run the lab with sourced timing:"
echo "  cd $HERE/.. && python3 run_vlab.py"
echo "The campaign JSON will report delay_model.source = SOURCED(sdf)."
