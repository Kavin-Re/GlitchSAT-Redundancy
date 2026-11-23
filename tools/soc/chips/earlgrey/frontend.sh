#!/usr/bin/env bash
# OpenTitan Earl Grey (top_earlgrey) whole-chip front end. Own code, Apache-2.0.
#
#   bash chips/earlgrey/frontend.sh fetch            sparse clone at tag Earlgrey-PROD-M6 (commit checked)
#   bash chips/earlgrey/frontend.sh elab             read_slang + hierarchy + stat           -> work/earlgrey/elab.*
#   bash chips/earlgrey/frontend.sh coarse           + proc, opt, memory -nomap (RTL cells)  -> work/earlgrey/coarse.il
#   bash chips/earlgrey/frontend.sh gates            coarse.il -> gates, no logic optimisation -> work/earlgrey/earlgrey_written.json
#   bash chips/earlgrey/frontend.sh hier             hierarchical: per-module gates, chip totals -> work/earlgrey/hier.stat
#   bash chips/earlgrey/frontend.sh abc              gates.il -> ABC-optimised gates         -> work/earlgrey/earlgrey_flat.json
# Each step is resumable (it starts from the file the previous step wrote) and prints wall time and peak memory.
# Environment: YOSYS or GSOC_YOSYS_SLANG (a Yosys with read_slang; default `yosys` on PATH),
#              GSOC_WORK (default ext/soc/work), STEP_TIMEOUT seconds (default 560).
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${GSOC_WORK:-$HERE/../../work}
W=$WORK/earlgrey
OT=$WORK/src/opentitan
URL=https://github.com/lowRISC/opentitan
TAG=Earlgrey-PROD-M6
COMMIT=a78922f14a8cc20c7ee569f322a04626f2ac6127
TOP=${TOP:-top_earlgrey}
TO=${STEP_TIMEOUT:-560}
YOSYS=${YOSYS:-${GSOC_YOSYS_SLANG:-$(command -v yosys)}}
mkdir -p "$W" "$WORK/src"
step=${1:-elab}

measure() { python3 "$HERE/runmeasure.py" "$TO" "$@"; }

case $step in
fetch)
  if [ ! -d "$OT/.git" ]; then
    GIT_LFS_SKIP_SMUDGE=1 git clone --quiet --depth 1 --filter=blob:none --sparse --branch "$TAG" "$URL" "$OT"
  fi
  have=$(git -C "$OT" rev-parse HEAD)
  [ "$have" = "$COMMIT" ] || { echo "fetch: $OT is at $have, expected $COMMIT" >&2; exit 3; }
  git -C "$OT" sparse-checkout set --no-cone '/LICENSE' '/hw/top_earlgrey/rtl/' '/hw/top_earlgrey/ip/*/rtl/' \
      '/hw/top_earlgrey/ip_autogen/*/rtl/' '/hw/top_earlgrey/data/' '/hw/top_englishbreakfast/' '/hw/ip/*/rtl/' \
      '/hw/ip/prim*/' '/hw/ip/tlul/' '/hw/vendor/lowrisc_ibex/rtl/' '/hw/vendor/pulp_riscv_dbg/src/' \
      '/hw/vendor/pulp_riscv_dbg/debug_rom/' '/hw/dv/sv/dv_utils/'
  grep -q "Apache License" "$OT/LICENSE"
  echo "opentitan at $have ($TAG, Apache-2.0) in $OT: $(find "$OT/hw" -name '*.sv' | wc -l) SystemVerilog files"
  ;;
