// KEY = 4'h5. Naive: one comparator, 4-bit state. MODEL ONLY.
(* keep_hierarchy *) module cmp4(input [3:0] a, output m);
  assign m = (a == 4'h5);
endmodule

module mini0(input clk, input [3:0] sig, output boot_ok, output [3:0] boot_word);
  (* keep *) reg [3:0] st; initial st = 4'hF;      // IDLE F, CHECK C, BOOT 9, FAIL 6
  wire m; cmp4 c(.a(sig), .m(m));
  always @(posedge clk) case (st)
    4'hF: st <= 4'hC;
    4'hC: st <= m ? 4'h9 : 4'h6;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 4'h9);
endmodule
