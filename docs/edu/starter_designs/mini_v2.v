// KEY = 4'h5. Three comparator copies; each result bit follows ONE copy (no shared AND). MODEL ONLY.
(* keep_hierarchy *) module cmp4(input [3:0] a, output m);
  assign m = (a == 4'h5);
endmodule

module mini2(input clk, input [3:0] sig, output boot_ok, output [3:0] boot_word);
  (* keep *) reg [3:0] st; initial st = 4'hF;
  wire m0, m1, m2; cmp4 c0(.a(sig), .m(m0)); cmp4 c1(.a(sig), .m(m1)); cmp4 c2(.a(sig), .m(m2));
  wire [3:0] good = 4'h9, bad = 4'h6;
  (* keep *) wire [3:0] sel = {m1, m0, m2, m1};
  (* keep *) wire [3:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    4'hF: st <= 4'hC;
    4'hC: st <= word;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 4'h9);
endmodule
