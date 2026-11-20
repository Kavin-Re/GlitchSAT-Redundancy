#!/bin/sh
# independent yosys flow (different from spike): no keep_hierarchy, flatten, legalize flops, abc to AND/OR/XOR/MUX
for v in v0 v1 v2; do yosys -q -p "read_verilog -sv nl/boot_flat.v; hierarchy -top $v; synth -flatten -top $v; dffunmap; abc -g AND,OR,XOR,MUX; opt_clean -purge; write_json nl/$v.json"; done
