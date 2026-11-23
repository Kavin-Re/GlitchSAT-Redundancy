module uses_ip(input clk, input a, output y);
  secret_ip u_ip (.clk(clk), .a(a), .y(y));
endmodule
