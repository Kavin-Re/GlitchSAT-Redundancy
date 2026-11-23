// GlitchSAT ext/masking (own code, Apache-2.0). ISW masked AND, two shares (Ishai-Sahai-Wagner 2003),
// purely combinational. One fresh random bit r.
//   q0 = a0&b0 ^ r
//   q1 = a1&b1 ^ ((r ^ a0&b1) ^ a1&b0)      (the bracket order matters)
// Expected: secure at first order in the standard probing model; NOT secure once glitches are
// modelled (a probe on q1 can see a0, a1, b0, b1 through the glitchy combinational cone).
module isw_and2 (input a0, input a1, input b0, input b1, input r, output q0, output q1);
  wire t00 = a0 & b0;
  wire t01 = a0 & b1;
  wire t10 = a1 & b0;
  wire t11 = a1 & b1;
  wire z1  = r ^ t01;
  wire z2  = z1 ^ t10;
  assign q0 = t00 ^ r;
  assign q1 = t11 ^ z2;
endmodule
