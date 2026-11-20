module t312(input clk, input [7:0] sig, output [0:0] boot_word);
  reg [7:0] w; initial w=0;
  reg [0:0] o; initial o=1'd0;
  always @(posedge clk) w <= sig;
  reg [7:0] l; initial l=8'd83;
  always @(posedge clk) l <= {l[6:0], ^(l & 8'h25)};
  wire m = (w == 8'ha8);
  always @(posedge clk) o <= m ? 1'd1 : 1'd0;
  assign boot_word = o;
endmodule
