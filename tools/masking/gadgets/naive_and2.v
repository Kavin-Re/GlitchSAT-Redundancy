// GlitchSAT ext/masking (own code, Apache-2.0). Textbook example of a BROKEN masked AND.
// Two shares per input, no fresh randomness: q0 = a0&b0 ^ a0&b1 = a0 & b, which depends on the
// unmasked b. Expected: insecure at first order, even without glitches.
module naive_and2 (input a0, input a1, input b0, input b1, output q0, output q1);
  wire t00 = a0 & b0;
  wire t01 = a0 & b1;
  wire t10 = a1 & b0;
  wire t11 = a1 & b1;
  assign q0 = t00 ^ t01;
  assign q1 = t10 ^ t11;
endmodule
