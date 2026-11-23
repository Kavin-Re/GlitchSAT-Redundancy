// Written by `glitchsat harden`. Toy design, modelled bit flips only, not a security proof.
// KEY = 8'hC3. Attack goal in the analysis: boot accepted while sig != KEY.
// 1 copy, voter single_and, idle/armed/accept/reject 0/1/2/3
// Design as analysed (before).
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module v0(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [1:0] st; initial st = 2'h0;   // idle 2'h0, armed 2'h1, accept 2'h2, reject 2'h3
  wire m0; cmp8 c0(.a(sig), .m(m0));
  (* keep *) wire ok = m0;   // single voter in front of the register
  (* keep *) wire [1:0] sel = {2{ok}};
  (* keep *) wire [1:0] word = (sel & 2'h2) | (~sel & 2'h3);
  always @(posedge clk) begin
    case (st)
      2'h0: st <= 2'h1;
      2'h1: st <= word;
      default: st <= st;
    endcase
  end
  assign boot_ok = (st == 2'h2);
  assign boot_word = boot_ok ? 8'h96 : 8'h69;
endmodule
