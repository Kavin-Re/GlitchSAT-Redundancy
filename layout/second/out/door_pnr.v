module door (clk,
    ena,
    rst_n,
    ui_in,
    uio_in,
    uio_oe,
    uio_out,
    uo_out);
 input clk;
 input ena;
 input rst_n;
 input [7:0] ui_in;
 input [7:0] uio_in;
 output [7:0] uio_oe;
 output [7:0] uio_out;
 output [7:0] uo_out;


 sky130_fd_sc_hd__nor4bb_1 _0_ (.A(ui_in[0]),
    .B(ui_in[2]),
    .C_N(ui_in[3]),
    .D_N(ui_in[1]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(uo_out[0]));
 sky130_fd_sc_hd__nand4bb_1 _1_ (.A_N(ui_in[0]),
    .B_N(ui_in[2]),
    .C(ui_in[3]),
    .D(ui_in[1]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(uo_out[1]));
 sky130_fd_sc_hd__conb_1 _2_ (.VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .LO(uio_oe[7]));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_0 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_1 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_2 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__fill_8 FILLER_0_0 ();
 sky130_fd_sc_hd__fill_8 FILLER_0_8 ();
 sky130_fd_sc_hd__fill_4 FILLER_0_16 ();
 sky130_fd_sc_hd__fill_1 FILLER_0_20 ();
 sky130_fd_sc_hd__fill_8 FILLER_0_22 ();
 sky130_fd_sc_hd__decap_3 FILLER_0_30 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_0 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_8 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_19 ();
 sky130_fd_sc_hd__fill_4 FILLER_1_27 ();
 sky130_fd_sc_hd__fill_2 FILLER_1_31 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_0 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_8 ();
 sky130_fd_sc_hd__fill_4 FILLER_2_16 ();
 sky130_fd_sc_hd__fill_1 FILLER_2_20 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_22 ();
 sky130_fd_sc_hd__decap_3 FILLER_2_30 ();
 sky130_fd_sc_hd__fill_1 FILLER_3_0 ();
 sky130_fd_sc_hd__decap_3 FILLER_3_18 ();
 sky130_fd_sc_hd__fill_8 FILLER_3_22 ();
 sky130_fd_sc_hd__decap_3 FILLER_3_30 ();
 assign uio_oe[0] = uio_oe[7];
 assign uio_oe[1] = uio_oe[7];
 assign uio_oe[2] = uio_oe[7];
 assign uio_oe[3] = uio_oe[7];
 assign uio_oe[4] = uio_oe[7];
 assign uio_oe[5] = uio_oe[7];
 assign uio_oe[6] = uio_oe[7];
 assign uio_out[0] = uio_oe[7];
 assign uio_out[1] = uio_oe[7];
 assign uio_out[2] = uio_oe[7];
 assign uio_out[3] = uio_oe[7];
 assign uio_out[4] = uio_oe[7];
 assign uio_out[5] = uio_oe[7];
 assign uio_out[6] = uio_oe[7];
 assign uio_out[7] = uio_oe[7];
 assign uo_out[2] = uio_oe[7];
 assign uo_out[3] = uio_oe[7];
 assign uo_out[4] = uio_oe[7];
 assign uo_out[5] = uio_oe[7];
 assign uo_out[6] = uio_oe[7];
 assign uo_out[7] = uio_oe[7];
endmodule
