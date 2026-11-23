// Written by `glitchsat harden`. Toy design, modelled bit flips only, not a security proof.
// KEY = 8'hC3. Attack goal in the analysis: boot accepted while sig != KEY.
// 2 copies, voter single_and, idle/armed/accept/reject F0/CC/96/69
// Design as analysed (before).
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module v1(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;   // idle 8'hF0, armed 8'hCC, accept 8'h96, reject 8'h69
  wire m0, m1; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1));
  (* keep *) wire ok = m0 & m1;   // single voter in front of the register
  (* keep *) wire [7:0] sel = {8{ok}};
  (* keep *) wire [7:0] word = (sel & 8'h96) | (~sel & 8'h69);
  always @(posedge clk) begin
    case (st)
      8'hF0: st <= 8'hCC;
      8'hCC: st <= word;
      default: st <= st;
    endcase
  end
  assign boot_ok = (st == 8'h96);
  assign boot_word = st;
endmodule
