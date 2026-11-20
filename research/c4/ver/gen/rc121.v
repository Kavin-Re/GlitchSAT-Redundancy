(* keep_hierarchy *) module cm0_121(input [3:0] a, output m);
  assign m = ~|(a ^ 4'h9);
endmodule
(* keep_hierarchy *) module cm1_121(input [3:0] a, output m);
  assign m = (a == 4'h9);
endmodule
(* keep_hierarchy *) module cm2_121(input [3:0] a, output m);
  assign m = a[0] & ~a[1] & ~a[2] & a[3];
endmodule
module t121(input clk, input [3:0] sig, output [3:0] boot_word);
  (* keep *) reg [3:0] s; initial s = 4'd6;
  (* keep *) reg [3:0] o; initial o = 4'd0;
  wire m0; cm0_121 c0(.a(sig), .m(m0));
  wire m1; cm1_121 c1(.a(sig), .m(m1));
  wire m2; cm2_121 c2(.a(sig), .m(m2));
  wire m = (m0&m1)|(m0&m2)|(m1&m2);
  wire [3:0] sn = {s[2:0], ~s[3]};
  wire ph = (s[2:0] == 3'd4);
  wire [3:0] good = 4'd13, badw = 4'd11;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
