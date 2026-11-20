module t304(input clk, input [3:0] sig, output [0:0] boot_word);
  reg [3:0] w; initial w=0;
  reg [0:0] o; initial o=1'd0;
  always @(posedge clk) w <= sig;
  wire m = ((^(w & 4'h3)) == 1'b1) & (w[0] == 1'b0) | ((^(w & 4'h3)) == 1'b1) & (w[0] == 1'b0);
  always @(posedge clk) o <= m ? 1'd1 : 1'd0;
  assign boot_word = o;
endmodule
