#!/bin/bash
# run from layout/triage
export PATH=/tmp/mm_root/envs/eda/bin:$PATH
netgen -batch lvs "out/ct_cmp_ext.spice ct_cmp_flat" "out/ct_cmp_ref.spice ct_cmp" /tmp/mm_root/envs/eda/share/pdk/sky130A/libs.tech/netgen/sky130A_setup.tcl out/lvs.rpt
