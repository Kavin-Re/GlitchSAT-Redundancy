#!/bin/bash
# Runs every command of docs/edu/ (shipped CLI version) in the COPY /tmp/work_edu2/p. Never in the tree.
cd /tmp/work_edu2/p || exit 3
. /tmp/work_edu2/venv/bin/activate
mkdir -p edu_work
LOG=${LOG:-/tmp/work_edu2/verification.log}
: > "$LOG"
echo "# verification.log. Run $(date -u +%FT%TZ) in a COPY at /tmp/work_edu2/p, fresh venv pip install ./product[test]." >> "$LOG"
echo "# yosys: $(yosys -V 2>&1|head -1); python: $(python3 -V); z3-solver: $(python3 -c 'import z3;print(z3.get_version_string())'); faultbound-wt: $(faultbound-wt --version 2>&1)" >> "$LOG"
echo "# Output filtered to verdict, MINIMUM ATTACK COST, scope lines, sweep table, exit code. Label of every number: MEASURED (this log)." >> "$LOG"
REF=reference/spike_netlists; D=docs/edu/starter_designs; T=docs/edu/tools; W=edu_work
CFG=product/src/faultbound_wt/examples/threat.toml
run() { echo "" >> "$LOG"; echo "\$ $*" >> "$LOG"; local s=$(date +%s.%N)
  timeout 400 bash -c "$*" > $W/last.txt 2>&1; local rc=$?
  grep -E '^(v[0-9]|mini[0-9]|pin[a-z]*): |minimum attack|MINIMUM ATTACK|scope: netlist|CONFIGURATION|error:|^yosys:|^netlist|^min_cost|^flips|^flip net|^mask|^ *(goal|word|bits|boot|n[ =]|width)|^[-+| ]*(goal|row)|^ *[0-9]+ +[0-9>un<=]|\|' $W/last.txt | cut -c1-240 >> "$LOG"
  echo "[exit code $rc; $(printf '%.1f' $(echo "$(date +%s.%N)-$s"|bc)) s]" >> "$LOG"; }
echo "## Ex1"
for d in v0 v1 v2; do for k in 1 2 3; do run "faultbound-wt analyze $REF/$d.json --top $d --config $CFG --max-flips $k"; done; done
echo "## Ex2 (CLI --consumer-bits, k<=3)"
for m in 0xFF 0x0F 0x1B 0x4E; do run "faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --consumer-bits $m"; done
run "faultbound-wt analyze $REF/v1.json --top v1 --config $CFG --max-flips 3 --consumer-bits 0x0F"
echo "## Ex2 exact worksheet loop"
run 'REF=reference/spike_netlists; CFG=product/src/faultbound_wt/examples/threat.toml; for m in 0xFF 0x0F 0x1B 0x4E; do echo "mask $m"; faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --consumer-bits $m | grep -E "minimum attack|MINIMUM"| cut -c1-150; done'
echo "## Ex3"
run "product/scripts/yosys_flow.sh rtl/v2.v v2 $W/v2_plain.json"
run "$T/synth_merge.sh rtl/v2.v v2 $W/v2_merge.json"
for f in plain merge; do for k in 1 2; do run "faultbound-wt analyze $W/v2_$f.json --top v2 --config $CFG --max-flips $k"; done; done
echo "## Ex4 (edu_scope.py = research wrapper, fanout rule not in product; unit rule cross-checked with CLI)"
run "python3 $T/edu_scope.py $W/v2_plain.json v2 --rule unit"
run "python3 $T/edu_scope.py $W/v2_plain.json v2 --rule fanout"
run "python3 $T/edu_scope.py $W/v2_merge.json v2 --rule fanout"
run "python3 $T/edu_scope.py $REF/v2.json v2 --rule unit"
run "python3 $T/edu_scope.py $REF/v2.json v2 --rule fanout"
run "faultbound-wt analyze $W/v2_plain.json --top v2 --config $CFG --max-flips 2"
echo "## Ex5"
run "faultbound-wt analyze $D/mini_v1.json --top mini1 --config $D/mini.toml --max-flips 1"
for k in 1 2; do run "faultbound-wt analyze $D/mini_v2.v --top mini2 --config $D/mini.toml --max-flips $k"; done
run "$T/synth_merge.sh $D/mini_v2.v mini2 $W/mini2_merge.json"
run "faultbound-wt analyze $W/mini2_merge.json --top mini2 --config $D/mini.toml --max-flips 1"
echo "## Ex6"
run "faultbound-wt analyze $REF/v2.json --top v2 --config $D/v2_bootok.toml --max-flips 1"
run "faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini_bootok.toml --max-flips 1"
sed 's/legitimate_value = 5/legitimate_value = 7/' $D/mini.toml > $W/bad.toml
run "faultbound-wt analyze $D/mini_v2.json --top mini2 --config $W/bad.toml --max-flips 1"
echo "## Ex7 sweep-widths"
run "faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --sweep-widths --sweep-out $W/widths_v2.csv"
echo "\$ cat $W/widths_v2.csv" >> "$LOG"; cat $W/widths_v2.csv >> "$LOG"
run "faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini.toml --max-flips 3 --sweep-widths --sweep-out $W/widths_mini2.csv"
echo "\$ cat $W/widths_mini2.csv" >> "$LOG"; cat $W/widths_mini2.csv >> "$LOG"
run "faultbound-wt analyze $REF/v1.json --top v1 --config $CFG --max-flips 3 --sweep-widths"
echo "## Ex8 scope-sweep"
run "faultbound-wt analyze $REF/v2.json --top v2 --config $CFG --max-flips 3 --scope-sweep --sweep-masks 0x0F --cell-timeout-ms 120000 --sweep-out $W/sweep_v2.csv"
echo "\$ cat $W/sweep_v2.csv" >> "$LOG"; cat $W/sweep_v2.csv >> "$LOG"
run "faultbound-wt analyze $D/mini_v2.json --top mini2 --config $D/mini.toml --max-flips 3 --scope-sweep --cell-timeout-ms 60000"
echo done
