# OpenSTA script: build a TRUE SDF (and per-flop path-delay report) for a placed V1/V2 netlist, so the
# virtual glitch lab can run with SOURCED timing instead of the ASSUMED linear model.
#
# Run via eda/regen_sdf.sh (which sets DESIGN, NETLIST, LIB, SDF). Needs OpenSTA (or `sta` inside
# OpenROAD) and the sky130_fd_sc_hd liberty from the PDK -- neither ships in the repo.
read_liberty $env(LIB)
read_verilog $env(NETLIST)
link_design $env(DESIGN)
# single clock on the clk port; period is irrelevant to the IOPATH cell delays we export
create_clock -name clk -period 10 [get_ports clk]
set_propagated_clock [all_clocks]
# worst-corner data delays
report_checks -path_delay max -fields {slew cap input nets fanout} -format full_clock > $env(REPORT)
# per-endpoint (flop D) arrival, the number the lab's static-timing model needs
report_checks -path_delay max -group_count 64 -endpoint_count 64 -fields {input} >> $env(REPORT)
write_sdf -divider / $env(SDF)
puts "wrote $env(SDF) and $env(REPORT)"
exit
