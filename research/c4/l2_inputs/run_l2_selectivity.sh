#!/bin/bash
# Regenerates L2's selectivity inputs (extract -> geometry -> minimal sets -> radius sweep) for one or all variants
# from the stored DEF + post-route netlist + sizes-only LEF. usage: run_l2_selectivity.sh WORKDIR [VAR ...]   (default VARs: base v8 s8 v15 rr)
# needs: python3 + z3-solver only (no OpenROAD). Variants run in parallel.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); W=$(cd "${1:?workdir}" && pwd); shift
VARS=${*:-base v8 s8 v15 rr}
export LEF=$HERE/lef/sky130_fd_sc_hd_sizes_only.lef
for V in $VARS; do
 (
  D=$W/$V; mkdir -p $D/nl; cd $D; cp $HERE/code/*.py .
  cp $HERE/def/$V.def v2.def; cp $HERE/pnr/${V}_pnr.v v2_pnr.v; export L2OUT=$D
  timeout 120 python3 layout_extract.py v2 > extract.log 2>&1
  timeout 300 python3 geom_report.py v2 > geom.log 2>&1
  timeout 900 python3 minsets.py v2 4 > minsets.log 2>&1
  timeout 1500 python3 radius_sweep.py v2 > sweep.log 2>&1
  echo done > DONE
 ) &
done
wait
