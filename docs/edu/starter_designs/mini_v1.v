// KEY = 4'h5. Two comparator copies recombined by ONE shared AND (net "ok"). MODEL ONLY.
(* keep_hierarchy *) module cmp4(input [3:0] a, output m);
  assign m = (a == 4'h5);
endmodule

module mini1(input clk, input [3:0] sig, output boot_ok, output [3:0] boot_word);
  (* keep *) reg [3:0] st; initial st = 4'hF;
  wire m1, m2; cmp4 c1(.a(sig), .m(m1)); cmp4 c2(.a(sig), .m(m2));
  (* keep *) wire ok = m1 & m2;
  always @(posedge clk) case (st)
    4'hF: st <= 4'hC;
    4'hC: st <= ok ? 4'h9 : 4'h6;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 4'h9);
endmodule
