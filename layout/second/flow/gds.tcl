# patched (triage fixes): run with -rcfile sky130A.magicrc; flat extraction with PDN labels
set D $::env(DESIGN)
set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
lef read $PDK/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
lef read $PDK/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
def read out/$D.def
load $D
select top cell
gds write out/$D.gds
save out/$D.mag
drc euclidean on
drc style drc(full)
drc check
drc catchup
puts "DRC_TOTAL [drc listall count]"
foreach {why boxes} [drc listall why] { puts "RULE|[llength $boxes]|$why" ; foreach b $boxes {puts "  BOX $b"} }
source out/${D}_pinpaint.tcl
source out/${D}_pwrlabels.tcl
save out/$D.mag
gds write out/$D.gds
flatten ${D}_flat
load ${D}_flat
select top cell
extract all
ext2spice lvs
ext2spice -o out/${D}_ext.spice
quit
