read_db layout/v_designs/out_patched/v1_routed.odb
puts "== check_antennas v1"
set n [check_antennas -report_file ant/v1_ant.rpt]
puts "ANT_VIOLATING_NETS_RETURN $n"
set tech [[ord::get_db] getTech]
set blk [ord::get_db_block]
set mg [$tech getManufacturingGrid]
puts "mfg_grid_dbu $mg dbu_per_um [$tech getDbUnitsPerMicron]"
set bad 0; set n 0
foreach inst [$blk getInsts] { set l [$inst getLocation]; incr n; if {([lindex $l 0] % $mg) || ([lindex $l 1] % $mg)} {incr bad} }
puts "instances $n offgrid_origin $bad"
set bad 0; set n 0
foreach net [$blk getNets] {
  foreach sw [$net getSWires] { foreach b [$sw getWires] { incr n; foreach c [list [$b xMin] [$b yMin] [$b xMax] [$b yMax]] { if {$c % $mg} {incr bad} } } }
  set w [$net getWire]
  if {$w ne "NULL"} { set dec [odb::dbWireShapeItr]; $dec begin $w; set s [odb::dbShape]
    while {[$dec next $s]} { incr n; foreach c [list [$s xMin] [$s yMin] [$s xMax] [$s yMax]] { if {$c % $mg} {incr bad} } } }
}
puts "wire_shapes $n offgrid_coords $bad"
foreach p [$blk getBTerms] { foreach bp [$p getBPins] { foreach bx [$bp getBoxes] { incr np; foreach c [list [$bx xMin] [$bx yMin] [$bx xMax] [$bx yMax]] { if {$c % $mg} {incr badp} } } } }
puts "pin_boxes $np offgrid $badp"
exit
