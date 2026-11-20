module v2 (boot_ok,
    clk,
    boot_word,
    sig);
 output boot_ok;
 input clk;
 output [7:0] boot_word;
 input [7:0] sig;

 wire _00_;
 wire _01_;
 wire _02_;
 wire _03_;
 wire _04_;
 wire _05_;
 wire _06_;
 wire _07_;
 wire _08_;
 wire _09_;
 wire _10_;
 wire _11_;
 wire _12_;
 wire _13_;
 wire _14_;
 wire _15_;
 wire m0;
 wire m1;
 wire m2;
 wire \c0/_0_ ;
 wire \c0/_1_ ;
 wire \c1/_0_ ;
 wire \c1/_1_ ;
 wire \c2/_0_ ;
 wire \c2/_1_ ;
 wire clknet_0_clk;
 wire clknet_1_0__leaf_clk;
 wire clknet_1_1__leaf_clk;
 wire [6:0] word;

 sky130_fd_sc_hd__inv_1 _16_ (.A(m2),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(word[5]));
 sky130_fd_sc_hd__inv_1 _17_ (.A(m0),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(word[6]));
 sky130_fd_sc_hd__nand2_1 _18_ (.A(boot_word[4]),
    .B(boot_word[7]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_08_));
 sky130_fd_sc_hd__nand4bb_1 _19_ (.A_N(boot_word[0]),
    .B_N(boot_word[3]),
    .C(boot_word[2]),
    .D(boot_word[1]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_09_));
 sky130_fd_sc_hd__nor4_1 _20_ (.A(boot_word[5]),
    .B(boot_word[6]),
    .C(_08_),
    .D(_09_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(boot_ok));
 sky130_fd_sc_hd__nor4bb_1 _21_ (.A(boot_word[0]),
    .B(boot_word[1]),
    .C_N(boot_word[7]),
    .D_N(boot_word[6]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_10_));
 sky130_fd_sc_hd__nor2_1 _22_ (.A(boot_word[5]),
    .B(boot_word[4]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_11_));
 sky130_fd_sc_hd__and4_2 _23_ (.A(boot_word[3]),
    .B(boot_word[2]),
    .C(_10_),
    .D(_11_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_12_));
 sky130_fd_sc_hd__a21o_1 _24_ (.A1(word[6]),
    .A2(_12_),
    .B1(boot_word[0]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_00_));
 sky130_fd_sc_hd__a21o_1 _25_ (.A1(m1),
    .A2(_12_),
    .B1(boot_word[1]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_01_));
 sky130_fd_sc_hd__nor2_1 _26_ (.A(boot_word[3]),
    .B(boot_word[2]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_13_));
 sky130_fd_sc_hd__and4_1 _27_ (.A(boot_word[5]),
    .B(boot_word[4]),
    .C(_10_),
    .D(_13_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_14_));
 sky130_fd_sc_hd__nand4_1 _28_ (.A(boot_word[5]),
    .B(boot_word[4]),
    .C(_10_),
    .D(_13_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_15_));
 sky130_fd_sc_hd__a2bb2oi_1 _29_ (.A1_N(boot_word[2]),
    .A2_N(_14_),
    .B1(_12_),
    .B2(word[5]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_02_));
 sky130_fd_sc_hd__a2bb2oi_1 _30_ (.A1_N(boot_word[3]),
    .A2_N(_14_),
    .B1(_12_),
    .B2(m0),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_03_));
 sky130_fd_sc_hd__a22o_1 _31_ (.A1(m1),
    .A2(_12_),
    .B1(_15_),
    .B2(boot_word[4]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_04_));
 sky130_fd_sc_hd__a22o_1 _32_ (.A1(word[5]),
    .A2(_12_),
    .B1(_15_),
    .B2(boot_word[5]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_05_));
 sky130_fd_sc_hd__a21boi_0 _33_ (.A1(m0),
    .A2(_12_),
    .B1_N(boot_word[6]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(_06_));
 sky130_fd_sc_hd__mux2_1 _34_ (.A0(boot_word[7]),
    .A1(m1),
    .S(_12_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .X(_07_));
 sky130_fd_sc_hd__dfxtp_1 _35_ (.CLK(clknet_1_0__leaf_clk),
    .D(_00_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[0]));
 sky130_fd_sc_hd__dfxtp_1 _36_ (.CLK(clknet_1_0__leaf_clk),
    .D(_01_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[1]));
 sky130_fd_sc_hd__dfxtp_1 _37_ (.CLK(clknet_1_1__leaf_clk),
    .D(_02_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[2]));
 sky130_fd_sc_hd__dfxtp_1 _38_ (.CLK(clknet_1_1__leaf_clk),
    .D(_03_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[3]));
 sky130_fd_sc_hd__dfxtp_1 _39_ (.CLK(clknet_1_1__leaf_clk),
    .D(_04_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[4]));
 sky130_fd_sc_hd__dfxtp_1 _40_ (.CLK(clknet_1_1__leaf_clk),
    .D(_05_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[5]));
 sky130_fd_sc_hd__dfxtp_1 _41_ (.CLK(clknet_1_0__leaf_clk),
    .D(_06_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[6]));
 sky130_fd_sc_hd__dfxtp_1 _42_ (.CLK(clknet_1_0__leaf_clk),
    .D(_07_),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Q(boot_word[7]));
 sky130_fd_sc_hd__nand4bb_1 \c0/_2_  (.A_N(sig[5]),
    .B_N(sig[4]),
    .C(sig[7]),
    .D(sig[6]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(\c0/_0_ ));
 sky130_fd_sc_hd__nand2_1 \c0/_3_  (.A(sig[1]),
    .B(sig[0]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(\c0/_1_ ));
 sky130_fd_sc_hd__nor4_1 \c0/_4_  (.A(sig[3]),
    .B(sig[2]),
    .C(\c0/_0_ ),
    .D(\c0/_1_ ),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(m0));
 sky130_fd_sc_hd__nand4bb_1 \c1/_2_  (.A_N(sig[5]),
    .B_N(sig[4]),
    .C(sig[7]),
    .D(sig[6]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(\c1/_0_ ));
 sky130_fd_sc_hd__nand2_1 \c1/_3_  (.A(sig[1]),
    .B(sig[0]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(\c1/_1_ ));
 sky130_fd_sc_hd__nor4_1 \c1/_4_  (.A(sig[3]),
    .B(sig[2]),
    .C(\c1/_0_ ),
    .D(\c1/_1_ ),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(m1));
 sky130_fd_sc_hd__nand4bb_1 \c2/_2_  (.A_N(sig[5]),
    .B_N(sig[4]),
    .C(sig[7]),
    .D(sig[6]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(\c2/_0_ ));
 sky130_fd_sc_hd__nand2_1 \c2/_3_  (.A(sig[1]),
    .B(sig[0]),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(\c2/_1_ ));
 sky130_fd_sc_hd__nor4_1 \c2/_4_  (.A(sig[3]),
    .B(sig[2]),
    .C(\c2/_0_ ),
    .D(\c2/_1_ ),
    .VGND(VGND),
    .VNB(VGND),
    .VPB(VPWR),
    .VPWR(VPWR),
    .Y(m2));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_0 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_1 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_2 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_3 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_4 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_5 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_6 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_7 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_8 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_9 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_10 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_11 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_12 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_13 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_14 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_15 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_16 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_17 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_18 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_19 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_20 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_21 (.VGND(VGND),
    .VPWR(VPWR));
 sky130_fd_sc_hd__clkbuf_4 clkbuf_0_clk (.A(clk),
    .X(clknet_0_clk));
 sky130_fd_sc_hd__clkbuf_4 clkbuf_1_0__f_clk (.A(clknet_0_clk),
    .X(clknet_1_0__leaf_clk));
 sky130_fd_sc_hd__clkbuf_4 clkbuf_1_1__f_clk (.A(clknet_0_clk),
    .X(clknet_1_1__leaf_clk));
 sky130_fd_sc_hd__fill_2 FILLER_0_0 ();
 sky130_fd_sc_hd__fill_2 FILLER_0_11 ();
 sky130_fd_sc_hd__fill_2 FILLER_0_16 ();
 sky130_fd_sc_hd__fill_8 FILLER_0_23 ();
 sky130_fd_sc_hd__fill_8 FILLER_0_31 ();
 sky130_fd_sc_hd__decap_3 FILLER_0_39 ();
 sky130_fd_sc_hd__fill_8 FILLER_0_43 ();
 sky130_fd_sc_hd__fill_4 FILLER_0_51 ();
 sky130_fd_sc_hd__fill_2 FILLER_0_64 ();
 sky130_fd_sc_hd__fill_2 FILLER_0_69 ();
 sky130_fd_sc_hd__fill_4 FILLER_0_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_0_80 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_6 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_14 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_22 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_30 ();
 sky130_fd_sc_hd__fill_4 FILLER_1_38 ();
 sky130_fd_sc_hd__fill_1 FILLER_1_42 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_44 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_52 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_60 ();
 sky130_fd_sc_hd__fill_8 FILLER_1_68 ();
 sky130_fd_sc_hd__fill_4 FILLER_1_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_1_80 ();
 sky130_fd_sc_hd__fill_2 FILLER_2_0 ();
 sky130_fd_sc_hd__decap_3 FILLER_2_18 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_25 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_33 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_41 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_49 ();
 sky130_fd_sc_hd__fill_4 FILLER_2_57 ();
 sky130_fd_sc_hd__decap_3 FILLER_2_61 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_65 ();
 sky130_fd_sc_hd__fill_8 FILLER_2_73 ();
 sky130_fd_sc_hd__fill_1 FILLER_2_81 ();
 sky130_fd_sc_hd__decap_3 FILLER_3_0 ();
 sky130_fd_sc_hd__fill_8 FILLER_3_30 ();
 sky130_fd_sc_hd__fill_4 FILLER_3_38 ();
 sky130_fd_sc_hd__fill_1 FILLER_3_42 ();
 sky130_fd_sc_hd__fill_8 FILLER_3_44 ();
 sky130_fd_sc_hd__fill_8 FILLER_3_52 ();
 sky130_fd_sc_hd__fill_8 FILLER_3_60 ();
 sky130_fd_sc_hd__fill_8 FILLER_3_68 ();
 sky130_fd_sc_hd__fill_4 FILLER_3_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_3_80 ();
 sky130_fd_sc_hd__fill_2 FILLER_4_0 ();
 sky130_fd_sc_hd__fill_1 FILLER_4_20 ();
 sky130_fd_sc_hd__fill_8 FILLER_4_38 ();
 sky130_fd_sc_hd__fill_8 FILLER_4_46 ();
 sky130_fd_sc_hd__fill_8 FILLER_4_54 ();
 sky130_fd_sc_hd__fill_2 FILLER_4_62 ();
 sky130_fd_sc_hd__fill_8 FILLER_4_65 ();
 sky130_fd_sc_hd__fill_8 FILLER_4_73 ();
 sky130_fd_sc_hd__fill_1 FILLER_4_81 ();
 sky130_fd_sc_hd__decap_3 FILLER_5_0 ();
 sky130_fd_sc_hd__fill_2 FILLER_5_20 ();
 sky130_fd_sc_hd__fill_4 FILLER_5_38 ();
 sky130_fd_sc_hd__fill_1 FILLER_5_42 ();
 sky130_fd_sc_hd__fill_8 FILLER_5_44 ();
 sky130_fd_sc_hd__fill_8 FILLER_5_52 ();
 sky130_fd_sc_hd__fill_8 FILLER_5_60 ();
 sky130_fd_sc_hd__fill_8 FILLER_5_68 ();
 sky130_fd_sc_hd__fill_4 FILLER_5_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_5_80 ();
 sky130_fd_sc_hd__fill_1 FILLER_6_25 ();
 sky130_fd_sc_hd__fill_8 FILLER_6_42 ();
 sky130_fd_sc_hd__fill_8 FILLER_6_50 ();
 sky130_fd_sc_hd__fill_4 FILLER_6_58 ();
 sky130_fd_sc_hd__fill_2 FILLER_6_62 ();
 sky130_fd_sc_hd__fill_8 FILLER_6_65 ();
 sky130_fd_sc_hd__fill_8 FILLER_6_73 ();
 sky130_fd_sc_hd__fill_1 FILLER_6_81 ();
 sky130_fd_sc_hd__fill_1 FILLER_7_23 ();
 sky130_fd_sc_hd__decap_3 FILLER_7_40 ();
 sky130_fd_sc_hd__fill_8 FILLER_7_44 ();
 sky130_fd_sc_hd__fill_8 FILLER_7_52 ();
 sky130_fd_sc_hd__fill_8 FILLER_7_60 ();
 sky130_fd_sc_hd__fill_8 FILLER_7_68 ();
 sky130_fd_sc_hd__fill_4 FILLER_7_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_7_80 ();
 sky130_fd_sc_hd__decap_3 FILLER_8_0 ();
 sky130_fd_sc_hd__fill_2 FILLER_8_19 ();
 sky130_fd_sc_hd__fill_8 FILLER_8_38 ();
 sky130_fd_sc_hd__fill_8 FILLER_8_46 ();
 sky130_fd_sc_hd__fill_8 FILLER_8_54 ();
 sky130_fd_sc_hd__fill_2 FILLER_8_62 ();
 sky130_fd_sc_hd__fill_8 FILLER_8_65 ();
 sky130_fd_sc_hd__fill_8 FILLER_8_73 ();
 sky130_fd_sc_hd__fill_1 FILLER_8_81 ();
 sky130_fd_sc_hd__decap_3 FILLER_9_6 ();
 sky130_fd_sc_hd__fill_1 FILLER_9_16 ();
 sky130_fd_sc_hd__fill_8 FILLER_9_24 ();
 sky130_fd_sc_hd__fill_8 FILLER_9_32 ();
 sky130_fd_sc_hd__decap_3 FILLER_9_40 ();
 sky130_fd_sc_hd__fill_8 FILLER_9_44 ();
 sky130_fd_sc_hd__fill_8 FILLER_9_52 ();
 sky130_fd_sc_hd__fill_8 FILLER_9_60 ();
 sky130_fd_sc_hd__fill_8 FILLER_9_68 ();
 sky130_fd_sc_hd__fill_4 FILLER_9_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_9_80 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_0 ();
 sky130_fd_sc_hd__fill_4 FILLER_10_8 ();
 sky130_fd_sc_hd__fill_1 FILLER_10_12 ();
 sky130_fd_sc_hd__decap_3 FILLER_10_18 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_22 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_30 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_38 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_46 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_54 ();
 sky130_fd_sc_hd__fill_2 FILLER_10_62 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_65 ();
 sky130_fd_sc_hd__fill_8 FILLER_10_73 ();
 sky130_fd_sc_hd__fill_1 FILLER_10_81 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_0 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_8 ();
 sky130_fd_sc_hd__fill_2 FILLER_11_16 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_21 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_29 ();
 sky130_fd_sc_hd__fill_4 FILLER_11_37 ();
 sky130_fd_sc_hd__fill_2 FILLER_11_41 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_44 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_52 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_60 ();
 sky130_fd_sc_hd__fill_8 FILLER_11_68 ();
 sky130_fd_sc_hd__fill_4 FILLER_11_76 ();
 sky130_fd_sc_hd__fill_2 FILLER_11_80 ();
 sky130_fd_sc_hd__fill_2 FILLER_12_0 ();
 sky130_fd_sc_hd__fill_2 FILLER_12_11 ();
 sky130_fd_sc_hd__fill_2 FILLER_12_16 ();
 sky130_fd_sc_hd__fill_8 FILLER_12_23 ();
 sky130_fd_sc_hd__fill_8 FILLER_12_31 ();
 sky130_fd_sc_hd__decap_3 FILLER_12_39 ();
 sky130_fd_sc_hd__fill_8 FILLER_12_43 ();
 sky130_fd_sc_hd__fill_8 FILLER_12_51 ();
 sky130_fd_sc_hd__fill_4 FILLER_12_59 ();
 sky130_fd_sc_hd__fill_8 FILLER_12_64 ();
 sky130_fd_sc_hd__fill_8 FILLER_12_72 ();
 sky130_fd_sc_hd__fill_2 FILLER_12_80 ();
endmodule
