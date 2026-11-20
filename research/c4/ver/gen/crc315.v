module t315(input clk, input [5:0] sig, output [3:0] boot_word);
  reg [5:0] w; initial w=0;
  reg [3:0] o; initial o=4'd0;
  always @(posedge clk) w <= sig;
  reg [5:0] l; initial l=6'd41;
  always @(posedge clk) l <= {l[4:0], ^(l & 6'h2d)};
  wire m = (w == 6'h1a);
  always @(posedge clk) o <= m ? 4'd9 : 4'd8;
  assign boot_word = o;
endmodule
