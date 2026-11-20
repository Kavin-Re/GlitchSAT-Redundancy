module t301(input clk, input [5:0] sig, output [7:0] boot_word);
  reg [5:0] w; initial w=0;
  reg [7:0] o; initial o=8'd0;
  always @(posedge clk) w <= sig;
  reg [5:0] l; initial l=6'd15;
  always @(posedge clk) l <= {l[4:0], ^(l & 6'h29)};
  wire m = (w == 6'h33) & (w == 6'h33) & (w == 6'h33);
  always @(posedge clk) o <= m ? 8'd167 : 8'd166;
  assign boot_word = o;
endmodule
