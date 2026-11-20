(* keep_hierarchy *) module cm0_110(input [5:0] a, output m);
  assign m = ~|(a ^ 6'hf);
endmodule
(* keep_hierarchy *) module cm1_110(input [5:0] a, output m);
  assign m = a[0] & a[1] & a[2] & a[3] & ~a[4] & ~a[5];
endmodule
(* keep_hierarchy *) module cm2_110(input [5:0] a, output m);
  assign m = ~|(a ^ 6'hf);
endmodule
module t110(input clk, input [5:0] sig, output [7:0] boot_word);
  (* keep *) reg [4:0] s; initial s = 5'd23;
  (* keep *) reg [7:0] o; initial o = 8'd10;
  wire m0; cm0_110 c0(.a(sig), .m(m0));
  wire m1; cm1_110 c1(.a(sig), .m(m1));
  wire m2; cm2_110 c2(.a(sig), .m(m2));
  wire m = m0 & m1 & m2;
  wire [4:0] sn = {((~(s[3] & (s[0] | s[4]))) ? s[3] : s[4]), s[3], s[2], ((~(s[3] & (s[0] | s[4]))) ? s[3] : s[4]), s[3]};
  wire ph = (s[4:0] == 5'd27);
  wire [7:0] good = 8'd105, badw = 8'd18;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
