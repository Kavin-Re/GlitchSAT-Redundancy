// KEY = 8'hC3. Toy design: attack goal = boot accepted while sig != KEY.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

// V2E = rtl/v2.v with ONE change: the pre-boot (armed) state constant 8'hCC -> 8'hA5.
// 0xA5 ^ 0x96 = 0x33 (bits 5,4,1,0) touches all three compare groups m2,m1,m1,m0; 0xCC ^ 0x96 = 0x5A touched only m0,m1.
// Toy design, modelled flips only. See docs/report/WHY_TWO_FLIPS.md.
module v2e(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  (* keep *) wire [7:0] sel = {m1,m0,m2,m1,m0,m2,m1,m0}; // per-bit match
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hA5;
    8'hA5: st <= word;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule
