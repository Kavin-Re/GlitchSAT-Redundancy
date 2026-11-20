#!/bin/sh
# usage: variants.sh <yosys-bin> <verilog> <top> <out.json> <variant>
# Mirrors /home/user/project/scripts/synth.sh but with variant knobs. base == synth.sh plain flow.
Y=$1; V=$2; T=$3; O=$4; VAR=$5
PRE="proc; opt_clean; techmap; opt_clean"; ABC="abc -g AND,OR,XOR,MUX"; POST="opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"
case $VAR in
 base) ;;
 abc_fast) ABC="abc -fast -g AND,OR,XOR,MUX";;
 abc_noMUX) ABC="abc -g AND,OR,XOR";;
 abc_AND_only) ABC="abc -g AND,OR";;
 noabc) ABC="";;
 opt_flow) PRE="synth -top $T; dffunmap";;
 opt_flow_fast) PRE="synth -top $T -run begin:fine; opt -fast; dffunmap";;
 post_opt_merge) POST="opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_merge; opt_clean";;
 post_opt_full) POST="opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt -full; opt_clean";;
 flatten_first) PRE="proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"; POST="opt_clean";;
 flatten_first_nomerge) PRE="proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean -purge; techmap; opt_clean"; POST="opt_clean";;
 flatten_first_fast) PRE="proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"; ABC="abc -fast -g AND,OR,XOR,MUX"; POST="opt_clean";;
 flatten_first_noabc) PRE="proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"; ABC=""; POST="opt_clean";;
 abc_dff) PRE="proc; opt_clean; techmap; opt_clean"; ABC="abc -dff -g AND,OR,XOR,MUX";;
 flatten_first_abc_dff) PRE="proc; setattr -mod -unset keep_hierarchy *; flatten; opt_clean; techmap; opt_clean"; ABC="abc -dff -g AND,OR,XOR,MUX"; POST="opt_clean";;
 *) echo "unknown variant $VAR" >&2; exit 2;;
esac
SCRIPT="read_verilog $V; hierarchy -top $T; $PRE; $ABC; $POST; write_json $O"
# Yosys >=0.4x splits -p on ',' too ('abc -g AND,OR' breaks on 0.52), so pass a script file (one command per line) for all builds.
printf '%s\n' "$SCRIPT" | sed 's/; */\n/g' > "$O.ys"
timeout 120 $Y -q -s "$O.ys"
