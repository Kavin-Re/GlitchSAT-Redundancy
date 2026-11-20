#!/bin/bash
# usage: runflow.sh tag netlist top
export UTIL=${UTIL:-60} PATH=/tmp/mm_root/envs/eda/bin:$PATH TAG=$1 NETF=$2 DESIGN=$3
cd /tmp/work_el2/lay
T0=$(date +%s.%N); timeout 300 openroad -no_splash -exit pnr_el2.tcl > out/$1_openroad.log 2>&1; echo "pnr_s $(echo "$(date +%s.%N)-$T0"|bc)" > out/$1_time.txt
