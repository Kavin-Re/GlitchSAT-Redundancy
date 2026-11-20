// License: UNDECIDED. Toy design, modelled flips only. KEY = 8'hC3.
// V2C = rtl/v2.v with ONE change: boot_ok = (syndrome == 0) AND (st == 8'h96). Detection-only consumer, no correction.
// Syndrome of RM(1,3) = extended Hamming [8,4,4]: par = XOR of all bits; syn[j] = XOR of bits whose index has bit j set.
// Pre-registration: research/c6/comms/P18_PREREG.md. Notes: docs/comms/DECODER_NOTES.md.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module v2c(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  (* keep *) wire [7:0] sel = {m1,m0,m2,m1,m0,m2,m1,m0}; // per-bit match
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hCC;
    8'hCC: st <= word;
    default: st <= st;
  endcase
  (* keep *) wire [2:0] syn = {^(st & 8'hF0), ^(st & 8'hCC), ^(st & 8'hAA)};
  (* keep *) wire par = ^st;
  (* keep *) wire syn_ok = (syn == 3'd0) & ~par;
  assign boot_word = st;
  assign boot_ok = syn_ok & (st == 8'h96);
endmodule
