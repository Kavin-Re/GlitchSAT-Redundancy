#!/bin/bash
FB=/tmp/work_rt3/venv/bin/faultbound-wt
W=/tmp/work_rt3/t; C=/tmp/work_rt3; P=$C/p
cd $W; rm -f canary_* $C/canary_*
chk(){ n=$(ls $C/canary_* $W/canary_* 2>/dev/null | wc -l); echo "[$1] rc=$2 canaries=$n"; rm -f $C/canary_* $W/canary_*; }
run(){ l=$1; shift; timeout 60 "$@" >out.txt 2>&1; rc=$?; chk "$l" $rc; head -c 160 out.txt|head -1|sed 's/^/     /'; }
FN=("m.v; exec -- touch canary_f1; .v" "m"$'\n'"exec -- touch canary_f2.v" 'm$(touch canary_f3).v' 'm`touch canary_f4`.v' "p'in.v" "pіn.v" "pin.v " "$(printf 'a%.0s' {1..300}).v" '${HOME}.v' '\pin.v' "pin#x.v" "my file.v" $'pin\r.v' $'pin\t.v' "pin%s.v" "pin\$HOME.v" "pin,x.v" "pin!x.v" 'pin"x.v' $'pin\xe2\x80\xae.v' "pin*.v" "pin?.v" "pin[1].v" "pin{a}.v")
i=0
for f in "${FN[@]}"; do i=$((i+1))
  cp pin.v "./$f" 2>/dev/null || { echo "[fn#$i] cannot create"; continue; }
  run "product fn#$i" $FB analyze "./$f" --config pin.toml --top pin
  run "synth.sh fn#$i" sh $P/scripts/synth.sh "./$f" pin o.json
  run "yosys_flow fn#$i" bash $P/product/scripts/yosys_flow.sh "./$f" pin o2.json
  run "glitchsat check fn#$i" python3 $P/scripts/glitchsat.py check "./$f" --top pin
  rm -f "./$f"
done
echo --- output names
OUTS=("o; exec -- touch canary_o1.json" $'o\nexec -- touch canary_o2' 'o$(touch canary_o3).json' 'o`touch canary_o4`.json' "-o.json" 'o"x.json' "o x.json" "o#.json" 'o\x.json')
i=0
for o in "${OUTS[@]}"; do i=$((i+1))
  run "synth.sh out#$i" sh $P/scripts/synth.sh pin.v pin "$o"
  run "yosys_flow out#$i" bash $P/product/scripts/yosys_flow.sh pin.v pin "$o"
  rm -f ./o*.json 2>/dev/null
done
echo --- tops via scripts
TOPS=("pin; exec -- touch canary_t1" $'pin\nexec -- touch canary_t2' 'pin$(touch canary_t3)' 'pin`touch canary_t4`' "-s" "--top" "pin " "pіn" 'pin\' '\pin ' "" 'pin;' 'pin # c' 'pin$' '$pin' 'pin.x' 'pin\x' "$(printf 'a%.0s' {1..300})")
i=0
for t in "${TOPS[@]}"; do i=$((i+1))
  run "synth.sh top#$i" sh $P/scripts/synth.sh pin.v "$t" o.json
  run "yosys_flow top#$i" bash $P/product/scripts/yosys_flow.sh pin.v "$t" o2.json
  run "glitchsat check top#$i" python3 $P/scripts/glitchsat.py check pin.v --top "$t"
done
echo --- glitchsat other args
run "gs check out/arg" python3 $P/scripts/glitchsat.py check pin.v --top pin --flow "plain; exec -- touch canary_g1"
python3 $P/scripts/glitchsat.py check --help 2>&1 | head -20
