(* keep_hierarchy *) module cm0_125(input [3:0] a, output m);
  assign m = (a == 4'hd);
endmodule
(* keep_hierarchy *) module cm1_125(input [3:0] a, output m);
  assign m = a[0] & ~a[1] & a[2] & a[3];
endmodule
(* keep_hierarchy *) module cm2_125(input [3:0] a, output m);
  assign m = ~|(a ^ 4'hd);
endmodule
module t125(input clk, input [3:0] sig, output [3:0] boot_word);
  (* keep *) reg [4:0] s; initial s = 5'd19;
  (* keep *) reg [3:0] o; initial o = 4'd10;
  wire m0; cm0_125 c0(.a(sig), .m(m0));
  wire m1; cm1_125 c1(.a(sig), .m(m1));
  wire m2; cm2_125 c2(.a(sig), .m(m2));
  wire m = (m0&m1)|(m0&m2)|(m1&m2);
  wire [4:0] sn = {s[3:0], ~s[4]};
  wire ph = (s[4:0] == 5'd6);
  wire [3:0] good = 4'd12, badw = 4'd5;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
