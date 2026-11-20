set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
lef read $PDK/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
lef read $PDK/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
def read ../../triage/out/ct_cmp.def
load ct_cmp
source ../../triage/flow/pinpaint.tcl
flatten ct_cmp_flat
load ct_cmp_flat
select top cell
extract all
extract warn all
puts "EXTRACT_DONE"
quit
