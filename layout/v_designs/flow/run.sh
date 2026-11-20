#!/bin/bash
# usage: flow/run.sh v1|v2   (run from layout/v_designs)
set -e; D=$1
export PATH=/tmp/mm_root/envs/eda/bin:$PATH DESIGN=$D
LIB=/tmp/mm_root/envs/eda/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
sed "s#@D@#$D#g;s#@LIB@#$LIB#g" flow/synth.ys.tpl > out/$D.ys
T0=$(date +%s.%N)
yosys -q -l out/${D}_yosys.log out/$D.ys
T1=$(date +%s.%N)
openroad -no_splash -exit flow/pnr.tcl > out/${D}_openroad.log 2>&1
T2=$(date +%s.%N)
echo "synth_s $(echo "$T1-$T0"|bc) pnr_s $(echo "$T2-$T1"|bc)" > out/${D}_time.txt
