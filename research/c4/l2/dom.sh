#!/bin/bash
# usage: dom.sh VAR  -> runs LAYOUT scripts on out_VAR in lay/VAR
V=$1; mkdir -p /tmp/work_l2/lay/$V; cd /tmp/work_l2/lay/$V; cp /tmp/work_l2/lay/code/*.py .
export L2OUT=/tmp/work_l2/out_$V
cp $L2OUT/v2.def $L2OUT/v2_pnr.v .
timeout 120 python3 layout_extract.py v2 > extract.log 2>&1
timeout 300 python3 geom_report.py v2 > geom.log 2>&1
timeout 300 python3 -c "
import simcheck as s
a=s.load('/home/user/project/research/c4/layout/nl/v2_layout.json','v2'); b=s.load('nl/v2_layout.json','v2')
bad=[x for x in range(256) if s.sim(a,x)!=s.sim(b,x)]
print('sig values with different 5-cycle trace, original-layout netlist vs this layout netlist:',len(bad),'of 256')" > sim.log 2>&1
timeout 900 python3 minsets.py v2 4 > minsets.log 2>&1
timeout 1500 python3 radius_sweep.py v2 > sweep.log 2>&1
echo done > DONE
