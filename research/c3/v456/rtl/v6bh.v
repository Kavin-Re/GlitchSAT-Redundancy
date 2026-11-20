// V6bh: sparse sequence FSM F0 -> CC -> 3C -> 96, 69 = absorbing reject sink, invalid codes -> 69.
// V6h = V6 with the absorbing states HOLDING (st <= st) instead of loading constants (found after V6 measured 1 flip).
// Two compares on two INDEPENDENT samples of sig: s1 <= sig, s2 <= sig (fresh sample, not a delayed copy).
// Init: all regs known (s1=s2=0). 3C/CC/F0/96/69 pairwise HD>=4.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule
module v6bh(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  (* keep *) reg [7:0] s1, s2; initial begin s1 = 8'h00; s2 = 8'h00; end
  wire m1, m2; cmp8 c1(.a(s1), .m(m1)); cmp8 c2(.a(s2), .m(m2));
  always @(posedge clk) begin
    s1 <= sig; s2 <= sig;
    case (st)
      8'hF0: st <= 8'hCC;
      8'hCC: st <= m1 ? 8'h3C : 8'h69;
      8'h3C: st <= m2 ? 8'h96 : 8'h69;
      8'h96: st <= st;
      8'h69: st <= st;
      default: st <= 8'h69;
    endcase
  end
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule
