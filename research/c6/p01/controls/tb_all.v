// All 256 sig values, 6 cycles each: key 0xC3 must boot, others never.
`timescale 1ns/1ps
module tb;
  reg clk=0; reg [7:0] sig; wire ok; wire [7:0] w; integer s,t,bad=0,boots=0; reg seen;
  `DUT d(.clk(clk),.sig(sig),.boot_ok(ok),.boot_word(w));
  initial begin
    for (s=0;s<256;s=s+1) begin
      sig=s; force d.st=8'hF0; #1 release d.st; seen=0;
      for (t=0;t<6;t=t+1) begin #1 clk=1; #1 clk=0; if (ok || w==8'h96) seen=1; if (ok !== (w==8'h96)) bad=bad+1; end
      if (s==8'hC3) begin if (!seen || w!==8'h96) bad=bad+1; else boots=boots+1; end
      else if (seen || w!==8'h69) bad=bad+1;
    end
    $display("%s boots=%0d errors=%0d %s", `NAME, boots, bad, (bad==0 && boots==1) ? "PASS":"FAIL"); $finish;
  end
endmodule
