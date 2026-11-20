#!/bin/bash
Y38=/tmp/mm_root/envs/formal/bin/yosys
i=0
declare -a SC=(
"abc -g AND,OR,XOR,MUX"
"abc -g AND,OR,XOR"
"abc -fast -g AND,OR,XOR,MUX"
"abc -fast -g AND,OR,XOR"
"abc -g AND,OR"
"abc -g AND,OR,MUX"
"abc -script +strash;dc2;map -g AND,OR,XOR"
"abc -g AND,OR,XOR,MUX -D 1000"
)
for v in 033 038; do
  if [ $v = 033 ]; then Y=yosys; else Y=$Y38; fi
  for d in v1 v2; do
   for fl in plain opt; do
    if [ $fl = opt ]; then PRE="synth -top $d; dffunmap"; else PRE="proc; opt_clean; techmap; opt_clean"; fi
    for j in "${!SC[@]}"; do
      timeout 120 $Y -q -p "read_verilog rtl/$d.v; hierarchy -top $d; $PRE; ${SC[$j]}; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json ../x4/${d}_${fl}_${v}_s$j.json" >/dev/null 2>&1 || echo "FAIL $v $d $fl $j"
    done
   done
  done
done
