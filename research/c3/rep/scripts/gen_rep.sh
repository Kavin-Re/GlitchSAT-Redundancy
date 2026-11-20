#!/bin/bash
# REP: independent generator of the 2 designs x 2 yosys x 2 flows x 8 ABC variants (64 netlists)
cd /tmp/work_rep
Y33=yosys; Y38=/tmp/mm_root/envs/formal/bin/yosys
ABC=("abc -g AND,OR,XOR,MUX" "abc -g AND,OR,XOR" "abc -fast -g AND,OR,XOR,MUX" "abc -fast -g AND,OR,XOR" "abc -g AND,OR" "abc -g AND,OR,MUX" "abc -script +strash;dc2;map -g AND,OR,XOR" "abc -g AND,OR,XOR,MUX -D 1000")
for ver in 033 038; do
 if [ $ver = 033 ]; then Y=$Y33; else Y=$Y38; fi
 for d in v1 v2; do for fl in plain opt; do
  if [ $fl = opt ]; then PRE="synth -top $d; dffunmap"; else PRE="proc; opt_clean; techmap; opt_clean"; fi
  for i in 0 1 2 3 4 5 6 7; do
   timeout 120 $Y -q -p "read_verilog rtl/$d.v; hierarchy -top $d; $PRE; ${ABC[$i]}; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json net/${d}_${fl}_${ver}_s$i.json" >/dev/null 2>&1 || echo "FAIL $ver $d $fl $i"
  done; done; done; done
ls net | wc -l
