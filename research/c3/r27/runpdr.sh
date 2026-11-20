#!/bin/sh
# usage: runpdr.sh tag netlist top K gport gval key aport style timeout
export PATH=/tmp/mm_root/envs/formal/bin:$PATH
cd /tmp/work_r27/pdr
tag=$1; python3 gen2.py $2 $3 $4 fi_$tag.sv $5 $6 $7 $8 $9 >/dev/null || exit 1
printf "[options]\nmode prove\n[engines]\nabc pdr\n[script]\nread_verilog -formal fi_$tag.sv\nprep -top fi_$3\n[files]\nfi_$tag.sv\n" > $tag.sby
rm -rf $tag; s=$(date +%s.%N)
timeout ${10} sby -f $tag.sby > $tag.log 2>&1; rc=$?
e=$(date +%s.%N)
st=$(grep -o "DONE ([A-Z]*" $tag.log | head -1); [ $rc = 124 ] && st="TIMEOUT"
echo "{\"tag\":\"$tag\",\"status\":\"$st\",\"wall_s\":$(echo "$e - $s" | bc)}"
