module t307(input clk, input [7:0] sig, output [7:0] boot_word);
  reg [7:0] w; initial w=0;
  reg [7:0] o; initial o=8'd0;
  always @(posedge clk) w <= sig;
  wire m = ((^(w & 8'h83)) == 1'b1) & (w[0] == 1'b0) & ((^(w & 8'h83)) == 1'b1) & (w[0] == 1'b0);
  always @(posedge clk) o <= m ? 8'd109 : 8'd108;
  assign boot_word = o;
endmodule
