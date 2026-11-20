set PDK /tmp/mm_root/envs/eda/share/pdk/sky130A
gds read $PDK/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds
drc euclidean on
drc style drc(full)
foreach C $::env(CELLS) {
  load $C
  select top cell
  drc check
  drc catchup
  set s {}
  foreach {why boxes} [drc listall why] { lappend s "[llength $boxes]x[regsub {.*\((.*)\)$} $why {\1}]" }
  puts "CELL $C $s"
}
# context test: tap + dfxtp_1 + tap, abutted
load ctx
box 0 0 0 0
set a [getcell sky130_fd_sc_hd__tapvpwrvgnd_1 0 0]
select cell [lindex [instance list children] 0]
puts "CTXLIST [cellname list children ctx]"
quit
