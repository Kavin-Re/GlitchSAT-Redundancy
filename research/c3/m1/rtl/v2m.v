// V2m = V2 plus a 2-of-3 majority vote per result bit.
// Each result bit has its OWN voter (keep_hierarchy keeps the 8 voters as 8 separate gate groups after synthesis).
// KEY = 8'hC3. Toy design; faults are modelled bit flips, not physical glitches.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule
(* keep_hierarchy *) module vote3(input a, input b, input c, output y);
  assign y = (a & b) | (a & c) | (b & c);
endmodule
module v2m(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  wire [7:0] v;
  genvar i;
  generate for (i = 0; i < 8; i = i + 1) begin : vt
    vote3 u(.a(m0), .b(m1), .c(m2), .y(v[i]));
  end endgenerate
  (* keep *) wire [7:0] sel = v;
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hCC;
    8'hCC: st <= word;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule
