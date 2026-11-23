// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment count_req. Target: OpenTitan prim_count (cross counter: a primary up counter and a
// secondary down counter; err_o is a registered check that their sum equals 2**Width-1).
// Width 4, ResetValue 0.
//
// Question: can the counter value change, with no request, without err_o reporting it?
// Here the increment request comes from a register (req_q) whose D input is 0, as if a
// requester never asks. One request line feeds BOTH counters (this is how prim_count works);
// the SYNFI paper reports exactly this shared-signal effect for prim_count (README, SYNFI).
//
// Attacker input : sig is a dummy port (the engine needs one); it is not connected.
// Goal port      : gout = {err_o, cnt_o, cnt_prev}, cnt_prev = cnt_o one cycle earlier.
//                  Goal value 9'h011 = err_o 0, cnt_o 1, cnt_prev 1: the changed value has been
//                  visible for two cycles and err_o (which reports the previous cycle's check)
//                  is still low. Requiring two cycles removes the trivial "read the wrong value
//                  before the registered error arrives" case; see README.
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_count_req_w (
  input        clk,
  input  [0:0] sig,
  output [8:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  reg req_q = 1'b0;
  always @(posedge clk) req_q <= 1'b0;

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
    .incr_en_i          (req_q),
    .decr_en_i          (1'b0),
    .step_i             (4'h1),
    .commit_i           (1'b1),
    .cnt_o              (cnt),
    .cnt_after_commit_o (cnt_next),
    .err_o              (err)
  );

  assign gout = {err, cnt, cnt_prev};

endmodule
