#!/bin/sh
# usage: run_bmc.sh design k [mode=bmc|prove] [engine line]   (run from formal/, PATH must have the formal env)
D=$1; K=$2; MODE=${3:-bmc}; ENG=${4:-smtbmc boolector}; DEPTH=${DEPTH:-6}
mkdir -p gen runs
python3 src/gen_wrapper.py gen/$D.json $D $K gen/fi_${D}_k$K.sv >/dev/null
TAG=${D}_k${K}_${MODE}_$(echo $ENG | tr ' ' '_')
cat > runs/$TAG.sby <<EOT
[tasks]
x
[options]
mode $MODE
depth $DEPTH
[engines]
$ENG
[script]
read_verilog -formal fi_${D}_k$K.sv
prep -top fi_$D
[files]
gen/fi_${D}_k$K.sv
EOT
rm -rf runs/$TAG
S=$(date +%s.%N); sby -f runs/$TAG.sby 2>&1 | tail -12; E=$(date +%s.%N); echo "wall_s=$(echo "$E - $S" | bc 2>/dev/null || python3 -c "print($E-$S)")"
