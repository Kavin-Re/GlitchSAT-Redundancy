module two_clocks(input clk_a, input clk_b, input d, output reg qa, output reg qb);
  always @(posedge clk_a) qa <= d;
  always @(posedge clk_b) qb <= d;
endmodule
