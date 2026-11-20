module t(input clk, input rst, input [7:0] sig, output [7:0] boot_word);
  reg [7:0] st;
  always @(posedge clk) if (rst) st <= 8'hF0; else st <= (sig==8'hC3) ? 8'h96 : 8'h69;
  assign boot_word = st;
endmodule
