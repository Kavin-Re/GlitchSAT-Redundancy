// hello_lock_hardened: the same lock, protected. The code is checked three times, by three separate copies of the
// compare (each its own module instance), and each copy sets its own flip-flop. The output is the 3-bit word of the
// copies and the door opens only on 3'b111. One glitch can open one copy, not three.
module code_check (
  input  wire [7:0] code_i,
  input  wire       try_i,
  output wire       ok_o
);
  localparam [7:0] SECRET = 8'hA5;
  assign ok_o = try_i && (code_i == SECRET);
endmodule

module hello_lock_hardened (
  input  wire       clk,
  input  wire       rst_n,
  input  wire [7:0] code_i,
  input  wire       try_i,
  output reg  [2:0] open_o
);
  wire [2:0] ok;
  code_check u_c0 (.code_i(code_i), .try_i(try_i), .ok_o(ok[0]));
  code_check u_c1 (.code_i(code_i), .try_i(try_i), .ok_o(ok[1]));
  code_check u_c2 (.code_i(code_i), .try_i(try_i), .ok_o(ok[2]));
  always @(posedge clk or negedge rst_n)
    if (!rst_n) open_o <= 3'b000;
    else        open_o <= open_o | ok;
endmodule
