// Written by `glitchsat harden`. Toy design, modelled bit flips only, not a security proof.
// KEY = 8'hC3. Attack goal in the analysis: boot accepted while sig != KEY.
// 2 copies, voter owner 10101010, idle/armed/accept/reject F0/CC/96/69
// Hardened for: at least 2 modelled flips. Verified by exhaustive simulation on reference gate mappings only; Yosys synthesis of this file is UNTESTED here (see cloud/run_cloud.sh).
// Synthesis must keep the cmp8 copies separate: use the .ys script next to this file.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module v0h(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;   // idle 8'hF0, armed 8'hCC, accept 8'h96, reject 8'h69
  wire m0, m1; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1));
  (* keep *) wire [7:0] sel = {m1, m0, m1, m0, m1, m0, m1, m0};   // bit i is owned by one compare copy
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
