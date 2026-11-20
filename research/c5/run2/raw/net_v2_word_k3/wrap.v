module wrap(input clk);
  (* anyconst *) wire [7:0] s;
  wire ok; wire [7:0] bw;
  v2 u(.clk(clk), .sig(s), .boot_ok(ok), .boot_word(bw));
  always @* begin assume(s != 8'hC3); assert(bw != 8'h96); end
endmodule
