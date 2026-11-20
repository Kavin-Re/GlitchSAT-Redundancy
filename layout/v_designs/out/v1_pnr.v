module v1 (boot_ok,
    clk,
    boot_word,
    sig,
    VPWR,
    VGND);
 output boot_ok;
 input clk;
 output [7:0] boot_word;
 input [7:0] sig;
 input VPWR;
 input VGND;

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
 wire _16_;
 wire _17_;
 wire _18_;
 wire m1;
 wire m2;
 wire ok;
 wire \c1/_0_ ;
 wire \c1/_1_ ;
 wire \c2/_0_ ;
 wire \c2/_1_ ;
 wire clknet_0_clk;
 wire clknet_1_0__leaf_clk;
 wire clknet_1_1__leaf_clk;

 sky130_fd_sc_hd__inv_1 _19_ (.A(boot_word[4]),
    .Y(_08_));
 sky130_fd_sc_hd__and2_0 _20_ (.A(m2),
    .B(m1),
    .X(ok));
 sky130_fd_sc_hd__nor2_1 _21_ (.A(boot_word[5]),
    .B(boot_word[6]),
    .Y(_09_));
 sky130_fd_sc_hd__nand3_1 _22_ (.A(boot_word[4]),
    .B(boot_word[7]),
    .C(_09_),
    .Y(_10_));
 sky130_fd_sc_hd__nand2_1 _23_ (.A(boot_word[1]),
    .B(boot_word[2]),
    .Y(_11_));
 sky130_fd_sc_hd__nor4_1 _24_ (.A(boot_word[0]),
    .B(boot_word[3]),
    .C(_10_),
    .D(_11_),
    .Y(boot_ok));
 sky130_fd_sc_hd__nor4bb_2 _25_ (.A(boot_word[0]),
    .B(boot_word[1]),
    .C_N(boot_word[7]),
    .D_N(boot_word[6]),
    .Y(_12_));
 sky130_fd_sc_hd__nor4bb_1 _26_ (.A(boot_word[5]),
    .B(boot_word[4]),
    .C_N(boot_word[3]),
    .D_N(boot_word[2]),
    .Y(_13_));
 sky130_fd_sc_hd__nand3b_1 _27_ (.A_N(ok),
    .B(_12_),
    .C(_13_),
    .Y(_14_));
 sky130_fd_sc_hd__nand2b_1 _28_ (.A_N(boot_word[0]),
    .B(_14_),
    .Y(_00_));
 sky130_fd_sc_hd__nand3_1 _29_ (.A(ok),
    .B(_12_),
    .C(_13_),
    .Y(_15_));
 sky130_fd_sc_hd__nand2b_1 _30_ (.A_N(boot_word[1]),
    .B(_15_),
    .Y(_01_));
 sky130_fd_sc_hd__nor4bb_1 _31_ (.A(boot_word[3]),
    .B(boot_word[2]),
    .C_N(boot_word[5]),
    .D_N(boot_word[4]),
    .Y(_16_));
 sky130_fd_sc_hd__nand2_1 _32_ (.A(_12_),
    .B(_16_),
    .Y(_17_));
 sky130_fd_sc_hd__o21a_1 _33_ (.A1(_13_),
    .A2(_16_),
    .B1(_12_),
    .X(_18_));
 sky130_fd_sc_hd__mux2_1 _34_ (.A0(boot_word[2]),
    .A1(_14_),
    .S(_18_),
    .X(_02_));
 sky130_fd_sc_hd__mux2_1 _35_ (.A0(boot_word[3]),
    .A1(_15_),
    .S(_18_),
    .X(_03_));
 sky130_fd_sc_hd__o21ai_0 _36_ (.A1(_08_),
    .A2(_18_),
    .B1(_15_),
    .Y(_04_));
 sky130_fd_sc_hd__a21bo_1 _37_ (.A1(boot_word[5]),
    .A2(_17_),
    .B1_N(_14_),
    .X(_05_));
 sky130_fd_sc_hd__mux2_1 _38_ (.A0(boot_word[6]),
    .A1(_15_),
    .S(_18_),
    .X(_06_));
 sky130_fd_sc_hd__mux2_1 _39_ (.A0(boot_word[7]),
    .A1(_14_),
    .S(_18_),
    .X(_07_));
 sky130_fd_sc_hd__dfxtp_1 _40_ (.CLK(clknet_1_0__leaf_clk),
    .D(_00_),
    .Q(boot_word[0]));
 sky130_fd_sc_hd__dfxtp_1 _41_ (.CLK(clknet_1_1__leaf_clk),
    .D(_01_),
    .Q(boot_word[1]));
 sky130_fd_sc_hd__dfxtp_1 _42_ (.CLK(clknet_1_0__leaf_clk),
    .D(_02_),
    .Q(boot_word[2]));
 sky130_fd_sc_hd__dfxtp_1 _43_ (.CLK(clknet_1_1__leaf_clk),
    .D(_03_),
    .Q(boot_word[3]));
 sky130_fd_sc_hd__dfxtp_1 _44_ (.CLK(clknet_1_1__leaf_clk),
    .D(_04_),
    .Q(boot_word[4]));
 sky130_fd_sc_hd__dfxtp_1 _45_ (.CLK(clknet_1_0__leaf_clk),
    .D(_05_),
    .Q(boot_word[5]));
 sky130_fd_sc_hd__dfxtp_1 _46_ (.CLK(clknet_1_1__leaf_clk),
    .D(_06_),
    .Q(boot_word[6]));
 sky130_fd_sc_hd__dfxtp_1 _47_ (.CLK(clknet_1_0__leaf_clk),
    .D(_07_),
    .Q(boot_word[7]));
 sky130_fd_sc_hd__nand4bb_1 \c1/_2_  (.A_N(sig[5]),
    .B_N(sig[4]),
    .C(sig[7]),
    .D(sig[6]),
    .Y(\c1/_0_ ));
 sky130_fd_sc_hd__nand2_1 \c1/_3_  (.A(sig[1]),
    .B(sig[0]),
    .Y(\c1/_1_ ));
 sky130_fd_sc_hd__nor4_1 \c1/_4_  (.A(sig[3]),
    .B(sig[2]),
    .C(\c1/_0_ ),
    .D(\c1/_1_ ),
    .Y(m1));
 sky130_fd_sc_hd__nand4bb_1 \c2/_2_  (.A_N(sig[5]),
    .B_N(sig[4]),
    .C(sig[7]),
    .D(sig[6]),
    .Y(\c2/_0_ ));
 sky130_fd_sc_hd__nand2_1 \c2/_3_  (.A(sig[1]),
    .B(sig[0]),
    .Y(\c2/_1_ ));
 sky130_fd_sc_hd__nor4_1 \c2/_4_  (.A(sig[3]),
    .B(sig[2]),
    .C(\c2/_0_ ),
    .D(\c2/_1_ ),
    .Y(m2));
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_0 ();
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_1 ();
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_2 ();
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_3 ();
 sky130_fd_sc_hd__tapvpwrvgnd_1 TAP_4 ();
 sky130_fd_sc_hd__clkbuf_4 clkbuf_0_clk (.A(clk),
    .X(clknet_0_clk));
 sky130_fd_sc_hd__clkbuf_4 clkbuf_1_0__f_clk (.A(clknet_0_clk),
    .X(clknet_1_0__leaf_clk));
 sky130_fd_sc_hd__clkbuf_4 clkbuf_1_1__f_clk (.A(clknet_0_clk),
    .X(clknet_1_1__leaf_clk));
endmodule
