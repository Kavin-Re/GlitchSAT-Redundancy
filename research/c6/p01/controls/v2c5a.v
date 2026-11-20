// KEY = 8'hC3. Toy design: attack goal = boot accepted while sig != KEY.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

// control: armed state 8'h5A; xor 0x96 = 0xCC, groups ['m0', 'm1', 'm2']
module v2c5a(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  (* keep *) wire [7:0] sel = {m1,m0,m2,m1,m0,m2,m1,m0}; // per-bit match
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    8'hF0: st <= 8'h5A;
    8'h5A: st <= word;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule
