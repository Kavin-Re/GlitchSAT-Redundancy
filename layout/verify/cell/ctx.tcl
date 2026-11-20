set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
load ctx
drc euclidean on
drc style drc(full)
proc put {c x} { box position ${x}um 0um; set r [getcell $c]; puts "PUT $c $x -> $r" }
put sky130_fd_sc_hd__tapvpwrvgnd_1 0
put sky130_fd_sc_hd__dfxtp_1 0.46
put sky130_fd_sc_hd__tapvpwrvgnd_1 7.82
puts "CHILDREN [cellname list children ctx]"
select top cell
drc check
drc catchup
puts "CTX total=[drc listall count]"
foreach {why boxes} [drc listall why] { puts "CTXRULE|[llength $boxes]|$why" }
save ctx
quit
