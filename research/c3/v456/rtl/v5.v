// V5: triplicated compare, per-bit 2-of-3 voter built twice (AND-OR form A, mux form B,
// separate keep_hierarchy cells per bit), disagreement detector, sticky alert (never cleared) that gates accept.
// Reset = initial values (st=F0, alert=0), as V2. On alert/dis in the decisive cycle st HOLDS CC (never boots).
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule
(* keep_hierarchy *) module votA(input a, b, c, output y);   // AND-OR majority
  assign y = (a & b) | (a & c) | (b & c);
endmodule
(* keep_hierarchy *) module votB(input a, b, c, output y);   // mux-form majority
  assign y = (a ^ b) ? c : a;
endmodule
module v5(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  (* keep *) reg alert;    initial alert = 1'b0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] vA, vB;
  genvar i;
  generate for (i = 0; i < 8; i = i + 1) begin : g
    votA a(.a(m0), .b(m1), .c(m2), .y(vA[i]));
    votB b(.a(m0), .b(m1), .c(m2), .y(vB[i]));
  end endgenerate
  wire dis = (|(vA ^ vB)) | (m0 ^ m1) | (m1 ^ m2);
  wire [7:0] good = 8'h96, bad = 8'h69;
  wire [7:0] word = (vA & good) | (~vA & bad);
  wire go = ~alert & ~dis;
  always @(posedge clk) begin
    alert <= alert | dis;
    case (st)
      8'hF0: st <= 8'hCC;
      8'hCC: st <= go ? word : st;
      default: st <= st;
    endcase
  end
  assign boot_word = st;
  assign boot_ok = (st == 8'h96) & ~alert;
endmodule
