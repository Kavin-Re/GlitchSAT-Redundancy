set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
load ctx
drc euclidean on
drc style drc(full)
flatten ctxflat
load ctxflat
select top cell
drc check
drc catchup
puts "FLAT total=[drc listall count]"
foreach {why boxes} [drc listall why] { puts "FLATRULE|[llength $boxes]|$why" }
# also single cell alone, flattened
load sky130_fd_sc_hd__dfxtp_1
select top cell
drc check
drc catchup
puts "ALONE total=[drc listall count]"
foreach {why boxes} [drc listall why] { puts "ALONERULE|[llength $boxes]|$why" }
quit
