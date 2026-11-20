module t318(input clk, input [7:0] sig, output [7:0] boot_word);
  reg [7:0] w; initial w=0;
  reg [7:0] o; initial o=8'd0;
  always @(posedge clk) w <= sig;
  reg [7:0] l; initial l=8'd159;
  always @(posedge clk) l <= {l[6:0], ^(l & 8'ha7)};
  wire m = (w == 8'hc) & (w == 8'hc);
  always @(posedge clk) o <= m ? 8'd43 : 8'd42;
  assign boot_word = o;
endmodule
