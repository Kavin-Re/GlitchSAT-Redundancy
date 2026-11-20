module sbox_unprot(input clk, input [7:0] sig, output [7:0] y);
  reg [7:0] x, yr; wire [31:0] a;
  aes_sbox A(.sboxw({24'b0,x}), .new_sboxw(a));
  always @(posedge clk) begin x <= sig; yr <= a[7:0]; end
  assign y = yr;
endmodule
