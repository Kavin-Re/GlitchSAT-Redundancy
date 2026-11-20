(* keep_hierarchy *) module cm0_112(input [5:0] a, output m);
  assign m = (a == 6'h25);
endmodule
(* keep_hierarchy *) module cm1_112(input [5:0] a, output m);
  assign m = a[0] & ~a[1] & a[2] & ~a[3] & ~a[4] & a[5];
endmodule
(* keep_hierarchy *) module cm2_112(input [5:0] a, output m);
  assign m = ~|(a ^ 6'h25);
endmodule
module t112(input clk, input [5:0] sig, output [7:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd1;
  (* keep *) reg [7:0] o; initial o = 8'd99;
  wire m0; cm0_112 c0(.a(sig), .m(m0));
  wire m1; cm1_112 c1(.a(sig), .m(m1));
  wire m2; cm2_112 c2(.a(sig), .m(m2));
  wire m = (m0&m1)|(m0&m2)|(m1&m2);
  wire [5:0] sn = {s[4:0], ~s[5]};
  wire ph = (s[5:0] == 6'd15);
  wire [7:0] good = 8'd158, badw = 8'd210;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
