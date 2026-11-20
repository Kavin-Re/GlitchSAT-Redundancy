read_verilog rtl/@D@.v
hierarchy -top @D@
synth -top @D@
dfflibmap -liberty @LIB@
abc -dont_use *lpflow* -dont_use *probe* -liberty @LIB@
hilomap -singleton -hicell sky130_fd_sc_hd__conb_1 HI -locell sky130_fd_sc_hd__conb_1 LO
opt_clean -purge
tee -o out_patched/@D@_stat.txt stat -liberty @LIB@
write_verilog -noattr -noexpr -nohex -nodec out_patched/@D@_net.v
