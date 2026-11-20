#!/bin/bash
# usage: flow_patched/run.sh v1|v2   (run from layout_patched/v_designs)
set -e; D=$1
export PATH=/tmp/mm_root2/envs/eda/bin:$PATH DESIGN=$D
LIB=/tmp/mm_root2/envs/eda/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
sed "s#@D@#$D#g;s#@LIB@#$LIB#g" flow_patched/synth.ys.tpl > out_patched/$D.ys
T0=$(date +%s.%N)
yosys -q -l out_patched/${D}_yosys.log out_patched/$D.ys
T1=$(date +%s.%N)
openroad -no_splash -exit flow_patched/pnr.tcl > out_patched/${D}_openroad.log 2>&1
T2=$(date +%s.%N)
echo "synth_s $(echo "$T1-$T0"|bc) pnr_s $(echo "$T2-$T1"|bc)" > out_patched/${D}_time.txt
