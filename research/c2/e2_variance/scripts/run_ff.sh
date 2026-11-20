#!/bin/sh
W=/tmp/work_e2
for YN in $YLIST; do
 case $YN in apt) Y=/usr/bin/yosys;; y038) Y=/tmp/mm_root/envs/formal/bin/yosys;; ynew) Y=/tmp/mm_root/envs/ynew/bin/yosys;; esac
 for VAR in $VARS; do for D in v0 v1 v2; do
   J=$W/nl/${YN}_${VAR}_$D.json
   if sh $W/scripts/variants.sh $Y $W/$D.v $D $J $VAR 2>$J.err; then
     R=$(timeout 600 python3 -I $W/scripts/analyze.py $J $D --k 3 --cycles 6 2>&1 | tail -1)
     echo "{\"yosys\":\"$YN\",\"variant\":\"$VAR\",\"design\":\"$D\",\"r\":$R}"
   else echo "{\"yosys\":\"$YN\",\"variant\":\"$VAR\",\"design\":\"$D\",\"r\":{\"synth_failed\":true}}"; fi
 done; done
done
