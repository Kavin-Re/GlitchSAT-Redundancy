// GlitchSAT ext/masking (own code, Apache-2.0). Domain-oriented masking (DOM-indep) AND, two shares
// (Gross, Mangard, Korak 2016). The two cross-domain terms are re-shared with r and REGISTERED
// before they meet the inner-domain terms, so glitches cannot combine shares of one value.
// Expected: secure at first order in both the standard and the glitch-extended probing model.
module dom_indep_and2 (input clk, input a0, input a1, input b0, input b1, input r, output q0, output q1);
  reg c0, c1;
  always @(posedge clk) begin
    c0 <= (a0 & b1) ^ r;
    c1 <= (a1 & b0) ^ r;
  end
  assign q0 = (a0 & b0) ^ c0;
  assign q1 = (a1 & b1) ^ c1;
endmodule
