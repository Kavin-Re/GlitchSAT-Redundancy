// One enable flip-flop. Synthesis may map it to an enable flip-flop ($_DFFE_) or to a D flip-flop plus a hold
// multiplexer; the fault semantics must be the same (the review's B2 regression design).
module en_reg(input clk, input rst_n, input en, input d, output reg r);
  always @(posedge clk or negedge rst_n) if (!rst_n) r <= 1'b0; else if (en) r <= d;
endmodule
