create_clock -name clk -period 10 [get_ports clk]
set ins [lsearch -inline -all -not -exact [get_ports *] [get_ports clk]]
set_input_delay 2 -clock clk [get_ports {rst_n en clr_fault a* b*}]
set_output_delay 2 -clock clk [all_outputs]
