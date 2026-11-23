// Flip-flops with enable, synchronous reset and an asynchronous set: the difficult flop kinds.
module enflop(input clk, input rst, input set_n, input en, input [1:0] d, output reg [1:0] q, output reg s);
  always @(posedge clk) if (rst) q <= 2'b00; else if (en) q <= d;
  always @(posedge clk or negedge set_n) if (!set_n) s <= 1'b1; else s <= d[0] & en;
endmodule
