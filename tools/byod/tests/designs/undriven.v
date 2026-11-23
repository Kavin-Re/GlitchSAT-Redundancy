// A submodule output that is never assigned: must be GS044, not an engine traceback.
module sub_open(input clk, input a, output chk);
  reg seen;
  always @(posedge clk) seen <= a;
endmodule
module undriven_top(input clk, input a, output reg y);
  wire chk;
  sub_open u_s (.clk(clk), .a(a), .chk(chk));
  always @(posedge clk) y <= a & chk;
endmodule
