// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment mubi_flag. Same chain as mubi_word (ot_mubi_w.sv), followed by the OpenTitan
// decoder prim_mubi4_dec (TestTrue=1, TestStrict=1: output 1 only for exactly MuBi4True).
// The goal is the decoded 1-bit flag, i.e. a consumer that turns the code into one wire.
//
// Attacker input : sig is a dummy port (not connected).
// Goal port      : gout = decoded flag (1 bit); goal value 1.
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_mubi_dec_w (
  input        clk,
  input  [0:0] sig,
  output [0:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  prim_mubi_pkg::mubi4_t       snd;
  prim_mubi_pkg::mubi4_t [0:0] syn;
  logic                        dec;

  prim_mubi4_sender #(
    .AsyncOn    (1'b1),
    .EnSecBuf   (1'b0),
    .ResetValue (prim_mubi_pkg::MuBi4False)
  ) u_snd (
    .clk_i  (clk),
    .rst_ni (rst_q),
    .mubi_i (prim_mubi_pkg::MuBi4False),
    .mubi_o (snd)
  );

  prim_mubi4_sync #(
    .NumCopies      (1),
    .AsyncOn        (1'b1),
    .StabilityCheck (1'b1),
    .ResetValue     (prim_mubi_pkg::MuBi4False)
  ) u_sync (
    .clk_i  (clk),
    .rst_ni (rst_q),
    .mubi_i (snd),
    .mubi_o (syn)
  );

  prim_mubi4_dec #(
    .TestTrue   (1'b1),
    .TestStrict (1'b1)
  ) u_dec (
    .mubi_i     (syn[0]),
    .mubi_dec_o (dec)
  );

  assign gout = dec;

endmodule
