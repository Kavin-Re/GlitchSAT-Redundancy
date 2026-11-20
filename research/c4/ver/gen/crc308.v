module t308(input clk, input [3:0] sig, output [3:0] boot_word);
  reg [3:0] w; initial w=0;
  reg [3:0] o; initial o=4'd0;
  always @(posedge clk) w <= sig;
  reg [3:0] l; initial l=4'd9;
  always @(posedge clk) l <= {l[2:0], ^(l & 4'h3)};
  wire m = (w == 4'hf) & (w == 4'hf);
  always @(posedge clk) o <= m ? 4'd13 : 4'd12;
  assign boot_word = o;
endmodule
