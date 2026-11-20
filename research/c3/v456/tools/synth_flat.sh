#!/bin/sh
# usage: synth_flat.sh <yosys> <verilog> <top> <out.json>   (AGGRESSIVE: flatten BEFORE opt/abc, opt_merge shares identical cells; keep_hierarchy ignored)
$1 -q -p "read_verilog $2; hierarchy -top $3; setattr -mod -unset keep_hierarchy *; synth -flatten -top $3; dffunmap; abc -g AND,OR,XOR,MUX; opt_clean; techmap; opt_clean; write_json $4"
