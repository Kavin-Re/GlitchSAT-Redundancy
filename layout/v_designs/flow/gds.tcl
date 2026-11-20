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
drc listall why
extract all
ext2spice lvs
ext2spice -o out/${D}_ext.spice
quit
