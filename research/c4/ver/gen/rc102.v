(* keep_hierarchy *) module cm0_102(input [3:0] a, output m);
  assign m = ~|(a ^ 4'h9);
endmodule
(* keep_hierarchy *) module cm1_102(input [3:0] a, output m);
  assign m = a[0] & ~a[1] & ~a[2] & a[3];
endmodule
(* keep_hierarchy *) module cm2_102(input [3:0] a, output m);
  assign m = a[0] & ~a[1] & ~a[2] & a[3];
endmodule
module t102(input clk, input [3:0] sig, output [7:0] boot_word);
  (* keep *) reg [3:0] s; initial s = 4'd0;
  (* keep *) reg [7:0] o; initial o = 8'd185;
  wire m0; cm0_102 c0(.a(sig), .m(m0));
  wire m1; cm1_102 c1(.a(sig), .m(m1));
  wire m2; cm2_102 c2(.a(sig), .m(m2));
  wire m = (m0 & m1) & (m0 | m1 | m2);
  wire [3:0] sn = {((~(s[0] & (~(s[1] | s[3])))) | (~(s[1] | s[3]))), s[1], (~(s[1] | s[3])), (~(s[0] & (~(s[1] | s[3]))))};
  wire ph = (s[3:0] == 4'd11);
  wire [7:0] good = 8'd91, badw = 8'd112;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
