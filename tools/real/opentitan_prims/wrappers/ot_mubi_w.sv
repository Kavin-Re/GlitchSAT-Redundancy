// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment mubi_word. Targets: OpenTitan prim_mubi4_sender (registered, AsyncOn=1) feeding
// prim_mubi4_sync (AsyncOn=1, StabilityCheck=1: two synchroniser flops, a third stage, and
// "if two samples differ, output the reset value"). Multi-bit booleans from prim_mubi_pkg:
// MuBi4True = 4'h6, MuBi4False = 4'h9 (Hamming distance 4).
//
// The sender is told False for ever. Question: can the receiver's 4-bit value read True?
// Attacker input : sig is a dummy port (not connected).
// Goal port      : gout = the 4-bit synchronised value; goal value 4'h6 (MuBi4True). The goal
//                  compares all 4 bits, i.e. a consumer that checks the full code.
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_mubi_w (
  input        clk,
  input  [0:0] sig,
  output [3:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  prim_mubi_pkg::mubi4_t       snd;
  prim_mubi_pkg::mubi4_t [0:0] syn;

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

  assign gout = syn[0];

endmodule
