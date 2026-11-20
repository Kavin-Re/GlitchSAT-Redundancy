read_db ../../triage/out/routed.odb
set blk [ord::get_db_block]
foreach n {FILLER_0_40 FILLER_0_67 FILLER_1_13 FILLER_1_65 FILLER_2_10 FILLER_3_30 FILLER_3_34 FILLER_4_32} { odb::dbInst_destroy [$blk findInst $n] }
write_def out/ct_cmp.def
write_verilog -include_pwr_gnd out/ct_cmp_pnr.v
exit
