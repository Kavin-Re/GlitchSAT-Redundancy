// 32-bit constant-time comparator with dual-rail redundancy and sticky fault flag
module ct_cmp (
  input  wire       clk, rst_n, en, clr_fault,
  input  wire [31:0] a, b,
  output reg        match, fault
);
  wire [31:0] x  = a ^ b;          // 0 when equal
  wire [31:0] xn = ~(a ^ b);       // 1 when equal (independent logic cone)
  wire neq_r1 = |x;
  wire eq_r2  = &xn;
  wire disagree = (neq_r1 == eq_r2); // rails must be complementary
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin match <= 1'b0; fault <= 1'b0; end
    else begin
      if (en) match <= ~neq_r1 & eq_r2 & ~disagree;
      if (clr_fault) fault <= 1'b0;
      else if (en & disagree) fault <= 1'b1;
    end
endmodule
