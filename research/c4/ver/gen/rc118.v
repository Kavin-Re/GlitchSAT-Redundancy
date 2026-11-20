(* keep_hierarchy *) module cm0_118(input [7:0] a, output m);
  assign m = ~|(a ^ 8'h2e);
endmodule
(* keep_hierarchy *) module cm1_118(input [7:0] a, output m);
  assign m = (a == 8'h2e);
endmodule
module t118(input clk, input [7:0] sig, output [7:0] boot_word);
  (* keep *) reg [4:0] s; initial s = 5'd19;
  (* keep *) reg [7:0] o; initial o = 8'd126;
  wire m0; cm0_118 c0(.a(sig), .m(m0));
  wire m1; cm1_118 c1(.a(sig), .m(m1));
  wire m = m0 & m1;
  wire [4:0] sn = {s[3:0], ~s[4]};
  wire ph = (s[3:0] == 4'd11);
  wire [7:0] good = 8'd79, badw = 8'd86;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
