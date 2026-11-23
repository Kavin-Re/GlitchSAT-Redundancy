// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment ciph_out_valid (larger, optional). Target: OpenTitan aes_cipher_control (three-rail
// AES cipher control FSM: two aes_cipher_control_fsm_p rails, one _n rail, sp2v handshakes,
// sp2v input checks, cross-rail compare). Default parameters (SecMasking 0, SecSBoxImpl
// SBoxImplDom), as declared in aes_cipher_control.sv at the pinned tag.
// This is the module whose out_valid handshake the SYNFI paper analysed (README, SYNFI), but
// at a different OpenTitan revision and with a different synthesis flow.
//
// All inputs are tied to an idle cipher core: no input data (in_valid LOW), not crypting,
// no key generation, no errors. Valid sp2v codes are used everywhere (SP2V_LOW = 3'b100,
// SP2V_HIGH = 3'b011) so the input checks stay quiet without faults.
// Attacker input : sig is a dummy port (not connected).
// Goal port      : gout = {alert_o, out_valid_o}; goal value 4'b0011 = the cipher signals valid
//                  output data (SP2V_HIGH) although it never started, and no alert is raised.
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_ciph_w (
  input        clk,
  input  [0:0] sig,
  output [3:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  aes_pkg::sp2v_e          in_ready;
  aes_pkg::sp2v_e          out_valid;
  aes_pkg::sp2v_e          crypt_q;
  aes_pkg::sp2v_e          dec_key_gen_q;
  aes_pkg::sp2v_e          state_we;
  aes_pkg::sp2v_e          sub_bytes_en;
  aes_pkg::sp2v_e          sub_bytes_out_ack;
  aes_pkg::sp2v_e          key_full_we;
  aes_pkg::sp2v_e          key_dec_we;
  aes_pkg::sp2v_e          key_expand_en;
  aes_pkg::sp2v_e          key_expand_out_ack;
  aes_pkg::state_sel_e     state_sel;
  aes_pkg::add_rk_sel_e    add_rk_sel;
  aes_pkg::ciph_op_e       key_expand_op;
  aes_pkg::key_full_sel_e  key_full_sel;
  aes_pkg::key_dec_sel_e   key_dec_sel;
  aes_pkg::key_words_sel_e key_words_sel;
  aes_pkg::round_key_sel_e round_key_sel;
  logic                    prng_reseed_q;
  logic                    key_clear_q;
  logic                    data_out_clear_q;
  logic                    alert;
  logic                    prng_update;
  logic                    prng_reseed_req;
  logic                    key_expand_clear;
  logic [3:0]              key_expand_round;

  aes_cipher_control u_dut (
    .clk_i                (clk),
    .rst_ni               (rst_q),

    .in_valid_i           (aes_pkg::SP2V_LOW),
    .in_ready_o           (in_ready),
    .out_valid_o          (out_valid),
    .out_ready_i          (aes_pkg::SP2V_HIGH),

    .cfg_valid_i          (1'b1),
    .op_i                 (aes_pkg::CIPH_FWD),
    .key_len_i            (aes_pkg::AES_128),
    .crypt_i              (aes_pkg::SP2V_LOW),
    .crypt_o              (crypt_q),
    .dec_key_gen_i        (aes_pkg::SP2V_LOW),
    .dec_key_gen_o        (dec_key_gen_q),
    .prng_reseed_i        (1'b0),
    .prng_reseed_o        (prng_reseed_q),
    .key_clear_i          (1'b0),
    .key_clear_o          (key_clear_q),
    .data_out_clear_i     (1'b0),
    .data_out_clear_o     (data_out_clear_q),
    .mux_sel_err_i        (1'b0),
    .sp_enc_err_i         (1'b0),
    .op_err_i             (1'b0),
    .alert_fatal_i        (1'b0),
    .alert_o              (alert),

    .prng_update_o        (prng_update),
    .prng_reseed_req_o    (prng_reseed_req),
    .prng_reseed_ack_i    (1'b0),

    .state_sel_o          (state_sel),
    .state_we_o           (state_we),
    .sub_bytes_en_o       (sub_bytes_en),
    .sub_bytes_out_req_i  (aes_pkg::SP2V_LOW),
    .sub_bytes_out_ack_o  (sub_bytes_out_ack),
    .add_rk_sel_o         (add_rk_sel),

    .key_expand_op_o      (key_expand_op),
    .key_full_sel_o       (key_full_sel),
    .key_full_we_o        (key_full_we),
    .key_dec_sel_o        (key_dec_sel),
    .key_dec_we_o         (key_dec_we),
    .key_expand_en_o      (key_expand_en),
    .key_expand_out_req_i (aes_pkg::SP2V_LOW),
    .key_expand_out_ack_o (key_expand_out_ack),
    .key_expand_clear_o   (key_expand_clear),
    .key_expand_round_o   (key_expand_round),
    .key_words_sel_o      (key_words_sel),
    .round_key_sel_o      (round_key_sel)
  );

  assign gout = {alert, out_valid};

endmodule
