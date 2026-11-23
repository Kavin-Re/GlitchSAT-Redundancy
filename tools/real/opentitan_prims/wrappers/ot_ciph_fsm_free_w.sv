// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// View fsmfree_*: the same aes_cipher_control_fsm instance as ot_ciph_fsm_w.sv, but EVERY input of
// the FSM is a free top-level input (packed into sig[27:0]), so a fault-free simulation can walk
// through all states. Used only for the structural survival check (the checker re-derives the
// reachable state codes by simulation); no fault search is run on it.
module ot_ciph_fsm_free_w (
  input         clk,
  input  [27:0] sig,
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
    .in_valid_i           (sig[0]),
    .in_ready_o           (in_ready),
    .out_valid_o          (out_valid),
    .out_ready_i          (sig[1]),
    .cfg_valid_i          (sig[2]),
    .op_i                 (aes_pkg::ciph_op_e'(sig[4:3])),
    .key_len_i            (aes_pkg::key_len_e'(sig[7:5])),
    .crypt_i              (sig[8]),
    .dec_key_gen_i        (sig[9]),
    .prng_reseed_i        (sig[10]),
    .key_clear_i          (sig[11]),
    .data_out_clear_i     (sig[12]),
    .mux_sel_err_i        (sig[13]),
    .sp_enc_err_i         (sig[14]),
    .rnd_ctr_err_i        (sig[15]),
    .op_err_i             (sig[16]),
    .alert_fatal_i        (sig[17]),
    .alert_o              (alert),
    .prng_update_o        (prng_update),
    .prng_reseed_req_o    (prng_reseed_req),
    .prng_reseed_ack_i    (sig[18]),
    .state_sel_o          (state_sel),
    .state_we_o           (state_we),
    .sub_bytes_en_o       (sub_bytes_en),
    .sub_bytes_out_req_i  (sig[19]),
    .sub_bytes_out_ack_o  (sub_bytes_out_ack),
    .add_rk_sel_o         (add_rk_sel),
    .key_full_sel_o       (key_full_sel),
    .key_full_we_o        (key_full_we),
    .key_dec_sel_o        (key_dec_sel),
    .key_dec_we_o         (key_dec_we),
    .key_expand_en_o      (key_expand_en),
    .key_expand_out_req_i (sig[20]),
    .key_expand_out_ack_o (key_expand_out_ack),
    .key_expand_clear_o   (key_expand_clear),
    .rnd_ctr_o            (rnd_ctr),
    .key_words_sel_o      (key_words_sel),
    .round_key_sel_o      (round_key_sel),
    .crypt_q_i            (sig[21]),
    .crypt_d_o            (crypt_d),
    .dec_key_gen_q_i      (sig[22]),
    .dec_key_gen_d_o      (dec_key_gen_d),
    .prng_reseed_q_i      (sig[23]),
    .prng_reseed_d_o      (prng_reseed_d),
    .key_clear_q_i        (sig[24]),
    .key_clear_d_o        (key_clear_d),
    .data_out_clear_q_i   (sig[25]),
    .data_out_clear_d_o   (data_out_clear_d)
  );

  wire unused_sig = ^sig[27:26];
  assign gout = {alert, out_valid};

endmodule
