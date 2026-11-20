#!/bin/bash
# usage: run_var.sh VAR UTIL PLACE ax0 ay0 ax1 ay1 ax2 ay2
set -u; cd /tmp/work_l2
export PATH=/tmp/mm_root/envs/eda/bin:$PATH
V=$1; export VAR=$V UTIL=$2 PLACE=$3 AX0=${4:-0} AY0=${5:-0} AX1=${6:-0} AY1=${7:-0} AX2=${8:-0} AY2=${9:-0}
export OUT=out_$V DESIGN=v2; mkdir -p $OUT; cp out_patched/v2_net.v $OUT/ 2>/dev/null
P=/tmp/mm_root/envs/eda/share/pdk/sky130A
T0=$(date +%s)
timeout 600 openroad -no_splash -exit pnr_l2.tcl > $OUT/v2_openroad.log 2>&1 ; echo "openroad rc $?"
python3 flow_patched/pinpaint.py $OUT/v2.def > $OUT/v2_pinpaint.tcl
python3 flow_patched/pwrlabels.py $OUT/v2.def > $OUT/v2_pwrlabels.tcl
sed "s#out_patched#$OUT#g" flow_patched/gds.tcl > $OUT/gds.tcl
timeout 600 magic -dnull -noconsole -rcfile $P/libs.tech/magic/sky130A.magicrc $OUT/gds.tcl > $OUT/v2_magic.log 2>&1; echo "magic rc $?"
python3 flow_patched/v2spice.py $OUT/v2_pnr.v $OUT/v2_top.spice $P/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice
cat $P/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice $OUT/v2_top.spice > $OUT/v2_ref.spice
sed "s#out_patched#$OUT#g" flow_patched/lvs.sh > $OUT/lvs.sh
timeout 600 bash $OUT/lvs.sh v2 > $OUT/v2_lvs.log 2>&1; echo "netgen rc $?"
echo "total_s $(( $(date +%s)-T0 ))" > $OUT/time.txt
