#!/bin/sh
# same as scripts/synth.sh but with chosen yosys binary: Y=<bin>
Y=${Y:-yosys}
FLOW=${4:-plain}
if [ "$FLOW" = opt ]; then PRE="synth -top $2; dffunmap"; else PRE="proc; opt_clean; techmap; opt_clean"; fi
$Y -q -p "read_verilog $1; hierarchy -top $2; $PRE; abc -g AND,OR,XOR,MUX; opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean; write_json $3"
