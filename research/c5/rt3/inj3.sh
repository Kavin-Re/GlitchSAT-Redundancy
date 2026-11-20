#!/bin/bash
W=/tmp/work_rt3/t; C=/tmp/work_rt3; P=$C/p; cd $W; rm -f canary_* $C/canary_*
GS="python3 $P/scripts/glitchsat.py check --goal-out unlock --goal-value 1 --attack-input code --key 10"
chk(){ n=$(ls $C/canary_* $W/canary_* 2>/dev/null | wc -l); echo "[$1] rc=$2 canaries=$n"; rm -f $C/canary_* $W/canary_*; }
run(){ l=$1; shift; timeout 90 "$@" >out.txt 2>&1; rc=$?; chk "$l" $rc; head -c 160 out.txt|head -1|sed 's/^/     /'; }
echo "--- baseline"; run base $GS pin.v --top pin --k 1 --cycles 4
TOPS=("pin; exec -- touch canary_t1" $'pin\nexec -- touch canary_t2' 'pin$(touch canary_t3)' 'pin`touch canary_t4`' "pin " "pіn" 'pin\' '\pin ' 'pin;' "$(printf 'a%.0s' {1..300})" "-s")
i=0; for t in "${TOPS[@]}"; do i=$((i+1)); run "gs top#$i" $GS pin.v --top "$t" --k 1 --cycles 4; done
FN=("m.v; exec -- touch canary_f1; .v" 'm$(touch canary_f3).v' 'm`touch canary_f4`.v' "p'in.v" "pin#x.v" "my file.v" $'pin\r.v' 'pin"x.v')
i=0; for f in "${FN[@]}"; do i=$((i+1)); cp pin.v "./$f"; run "gs fn#$i" $GS "./$f" --top pin --k 1 --cycles 4; rm -f "./$f"; done
OUTS=("o; exec -- touch canary_o1.json" 'o$(touch canary_o3).json' 'o`touch canary_o4`.json' $'o\nexec -- touch canary_o2' 'o"x.json' "-o.json")
i=0; for o in "${OUTS[@]}"; do i=$((i+1)); run "gs out#$i" $GS pin.v --top pin --k 1 --cycles 4 --out "$o"; rm -f ./o*.json; done
python3 $P/scripts/glitchsat.py check --help | tail -15
