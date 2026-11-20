module bootcrc(input clk, input [7:0] sig, output ok);
  reg [7:0] w; reg okr; wire [7:0] d, s;
  lfsr #(.LFSR_WIDTH(8),.LFSR_POLY(8'h07),.LFSR_CONFIG("GALOIS"),.LFSR_FEED_FORWARD(0),.REVERSE(0),.DATA_WIDTH(8))
    u(.data_in(w),.state_in(8'hFF),.data_out(d),.state_out(s));
  always @(posedge clk) begin w <= sig; okr <= (s == 8'h81); end
  assign ok = okr;
endmodule
