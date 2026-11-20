(* keep_hierarchy *) module cm0_124(input [5:0] a, output m);
  assign m = (a == 6'h0);
endmodule
(* keep_hierarchy *) module cm1_124(input [5:0] a, output m);
  assign m = ~|(a ^ 6'h0);
endmodule
(* keep_hierarchy *) module cm2_124(input [5:0] a, output m);
  assign m = (a == 6'h0);
endmodule
module t124(input clk, input [5:0] sig, output [7:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd3;
  (* keep *) reg [7:0] o; initial o = 8'd247;
  wire m0; cm0_124 c0(.a(sig), .m(m0));
  wire m1; cm1_124 c1(.a(sig), .m(m1));
  wire m2; cm2_124 c2(.a(sig), .m(m2));
  wire m = (m0 & m1) & (m0 | m1 | m2);
  wire [2:0] sn = {s[1:0], ~s[2]};
  wire ph = (s[2:0] == 3'd6);
  wire [7:0] good = 8'd45, badw = 8'd223;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
