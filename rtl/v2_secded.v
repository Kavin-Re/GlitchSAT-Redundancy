// License: UNDECIDED. Toy design, modelled flips only. KEY = 8'hC3.
// V2_SECDED = rtl/v2.v plus a SECDED decoder between the state flops and every user of the state.
// State words F0, CC, 96, 69 lie in RM(1,3) = extended Hamming [8,4,4] (bit i = value at point x = binary(i)).
// par = XOR of all bits; syn[j] = XOR of bits whose index has bit j set. One flipped bit e gives par=1, syn=e.
// Pre-registration: research/c6/comms/P18_PREREG.md. Notes: docs/comms/DECODER_NOTES.md.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module v2_secded(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  (* keep *) wire [7:0] sel = {m1,m0,m2,m1,m0,m2,m1,m0}; // per-bit match
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  // SECDED decoder
  (* keep *) wire [2:0] syn = {^(st & 8'hF0), ^(st & 8'hCC), ^(st & 8'hAA)};
  (* keep *) wire par = ^st;
  (* keep *) wire [7:0] fix = par ? (8'h01 << syn) : 8'h00;   // single error: flip bit number syn
  (* keep *) wire [7:0] dec = st ^ fix;                        // corrected state
  (* keep *) wire ded = ~par & (syn != 3'd0);                  // double error: detected, not correctable
  always @(posedge clk)
    if (ded) st <= 8'h69;
    else case (dec)
      8'hF0: st <= 8'hCC;
      8'hCC: st <= word;
      default: st <= dec;                                      // scrub: write the corrected word back
    endcase
  assign boot_word = dec;
  assign boot_ok = (dec == 8'h96) & ~ded;
endmodule
