module gated(input clk, input en, input d, output reg q);
  wire gclk = clk & en;
  always @(posedge gclk) q <= d;
endmodule
