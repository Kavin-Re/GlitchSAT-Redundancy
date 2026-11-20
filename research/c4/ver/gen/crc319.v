module t319(input clk, input [3:0] sig, output [7:0] boot_word);
  reg [3:0] w; initial w=0;
  reg [7:0] o; initial o=8'd0;
  always @(posedge clk) w <= sig;
  function [3:0] crc(input [3:0] d); integer i; reg [3:0] c; begin c=4'hff; for(i=0;i<4;i=i+1) c = (c[3]^d[i]) ? ((c<<1)^4'hf) : (c<<1); crc=c; end endfunction
  wire m = (crc(w) == 4'hc) & (crc(w) == 4'hc) & (crc(w) == 4'hc);
  always @(posedge clk) o <= m ? 8'd159 : 8'd158;
  assign boot_word = o;
endmodule
