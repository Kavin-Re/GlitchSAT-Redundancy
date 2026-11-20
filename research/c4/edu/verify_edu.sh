#!/bin/bash
# Runs every command used in docs/edu/ on the COPY /tmp/work_edu and logs command, key output lines, exit code.
cd /tmp/work_edu || exit 3
. .v/bin/activate
mkdir -p edu_work
LOG=/tmp/work_edu/verification.log
: > "$LOG"
echo "# verification.log. Run $(date -u +%FT%TZ) in a COPY of the project at /tmp/work_edu (never in the tree)." >> "$LOG"
echo "# yosys: $(yosys -V 2>&1|head -1); python: $(python3 -V); z3-solver: $(python3 -c 'import z3;print(z3.get_version_string())'); faultbound-wt: $(faultbound-wt --version 2>&1)" >> "$LOG"
echo "# Output is filtered to the verdict line, minimum attack, netlist sha line and exit code; label of every number: MEASURED (this log)." >> "$LOG"
REF=reference/spike_netlists; D=docs/edu/starter_designs; T=docs/edu/tools; W=edu_work
run() { echo "" >> "$LOG"; echo "\$ $*" >> "$LOG"; local s=$(date +%s.%N)
  timeout 300 bash -c "$*" > $W/last.txt 2>&1; local rc=$?
  grep -E '^(v[0-9]|mini[0-9]|pin[a-z]*): |minimum attack|MINIMUM ATTACK|scope: netlist|CONFIGURATION|CONFIG|error:|^yosys:|^netlist|^mask|^min_cost|^flips|^flip net|bounds:' $W/last.txt | cut -c1-260 >> "$LOG"
  echo "[exit code $rc; $(printf '%.1f' $(echo "$(date +%s.%N)-$s"|bc)) s]" >> "$LOG"; }
echo "## Exercise 1: V0/V1/V2 stored netlists, bundled threat.toml"
EX="$(faultbound-wt example-path)"
for d in v0 v1 v2; do for k in 1 2 3; do run "faultbound-wt analyze $REF/$d.json --top $d --config product/src/faultbound_wt/examples/threat.toml --max-flips $k"; done; done
echo "## Exercise 2: consumer mask"
for m in 0xFF 0x0F 0x1B 0x4E; do run "python3 $T/edu_scope.py $REF/v2.json v2 --mask $m"; done
run "python3 $T/edu_scope.py $REF/v1.json v1 --mask 0x0F"
run "python3 $T/edu_scope.py $REF/v0.json v0 --mask 0x0F"
echo "## Exercise 3: re-synthesis and opt_merge"
run "product/scripts/yosys_flow.sh rtl/v2.v v2 $W/v2_plain.json"
run "$T/synth_merge.sh rtl/v2.v v2 $W/v2_merge.json"
for f in plain merge; do for k in 1 2; do run "faultbound-wt analyze $W/v2_$f.json --top v2 --config product/src/faultbound_wt/examples/threat.toml --max-flips $k"; done; done
echo "## Exercise 4: stem vs fanout"
run "python3 $T/edu_scope.py $W/v2_plain.json v2 --rule unit"
run "python3 $T/edu_scope.py $W/v2_plain.json v2 --rule fanout"
run "python3 $T/edu_scope.py $REF/v2.json v2 --rule unit"
run "python3 $T/edu_scope.py $REF/v2.json v2 --rule fanout"
run "python3 $T/edu_scope.py $W/v2_merge.json v2 --rule fanout"
echo "## Exercise 5: starters and design a variant"
for n in 0 1 2; do for k in 1 2; do run "faultbound-wt analyze $D/mini_v$n.json --top mini$n --config $D/mini.toml --max-flips $k"; done; done
run "faultbound-wt analyze $D/mini_v2.v --top mini2 --config $D/mini.toml --max-flips 1"
run "$T/synth_merge.sh $D/mini_v2.v mini2 $W/mini2_merge.json"
run "faultbound-wt analyze $W/mini2_merge.json --top mini2 --config $D/mini.toml --max-flips 1"
echo "## Exercise 6: asset and configuration"
run "faultbound-wt analyze $REF/v2.json --top v2 --config $D/v2_bootok.toml --max-flips 1"
run "faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini_bootok.toml --max-flips 1"
sed 's/legitimate_value = 5/legitimate_value = 7/' $D/mini.toml > $W/bad.toml
run "faultbound-wt analyze $D/mini_v2.json --top mini2 --config $W/bad.toml --max-flips 1"
run "faultbound-wt analyze product/examples/pin_lock/pin.v --top pin --config product/examples/pin_lock/pin.toml"
run "faultbound-wt analyze product/examples/pin_lock/pin_async.v --top pina --config product/examples/pin_lock/pin.toml"
echo "## starter netlist regeneration (hashes must equal the committed ones)"
for n in 0 1 2; do run "product/scripts/yosys_flow.sh $D/mini_v$n.v mini$n $W/regen_mini$n.json"; cmp $D/mini_v$n.json $W/regen_mini$n.json && echo "mini_v$n.json identical on regeneration" >> "$LOG"; done
sha256sum $D/*.json $D/*.v >> "$LOG"
echo done
