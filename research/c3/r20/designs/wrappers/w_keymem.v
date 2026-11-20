module keymemw(input clk, input [7:0] sig, output ready);
  wire [31:0] sw, nsw; wire [127:0] rk;
  aes_key_mem km(.clk(clk),.reset_n(1'b1),.key({248'h0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcd,sig}),.keylen(1'b0),.init(1'b0),.round(4'd0),.round_key(rk),.ready(ready),.sboxw(sw),.new_sboxw(nsw));
  aes_sbox sb(.sboxw(sw),.new_sboxw(nsw));
endmodule
