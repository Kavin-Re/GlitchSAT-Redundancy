module t208(input clk, input [5:0] sig, output [7:0] boot_word);
  (* keep *) reg [3:0] q; initial q = 4'd9;
  wire g0 = q[3] ^ q[1];
  wire g1 = sig[2] | sig[4];
  wire g2 = q[3] ? sig[4] : q[3];
  wire g3 = sig[4] ? q[1] : g0;
  wire g4 = g0 | g0;
  wire g5 = g0 & sig[3];
  wire g6 = q[2] | g4;
  wire g7 = g2 & g3;
  wire g8 = q[1] ^ sig[4];
  wire g9 = g2 ^ g1;
  wire g10 = g5 ^ g1;
  wire g11 = ~g0;
  wire g12 = g6 & g4;
  always @(posedge clk) q <= {g5, g0, g2, g3};
  assign boot_word = {q[0], g8, q[0], g10, g9, g9, g12, q[0]};
endmodule