elab|coarse)
  python3 "$HERE/gen_prim_shims.py" "$OT" "$W/prim_shims.sv" > "$W/prim_shims.txt"
  cd "$OT"
  # packages: every *_pkg.sv of the design; where a name exists twice the top-specific (generated) file wins
  PK=$(find hw/top_earlgrey hw/ip hw/vendor/lowrisc_ibex/rtl hw/vendor/pulp_riscv_dbg/src -name '*_pkg.sv' \
        -not -path '*/dv/*' -not -path '*_dv/*' -not -path '*/fpv/*' -not -path '*prim_xilinx*' -not -path '*/tb/*' \
        | awk -F/ '{ if (!seen[$NF]++) print }' | tr '\n' ' ')
  YD=""
  for d in hw/top_earlgrey/rtl/autogen hw/top_earlgrey/rtl hw/top_earlgrey/ip_autogen/*/rtl hw/top_earlgrey/ip/*/rtl/autogen \
           hw/top_earlgrey/ip/*/rtl hw/ip/*/rtl hw/vendor/lowrisc_ibex/rtl hw/vendor/pulp_riscv_dbg/src \
           hw/vendor/pulp_riscv_dbg/debug_rom; do
    case $d in *prim_xilinx*) ;; *) [ -d "$d" ] && YD="$YD -y $d" ;; esac
  done
  # One compilation unit, as FuseSoC builds it: the assertion and flop macros are defined once, first, and
  # library files inherit them.
  printf '`include "prim_assert.sv"\n`include "prim_flop_macros.sv"\n' > "$W/prelude.sv"
  printf '`include "hw/top_earlgrey/rtl/autogen/%s.sv"\n' "$TOP" > "$W/top_inc.sv"
  {
    [ -n "${GSOC_SLANG_PLUGIN:-}" ] && echo "plugin -i slang"      # Yosys builds where read_slang is a plugin
    echo "read_slang --top $TOP -DSYNTHESIS -DYOSYS --allow-use-before-declare --ignore-initial \\"
    echo "  --single-unit --libraries-inherit-macros ${SLANG_EXTRA:-} \\"
    echo "  -I . -I hw/ip/prim/rtl -I hw/dv/sv/dv_utils -I hw/vendor/lowrisc_ibex/rtl $YD --libext sv \\"
    echo "  $W/prelude.sv $PK $W/prim_shims.sv $W/top_inc.sv"
    echo "hierarchy -check -top $TOP"
    echo "tee -o $W/elab.stat stat"
    if [ "$step" = coarse ]; then
      echo "proc; opt_expr; opt_clean; memory -nomap; opt_clean"
      echo "tee -o $W/coarse.stat stat"
      echo "write_rtlil $W/coarse.il"
    fi
  } > "$W/$step.ys"
  measure "$YOSYS" -q -l "$W/$step.log" "$W/$step.ys" 2>&1 | grep -v 'Warning' | tail -25 | cut -c1-300
  ;;
gates)
  # RTL cells -> gates (the gate set of the loader) with constant folding only: the chip "as written".
  [ -s "$W/coarse.il" ] || { echo "run the coarse step first" >&2; exit 3; }
  {
    echo "read_rtlil $W/coarse.il"
    echo 'memory_map t:$mem_v2 r:SIZE<=4096 %i'
    echo "techmap; opt_expr; opt_clean"
    echo "tee -o $W/gates.stat stat"
    echo "write_rtlil $W/gates.il"
    echo "write_json $W/earlgrey_written.json"
  } > "$W/gates.ys"
  measure "$YOSYS" -q -l "$W/gates.log" "$W/gates.ys" 2>&1 | tail -8 | cut -c1-300
  ;;
abc)
  # Logic optimisation of the whole flattened chip (the `flat` flow). Not resumable inside ABC: needs one long run.
  [ -s "$W/gates.il" ] || { echo "run the gates step first" >&2; exit 3; }
  {
    echo "read_rtlil $W/gates.il"
    echo "opt -fast; abc -g AND,OR,XOR,MUX; opt -fast; opt_clean"
    echo "tee -o $W/abc.stat stat"
    echo "write_json $W/earlgrey_flat.json"
  } > "$W/abc.ys"
  measure "$YOSYS" -q -l "$W/abc.log" "$W/abc.ys" 2>&1 | tail -8 | cut -c1-300
  ;;
hier)
  # Hierarchical route for machines where flattening does not fit: every module is mapped to gates on its own
  # (each distinct module once), nothing is flattened. Gives gate and flop counts per module and for the chip.
  cd "$OT"
  sed -e 's/^read_slang --top/read_slang --keep-hierarchy --top/' -e '/^hierarchy -check/q' -e '/^tee -o/d' "$W/elab.ys" > "$W/hier.ys"
  {
    echo "proc; opt_expr; opt_clean; memory -nomap; opt_clean"
    echo 'memory_map t:$mem_v2 r:SIZE<=64 %i'
    echo "techmap; opt_expr; opt_clean"
    echo "tee -o $W/hier.stat stat -top $TOP"
    echo "write_rtlil $W/hier.il"
  } >> "$W/hier.ys"
  [ -s "$W/elab.ys" ] || { echo "run the elab step first" >&2; exit 3; }
  measure "$YOSYS" -q -l "$W/hier.log" "$W/hier.ys" 2>&1 | grep -v 'Warning' | tail -8 | cut -c1-300
  ;;
*) echo "unknown step $step" >&2; exit 3 ;;
esac
