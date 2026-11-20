#!/bin/bash
D=$1
/tmp/mm_root/envs/eda/bin/netgen -batch lvs "out/${D}_ext.spice out/$D" "out/${D}_pnr.v $D" /tmp/mm_root/envs/eda/share/pdk/sky130A/libs.tech/netgen/sky130A_setup.tcl out/${D}_lvs.rpt
