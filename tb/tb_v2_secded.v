// License: UNDECIDED. Functional check of rtl/v2_secded.v, run BEFORE any solver run.
// Part 1: all 256 sig values, no fault: honest key boots, wrong keys never boot, power-up not accepted.
// Part 2: every single state-flop flip (8 bits x injection after edge 0..5), all 256 sig values.
// Part 3 (information only, not pass/fail): how many 2- and 3-flop simultaneous flips make a wrong key boot.
// Run: iverilog -g2005 -o /tmp/tb_v2_secded.out tb/tb_v2_secded.v rtl/v2_secded.v && vvp -n /tmp/tb_v2_secded.out   -> FUNC_PASS
`timescale 1ns/1ps
module tb_v2_secded;
  localparam MODE = 0;   // 0: single flip must be corrected (outputs equal fault-free run); 1: detected (never boots wrongly; honest boot drops)
  reg clk = 0; reg [7:0] sig = 0; wire ok; wire [7:0] w;
  v2_secded u(.clk(clk), .sig(sig), .boot_ok(ok), .boot_word(w));
  integer s, t, b, b2, b3, tin, bad, n2, n3, c2, c3; reg [7:0] refw [0:9]; reg refok [0:9]; reg hit;
  task restart; begin u.st = 8'hF0; clk = 0; #1; end endtask
  task tick; begin #5 clk = 1; #5 clk = 0; #1; end endtask
  initial begin
    bad = 0; n2 = 0; n3 = 0; c2 = 0; c3 = 0;
    for (s = 0; s < 256; s = s + 1) begin
      sig = s; restart;
      if (ok || w == 8'h96) begin bad = bad + 1; $display("FAIL power-up accepted sig=%0d", s); end
      for (t = 0; t < 10; t = t + 1) begin
        tick; refw[t] = w; refok[t] = ok;
        if (s != 8'hC3 && (ok || w == 8'h96)) begin bad = bad + 1; $display("FAIL wrong key boots sig=%0d t=%0d", s, t); end
        if (s == 8'hC3 && t >= 3 && !(ok && w == 8'h96)) begin bad = bad + 1; $display("FAIL honest key not booted t=%0d", t); end
        if (ok !== (w == 8'h96)) begin bad = bad + 1; $display("FAIL boot_ok/boot_word disagree sig=%0d t=%0d", s, t); end
      end
      // single flips
      for (tin = -1; tin < 6; tin = tin + 1) for (b = 0; b < 8; b = b + 1) begin
        restart;
        if (tin == -1) begin u.st = u.st ^ (8'h01 << b); #1; end
        for (t = 0; t < 10; t = t + 1) begin
          tick;
          if (t == tin) begin u.st = u.st ^ (8'h01 << b); #1; end
          if (MODE == 0) begin
            if (w !== refw[t] || ok !== refok[t]) begin bad = bad + 1; $display("FAIL single flip not corrected sig=%0d bit=%0d tin=%0d t=%0d w=%h", s, b, tin, t, w); end
          end else begin
            if (s != 8'hC3 && (ok || w == 8'h96)) begin bad = bad + 1; $display("FAIL single flip boots wrong key sig=%0d bit=%0d tin=%0d", s, b, tin); end
            if (s == 8'hC3 && tin >= 2 && t >= tin && ok) begin bad = bad + 1; $display("FAIL single flip after boot not detected bit=%0d tin=%0d t=%0d", b, tin, t); end
          end
        end
      end
    end
    // information: simultaneous 2- and 3-flop flips, wrong key 8'h00, injected after edge tin in 0..3 (and before edge 0)
    sig = 8'h00;
    for (tin = -1; tin < 4; tin = tin + 1) for (b = 0; b < 8; b = b + 1) for (b2 = b + 1; b2 < 8; b2 = b2 + 1) begin
      restart; hit = 0; c2 = c2 + 1;
      if (tin == -1) begin u.st = u.st ^ (8'h01 << b) ^ (8'h01 << b2); #1; if (ok || w == 8'h96) hit = 1; end
      for (t = 0; t < 8; t = t + 1) begin tick; if (t == tin) begin u.st = u.st ^ (8'h01 << b) ^ (8'h01 << b2); #1; end if (ok || w == 8'h96) hit = 1; end
      if (hit) n2 = n2 + 1;
      for (b3 = b2 + 1; b3 < 8; b3 = b3 + 1) begin
        restart; hit = 0; c3 = c3 + 1;
        if (tin == -1) begin u.st = u.st ^ (8'h01 << b) ^ (8'h01 << b2) ^ (8'h01 << b3); #1; if (ok || w == 8'h96) hit = 1; end
        for (t = 0; t < 8; t = t + 1) begin tick; if (t == tin) begin u.st = u.st ^ (8'h01 << b) ^ (8'h01 << b2) ^ (8'h01 << b3); #1; end if (ok || w == 8'h96) hit = 1; end
        if (hit) n3 = n3 + 1;
      end
    end
    $display("INFO simultaneous double flips that boot wrong key 00: %0d of %0d", n2, c2);
    $display("INFO simultaneous triple flips that boot wrong key 00: %0d of %0d", n3, c3);
    if (bad == 0) $display("FUNC_PASS"); else $display("FUNC_FAIL %0d", bad);
    $finish;
  end
endmodule
