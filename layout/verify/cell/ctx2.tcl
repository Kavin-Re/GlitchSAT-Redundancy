set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
load ctx
puts "CHILDREN [cellname list children ctx] BBOX [property FIXED_BBOX]"
drc euclidean on
drc style drc(full)
select top cell
puts "BB [box values]"
drc check
drc catchup
puts "CTX total=[drc listall count]"
foreach {why boxes} [drc listall why] { puts "CTXRULE|[llength $boxes]|$why" }
quit
