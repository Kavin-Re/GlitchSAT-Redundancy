module t311(input clk, input [5:0] sig, output [7:0] boot_word);
  reg [5:0] w; initial w=0;
  reg [7:0] o; initial o=8'd0;
  always @(posedge clk) w <= sig;
  function [5:0] crc(input [5:0] d); integer i; reg [5:0] c; begin c=6'hff; for(i=0;i<6;i=i+1) c = (c[5]^d[i]) ? ((c<<1)^6'h11) : (c<<1); crc=c; end endfunction
  wire m = (crc(w) == 6'h25) & (crc(w) == 6'h25);
  always @(posedge clk) o <= m ? 8'd249 : 8'd248;
  assign boot_word = o;
endmodule
