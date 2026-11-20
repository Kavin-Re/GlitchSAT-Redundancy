gds read out/ct_cmp.gds
load ct_cmp
select top cell
drc euclidean on
drc style drc(full)
drc check
drc catchup
puts "DRC_COUNT [drc list count]"
foreach {why boxes} [drc listall why] { puts "RULE|[llength $boxes]|$why" ; foreach b $boxes {puts "  BOX $b"} }
quit
