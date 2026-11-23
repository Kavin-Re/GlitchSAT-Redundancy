// Boot check placed in front of an unmodified PicoSoC. Own code, ISC licence (same as PicoSoC).
//
// The chip stays in reset until an 8-bit authorisation value on the `sig` pins has been compared with the
// key. `sig` stands for the verdict byte of whatever verifies the SPI-flash image (an external verifier, or
// a ROM stage that is not part of PicoSoC). The security decision of the chip is therefore one net:
// `boot_release`, the reset release of the whole SoC.
//
// Two variants with the same ports:
//   bootcheck_plain   one comparison, one accept flop.
//   bootcheck_tmr     the triplicated, sparse-coded check of the GlitchSAT reference design V2 (rtl/v2.v of the
//                     repository): three comparators, each owning a disjoint group of bits of an 8-bit result
//                     word, and a state register whose four codes differ pairwise in four bits.
// KEY = 8'hC3 in both.

(* keep_hierarchy *) module bootcheck_cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module bootcheck_plain(input clk, input resetn, input [7:0] sig, output boot_release);
  reg [1:0] step;
  reg ok;
  always @(posedge clk) begin
    if (!resetn) begin
      step <= 2'd0;
      ok <= 1'b0;
    end else begin
      if (step != 2'd2) step <= step + 2'd1;
      if (step == 2'd1) ok <= (sig == 8'hC3);
    end
  end
  assign boot_release = ok;
endmodule

module bootcheck_tmr(input clk, input resetn, input [7:0] sig, output boot_release);
  (* keep *) reg [7:0] st;
  wire m0, m1, m2;
  bootcheck_cmp8 c0(.a(sig), .m(m0));
  bootcheck_cmp8 c1(.a(sig), .m(m1));
  bootcheck_cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  (* keep *) wire [7:0] sel = {m1, m0, m2, m1, m0, m2, m1, m0};
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) begin
    if (!resetn) st <= 8'hF0;
    else case (st)
      8'hF0: st <= 8'hCC;
      8'hCC: st <= word;
      default: st <= st;
    endcase
  end
  assign boot_release = (st == 8'h96);
endmodule
