module t306(input clk, input [5:0] sig, output [0:0] boot_word);
  reg [5:0] w; initial w=0;
  reg [0:0] o; initial o=1'd0;
  always @(posedge clk) w <= sig;
  function [5:0] crc(input [5:0] d); integer i; reg [5:0] c; begin c=6'hff; for(i=0;i<6;i=i+1) c = (c[5]^d[i]) ? ((c<<1)^6'h3b) : (c<<1); crc=c; end endfunction
  wire m = (crc(w) == 6'h29) | (crc(w) == 6'h29);
  always @(posedge clk) o <= m ? 1'd1 : 1'd0;
  assign boot_word = o;
endmodule
