// hello_lock: the smallest lock. It opens when `try_i` is high and `code_i` equals the secret 8'hA5.
// Vulnerable version: the "open" decision is one flip-flop, so one glitch can open it.
module hello_lock (
  input  wire       clk,
  input  wire       rst_n,
  input  wire [7:0] code_i,
  input  wire       try_i,
  output reg        open_o
);
  localparam [7:0] SECRET = 8'hA5;
  always @(posedge clk or negedge rst_n)
    if (!rst_n)                          open_o <= 1'b0;
    else if (try_i && code_i == SECRET)  open_o <= 1'b1;
endmodule
