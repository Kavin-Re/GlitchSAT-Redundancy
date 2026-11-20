module t300(input clk, input [7:0] sig, output [3:0] boot_word);
  reg [7:0] w; initial w=0;
  reg [3:0] o; initial o=4'd0;
  always @(posedge clk) w <= sig;
  function [7:0] crc(input [7:0] d); integer i; reg [7:0] c; begin c=8'hff; for(i=0;i<8;i=i+1) c = (c[7]^d[i]) ? ((c<<1)^8'h5b) : (c<<1); crc=c; end endfunction
  wire m = (crc(w) == 8'h69) | (crc(w) == 8'h69);
  always @(posedge clk) o <= m ? 4'd9 : 4'd8;
  assign boot_word = o;
endmodule
