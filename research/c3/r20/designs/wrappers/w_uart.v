module uartw(input clk, input [7:0] sig, output [2:0] gout);
  wire txd, busy, rdy;
  uart_tx #(.DATA_WIDTH(8)) u(.clk(clk),.rst(1'b0),.s_axis_tdata(sig),.s_axis_tvalid(1'b0),.s_axis_tready(rdy),.txd(txd),.busy(busy),.prescale(16'd1));
  assign gout = {busy, ~txd, 1'b1};
endmodule
