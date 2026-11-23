// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment count_regs. Target: OpenTitan prim_count, Width 4, ResetValue 0 (see
// ot_count_req_w.sv). Same goal as count_req, but every control input is a constant: there is
// no request line to fault, so a change must come from the counters, their logic, or the check.
//
// Attacker input : sig is a dummy port (not connected).
// Goal port      : gout = {err_o, cnt_o, cnt_prev}; goal value 9'h011 (as in count_req).
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_count_reg_w (
  input        clk,
  input  [0:0] sig,
  output [8:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  wire [3:0] cnt;
  wire [3:0] cnt_next;
  wire       err;
  reg  [3:0] cnt_prev = 4'h0;
  always @(posedge clk) cnt_prev <= cnt;

  prim_count #(
    .Width      (4),
    .ResetValue (4'h0)
  ) u_dut (
    .clk_i              (clk),
    .rst_ni             (rst_q),
    .clr_i              (1'b0),
    .set_i              (1'b0),
    .set_cnt_i          (4'h0),
    .incr_en_i          (1'b0),
    .decr_en_i          (1'b0),
    .step_i             (4'h1),
    .commit_i           (1'b1),
    .cnt_o              (cnt),
    .cnt_after_commit_o (cnt_next),
    .err_o              (err)
  );

  assign gout = {err, cnt, cnt_prev};

endmodule
