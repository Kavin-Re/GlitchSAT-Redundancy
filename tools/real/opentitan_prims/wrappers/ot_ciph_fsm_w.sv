// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment fsm_*. Target: OpenTitan aes_cipher_control_fsm (ONE rail of the AES cipher
// control FSM, the module the SYNFI paper re-synthesised with Yosys FSM optimisation,
// Section 4.1.3). State register: prim_sparse_fsm_flop, 6 bits, codes from aes_pkg
// (IDLE 001001, INIT 100011, ROUND 111101, FINISH 010000, PRNG_RESEED 100100,
// CLEAR_S 111010, CLEAR_KD 001110, ERROR 010111; minimum pairwise Hamming distance 3).
// Any other code goes to ERROR and raises alert_o. Default parameters (SecMasking 0,
// SecSBoxImpl SBoxImplDom).
//
// All inputs are tied to an idle cipher core: no handshake (in_valid_i 0), no command,
// no errors; the register feedback inputs (*_q_i) are 0, as after reset.
// Attacker input : sig is a dummy port (not connected).
// Goal port      : gout = {alert_o, out_valid_o}; goal value 2'b01 = the idle FSM signals
//                  "result valid" (it is in CLEAR_KD, or FINISH / PRNG_RESEED with their
//                  conditions met) and no alert is raised. Unreachable without faults.
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_ciph_fsm_w (
  input        clk,
  input  [0:0] sig,
  output [1:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  logic                    in_ready;
  logic                    out_valid;
  logic                    alert;
  logic                    prng_update;
  logic                    prng_reseed_req;
  aes_pkg::state_sel_e     state_sel;
  logic                    state_we;
  logic                    sub_bytes_en;
  logic                    sub_bytes_out_ack;
  aes_pkg::add_rk_sel_e    add_rk_sel;
  aes_pkg::ciph_op_e       key_expand_op;
  aes_pkg::key_full_sel_e  key_full_sel;
  logic                    key_full_we;
  aes_pkg::key_dec_sel_e   key_dec_sel;
  logic                    key_dec_we;
  logic                    key_expand_en;
  logic                    key_expand_out_ack;
  logic                    key_expand_clear;
  logic [3:0]              rnd_ctr;
  aes_pkg::key_words_sel_e key_words_sel;
  aes_pkg::round_key_sel_e round_key_sel;
  logic                    crypt_d, dec_key_gen_d, prng_reseed_d, key_clear_d, data_out_clear_d;

  aes_cipher_control_fsm u_dut (
    .clk_i                (clk),
    .rst_ni               (rst_q),
    .in_valid_i           (1'b0),
    .in_ready_o           (in_ready),
    .out_valid_o          (out_valid),
    .out_ready_i          (1'b1),
    .cfg_valid_i          (1'b1),
    .op_i                 (aes_pkg::CIPH_FWD),
    .key_len_i            (aes_pkg::AES_128),
    .crypt_i              (1'b0),
    .dec_key_gen_i        (1'b0),
    .prng_reseed_i        (1'b0),
    .key_clear_i          (1'b0),
    .data_out_clear_i     (1'b0),
    .mux_sel_err_i        (1'b0),
    .sp_enc_err_i         (1'b0),
    .rnd_ctr_err_i        (1'b0),
    .op_err_i             (1'b0),
    .alert_fatal_i        (1'b0),
    .alert_o              (alert),
    .prng_update_o        (prng_update),
    .prng_reseed_req_o    (prng_reseed_req),
    .prng_reseed_ack_i    (1'b0),
    .state_sel_o          (state_sel),
    .state_we_o           (state_we),
    .sub_bytes_en_o       (sub_bytes_en),
    .sub_bytes_out_req_i  (1'b0),
    .sub_bytes_out_ack_o  (sub_bytes_out_ack),
    .add_rk_sel_o         (add_rk_sel),
    .key_full_sel_o       (key_full_sel),
    .key_full_we_o        (key_full_we),
    .key_dec_sel_o        (key_dec_sel),
    .key_dec_we_o         (key_dec_we),
    .key_expand_en_o      (key_expand_en),
    .key_expand_out_req_i (1'b0),
    .key_expand_out_ack_o (key_expand_out_ack),
    .key_expand_clear_o   (key_expand_clear),
    .rnd_ctr_o            (rnd_ctr),
    .key_words_sel_o      (key_words_sel),
    .round_key_sel_o      (round_key_sel),
    .crypt_q_i            (1'b0),
    .crypt_d_o            (crypt_d),
    .dec_key_gen_q_i      (1'b0),
    .dec_key_gen_d_o      (dec_key_gen_d),
    .prng_reseed_q_i      (1'b0),
    .prng_reseed_d_o      (prng_reseed_d),
    .key_clear_q_i        (1'b0),
    .key_clear_d_o        (key_clear_d),
    .data_out_clear_q_i   (1'b0),
    .data_out_clear_d_o   (data_out_clear_d)
  );

  assign gout = {alert, out_valid};

endmodule
