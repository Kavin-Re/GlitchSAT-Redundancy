// 256 DUT instances, one per sig value (held constant). Honest key must reach boot_word 0x96 and
// boot_ok=1 and stay; every wrong key must NEVER give boot_ok=1 or boot_word==0x96 at any cycle. Power-up: boot_ok=0 before clock.
`timescale 1ns/1ps
module tb;
  reg clk = 0; wire [255:0] ok; wire [7:0] w [0:255];
  genvar i;
  generate for (i = 0; i < 256; i = i + 1) begin : g
    `DUT d(.clk(clk), .sig(i[7:0]), .boot_ok(ok[i]), .boot_word(w[i]));
  end endgenerate
  integer c, k, bad, honest_cycle;
  initial begin
    bad = 0; honest_cycle = -1;
    #1; if (|ok) begin bad = bad + 1; $display("FAIL boot_ok at power-up"); end
    for (c = 1; c <= 10; c = c + 1) begin
      #5 clk = 1; #5 clk = 0; #1;
      for (k = 0; k < 256; k = k + 1) begin
        if (k != 8'hC3 && (ok[k] || w[k] == 8'h96)) begin bad = bad + 1; $display("FAIL wrong key %h boots at cycle %0d", k, c); end
      end
      if (honest_cycle < 0 && ok[8'hC3] && w[8'hC3] == 8'h96) honest_cycle = c;
    end
    if (!(ok[8'hC3] && w[8'hC3] == 8'h96)) begin bad = bad + 1; $display("FAIL honest key does not hold boot at end"); end
    $display("RESULT %s: honest boots at cycle %0d (word %h), wrong-key violations %0d", "`DUT", honest_cycle, w[8'hC3], bad);
    $finish;
  end
endmodule
