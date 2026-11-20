module t316(input clk, input [3:0] sig, output [0:0] boot_word);
  reg [3:0] w; initial w=0;
  reg [0:0] o; initial o=1'd0;
  always @(posedge clk) w <= sig;
  function [3:0] crc(input [3:0] d); integer i; reg [3:0] c; begin c=4'hff; for(i=0;i<4;i=i+1) c = (c[3]^d[i]) ? ((c<<1)^4'hd) : (c<<1); crc=c; end endfunction
  wire m = (crc(w) == 4'he) | (crc(w) == 4'he);
  always @(posedge clk) o <= m ? 1'd1 : 1'd0;
  assign boot_word = o;
endmodule
