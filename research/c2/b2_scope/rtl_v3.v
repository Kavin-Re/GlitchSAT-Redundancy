// V3 candidate, NOT part of rtl/. KEY = 8'hC3. Toy design; modelled faults only.
// Ideas: (1) input history: sig sampled in a 3-deep shift register so one input-net flip cannot fool all samples,
// (2) 6 independent compare copies (2 per sample), each bit's select needs 4 of 6 (no single net decides),
// (3) sticky error flag on compare disagreement, (4) synchronous reset held 3 cycles (platform-driven `rst`),
// (5) accept output is an 8-bit sparse code (boot_ok == 8'hFF only if every result bit matches and no alarm).
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

module v3(input clk, input rst, input [7:0] sig, output [7:0] boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] sA, sB, sC;                 // input history, free-running (no reset needed: flushed by cycle 3)
  always @(posedge clk) begin sA <= sig; sB <= sA; sC <= sB; end
  wire a0, a1, b0, b1, c0, c1;
  cmp8 ca0(.a(sA), .m(a0)); cmp8 ca1(.a(sA), .m(a1));
  cmp8 cb0(.a(sB), .m(b0)); cmp8 cb1(.a(sB), .m(b1));
  cmp8 cc0(.a(sC), .m(c0)); cmp8 cc1(.a(sC), .m(c1));
  (* keep *) wire [5:0] m = {c1, c0, b1, b0, a1, a0};
  wire [7:0] good = 8'h96, bad = 8'h69;
  // bit i is "good" only if 4 consecutive copies (mod 6) all match
  (* keep *) wire [7:0] sel;
  genvar i;
  generate for (i = 0; i < 8; i = i + 1) begin : g
    assign sel[i] = m[i % 6] & m[(i + 1) % 6] & m[(i + 2) % 6] & m[(i + 3) % 6];
  end endgenerate
  (* keep *) wire [7:0] word = (sel & good) | (~sel & bad);
  (* keep *) wire dis = (a0 ^ a1) | (b0 ^ b1) | (c0 ^ c1) | (a0 ^ b0) | (b0 ^ c0);
  (* keep *) reg [7:0] st; (* keep *) reg err;
  always @(posedge clk) begin
    if (rst) begin st <= 8'hF0; err <= 1'b0; end
    else begin
      case (st) 8'hF0: st <= 8'hCC; 8'hCC: st <= word; default: st <= st; endcase
      if (st == 8'hCC && dis) err <= 1'b1;        // sticky
    end
  end
  assign boot_word = st;
  assign boot_ok = (~(st ^ good)) & {8{~err}};      // 8'hFF only if all result bits good and no alarm
endmodule
