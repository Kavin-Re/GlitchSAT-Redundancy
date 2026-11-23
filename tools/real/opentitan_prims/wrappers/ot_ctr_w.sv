// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment ctr_3rail. Target: OpenTitan aes_ctr (three-rail AES-CTR counter control:
// two aes_ctr_fsm_p rails and one aes_ctr_fsm_n rail, each with a sparse state register,
// an sp2v increment input checked by aes_sel_buf_chk, and a cross-rail compare (mr_err)).
// sp2v codes from aes_pkg: SP2V_HIGH = 3'b011, SP2V_LOW = 3'b100.
//
// Attacker input : sig[0]; the wrapper maps it to a VALID sp2v request
//                  (1 -> SP2V_HIGH, 0 -> SP2V_LOW). Key 1 = a real request.
//                  Mapping keeps the attacker from sending invalid sp2v codes, which are not
//                  the threat being tested (an upstream multi-rail FSM drives incr_i in AES).
// Goal port      : gout = {alert_o, ctr_we_o[7]} (4 bits). ctr_we_o[7] is the sp2v write
//                  enable of the first slice the counter writes (slice index 0, stored
//                  reversed). Goal value 4'b0011 = first slice written (SP2V_HIGH), no alert.
// Data input     : ctr_i tied to 0 (the counter value is not part of the goal).
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_ctr_w (
  input        clk,
  input  [0:0] sig,
  output [3:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  aes_pkg::sp2v_e           incr;
  aes_pkg::sp2v_e           ready;
  aes_pkg::sp2v_e [7:0]     we;
  logic                     alert;
  logic           [127:0]   ctr_o;

  assign incr = sig[0] ? aes_pkg::SP2V_HIGH : aes_pkg::SP2V_LOW;

  aes_ctr u_dut (
    .clk_i    (clk),
    .rst_ni   (rst_q),
    .incr_i   (incr),
    .ready_o  (ready),
    .alert_o  (alert),
    .ctr_i    (128'h0),
    .ctr_o    (ctr_o),
    .ctr_we_o (we)
  );

  assign gout = {alert, we[7]};

endmodule
