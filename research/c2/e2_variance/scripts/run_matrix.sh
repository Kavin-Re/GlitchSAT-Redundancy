#!/bin/sh
# Builds each (yosys, variant, design) netlist and analyses it. Output: jsonl on stdout.
W=/tmp/work_e2
for YN in $YLIST; do
 case $YN in apt) Y=/usr/bin/yosys;; y038) Y=/tmp/mm_root/envs/formal/bin/yosys;; ynew) Y=/tmp/mm_root/envs/ynew/bin/yosys;; esac
 for VAR in base abc_fast abc_noMUX abc_AND_only noabc opt_flow opt_flow_fast post_opt_merge post_opt_full flatten_first flatten_first_fast flatten_first_noabc abc_dff flatten_first_abc_dff; do
  for D in v0 v1 v2; do
   J=$W/nl/${YN}_${VAR}_$D.json
   if sh $W/scripts/variants.sh $Y $W/$D.v $D $J $VAR 2>$J.err; then
     R=$(timeout 600 python3 -I $W/scripts/analyze.py $J $D --k 3 --cycles 6 2>&1 | tail -1)
     echo "{\"yosys\":\"$YN\",\"variant\":\"$VAR\",\"design\":\"$D\",\"r\":$R}"
   else echo "{\"yosys\":\"$YN\",\"variant\":\"$VAR\",\"design\":\"$D\",\"r\":{\"synth_failed\":true}}"; fi
  done
 done
done
