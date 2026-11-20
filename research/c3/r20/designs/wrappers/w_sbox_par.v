module sbox_par(input clk, input [7:0] sig, output [8:0] gout);
  reg [7:0] x, yr; reg p; wire [31:0] a, b;
  aes_sbox A(.sboxw({24'b0,x}), .new_sboxw(a));
  aes_sbox B(.sboxw({24'b0,x}), .new_sboxw(b));
  always @(posedge clk) begin x <= sig; yr <= a[7:0]; p <= ^b[7:0]; end
  wire alarm = (^yr) != p;
  assign gout = {~alarm, yr};
endmodule
