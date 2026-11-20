#!/bin/bash
# run from layout/v_designs
export PATH=/tmp/mm_root2/envs/eda/bin:$PATH
P=/tmp/mm_root2/envs/eda/share/pdk/sky130A
for d in v1; do
  [ "$1" = norun ] || flow_patched/run.sh $d
  python3 flow_patched/pinpaint.py out_patched/$d.def > out_patched/${d}_pinpaint.tcl
  python3 flow_patched/pwrlabels.py out_patched/$d.def > out_patched/${d}_pwrlabels.tcl
  DESIGN=$d magic -dnull -noconsole -rcfile $P/libs.tech/magic/sky130A.magicrc flow_patched/gds.tcl > out_patched/${d}_magic.log 2>&1
  python3 flow_patched/v2spice.py out_patched/${d}_pnr.v out_patched/${d}_top.spice $P/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice
  
  cat $P/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice out_patched/${d}_top.spice > out_patched/${d}_ref.spice
  bash flow_patched/lvs.sh $d > out_patched/${d}_lvs.log 2>&1
done
