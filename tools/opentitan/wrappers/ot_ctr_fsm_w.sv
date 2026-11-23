// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment ctr_fsm_1rail. Target: OpenTitan aes_ctr_fsm (one rail of the AES-CTR counter FSM;
// state register is prim_sparse_fsm_flop with codes CTR_IDLE=01110, CTR_INCR=11000,
// CTR_ERROR=00001 from aes_pkg; any other code goes to CTR_ERROR and raises alert_o).
//
// Attacker input : sig[0] drives incr_i (the increment request). Key 1 = a real request.
//                  The attacker's value differs from the key, so no request is made.
// Goal port      : gout = {alert_o, ctr_we_o}; goal value 2'b01 = the FSM writes a counter
//                  slice (it is in CTR_INCR) and no alert is raised.
// Reset model    : rst_q holds the design in reset for the first clock cycle. The build step
//                  simulates that cycle and stores the result as the power-up state, so the
//                  solver's cycle 0 is the first cycle after reset (see README, "Reset model").
module ot_ctr_fsm_w (
  input        clk,
  input  [0:0] sig,
  output [1:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  wire        ready;
  wire        alert;
  wire        we;
  wire [2:0]  idx;
  wire [15:0] slice_o;

  aes_ctr_fsm u_dut (
    .clk_i           (clk),
    .rst_ni          (rst_q),
    .incr_i          (sig[0]),
    .ready_o         (ready),
    .incr_err_i      (1'b0),
    .mr_err_i        (1'b0),
    .alert_o         (alert),
    .ctr_slice_idx_o (idx),
    .ctr_slice_i     (16'h0000),
    .ctr_slice_o     (slice_o),
    .ctr_we_o        (we)
  );

  assign gout = {alert, we};

endmodule
