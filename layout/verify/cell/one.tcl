set C $::env(CELL); set MODE $::env(MODE); set STYLE $::env(STYLE)
set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
if {$MODE eq "gds"} {
  gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
  load $C
} else {
  addpath $PDK/libs.ref/sky130_fd_sc_hd/mag
  load $PDK/libs.ref/sky130_fd_sc_hd/mag/$C.mag
}
select top cell
drc euclidean on
drc style $STYLE
drc check
drc catchup
puts "RES $C $MODE $STYLE total=[drc listall count]"
foreach {why boxes} [drc listall why] { puts "RULE|[llength $boxes]|$why" }
quit
