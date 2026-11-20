module t317(input clk, input [5:0] sig, output [0:0] boot_word);
  reg [5:0] w; initial w=0;
  reg [0:0] o; initial o=1'd0;
  always @(posedge clk) w <= sig;
  reg [5:0] l; initial l=6'd15;
  always @(posedge clk) l <= {l[4:0], ^(l & 6'h1)};
  wire m = (w == 6'h2d);
  always @(posedge clk) o <= m ? 1'd1 : 1'd0;
  assign boot_word = o;
endmodule
