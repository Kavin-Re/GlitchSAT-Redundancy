#!/bin/bash
D=$1
/tmp/mm_root/envs/eda/bin/netgen -batch lvs "out_patched/${D}_ext.spice ${D}_flat" "out_patched/${D}_ref.spice $D" /tmp/mm_root/envs/eda/share/pdk/sky130A/libs.tech/netgen/sky130A_setup.tcl out_patched/${D}_lvs.rpt
