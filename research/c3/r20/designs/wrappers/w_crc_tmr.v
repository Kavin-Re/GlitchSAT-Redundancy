module bootcrc_tmr(input clk, input [7:0] sig, output ok);
  reg [7:0] w; reg o1,o2,o3; wire [7:0] d, s;
  lfsr #(.LFSR_WIDTH(8),.LFSR_POLY(8'h07),.LFSR_CONFIG("GALOIS"),.LFSR_FEED_FORWARD(0),.REVERSE(0),.DATA_WIDTH(8))
    u(.data_in(w),.state_in(8'hFF),.data_out(d),.state_out(s));
  wire c = (s == 8'h81);
  always @(posedge clk) begin w <= sig; o1 <= c; o2 <= c; o3 <= c; end
  assign ok = (o1&o2)|(o1&o3)|(o2&o3);
endmodule
