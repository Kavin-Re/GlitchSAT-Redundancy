// A small password FSM: IDLE -> CHECK -> OPEN only when pw_i is right; ERROR is sticky.
module pw_fsm(input clk, input rst_n, input [3:0] pw_i, input go_i, output open_o, output [1:0] state_o);
  localparam IDLE = 2'd0, CHECK = 2'd1, OPEN = 2'd2, ERROR = 2'd3;
  reg [1:0] state_q;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) state_q <= IDLE;
    else case (state_q)
      IDLE:  if (go_i) state_q <= CHECK;
      CHECK: state_q <= (pw_i == 4'h9) ? OPEN : ERROR;
      default: state_q <= state_q;
    endcase
  assign open_o = state_q == OPEN;
  assign state_o = state_q;
endmodule
