#!/bin/sh
# Same yosys script as scripts/synth.sh (plain flow) but with a chosen yosys binary.
# usage: synth_variants.sh <repo_root> <outdir>
R=$1; O=$2; mkdir -p $O
Y38=/tmp/mm_root/envs/formal/bin/yosys
for v in v0 v1 v2; do
 for tag in apt033:yosys conda038:$Y38; do
  n=${tag%%:*}; Y=${tag#*:}
  timeout 120 $Y -q -p "read_verilog $R/rtl/$v.v; hierarchy -top $v; proc; opt_clean; techmap; opt_clean; abc -g AND,OR,XOR,MUX; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json $O/${v}_$n.json" || echo FAIL $v $n
 done
done
