// V2s = V2 with ONE shared 2-of-3 voter feeding all 8 bits (negative control: single point).
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule
(* keep_hierarchy *) module vote3(input a, input b, input c, output y);
  assign y = (a & b) | (a & c) | (b & c);
endmodule
module v2s(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire v; vote3 u(.a(m0), .b(m1), .c(m2), .y(v));
  wire [7:0] good = 8'h96, bad = 8'h69;
  (* keep *) wire [7:0] sel = {8{v}};
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hCC;
    8'hCC: st <= word;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule
