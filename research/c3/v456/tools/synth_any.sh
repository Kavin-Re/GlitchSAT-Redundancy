#!/bin/sh
# usage: synth_any.sh <yosys-binary> <verilog> <top> <out.json> [plain|opt]  (copy of scripts/synth.sh with selectable yosys)
Y=$1; FLOW=${5:-plain}
if [ "$FLOW" = opt ]; then PRE="synth -top $3; dffunmap"; else PRE="proc; opt_clean; techmap; opt_clean"; fi
$Y -q -p "read_verilog $2; hierarchy -top $3; $PRE; abc -g AND,OR,XOR,MUX; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json $4"
