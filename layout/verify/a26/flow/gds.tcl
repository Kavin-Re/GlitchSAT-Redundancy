# patched: run with -rcfile sky130A.magicrc ; reads DEF (with PDN special nets + fillers), writes GDS, DRC, flat extract
set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
lef read $PDK/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
lef read $PDK/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
def read out/ct_cmp.def
load ct_cmp
select top cell
gds write out/ct_cmp.gds
save out/ct_cmp.mag
drc euclidean on
drc style drc(full)
drc check
drc catchup
puts "DRC_TOTAL [drc listall count]"
foreach {why boxes} [drc listall why] { puts "RULE|[llength $boxes]|$why" ; foreach b $boxes {puts "  BOX $b"} }
# flat extraction: all std-cell internals + PDN; VPWR/VGND come from labels in cells + DEF pins
source flow/pinpaint.tcl
# power labels on the met5 PDN stripes (DEF special nets carry no pin labels)
box 19.5um 23.6um 20.5um 24.2um
label VGND FreeSans 0.25u 0 0 0 c metal5
port make
box 19.5um 33.6um 20.5um 34.2um
label VPWR FreeSans 0.25u 0 0 0 c metal5
port make
save out/ct_cmp.mag
gds write out/ct_cmp.gds
flatten ct_cmp_flat
load ct_cmp_flat
select top cell
extract all
ext2spice lvs
ext2spice -o out/ct_cmp_ext.spice
quit
