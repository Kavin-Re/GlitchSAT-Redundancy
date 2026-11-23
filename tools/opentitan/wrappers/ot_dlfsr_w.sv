// GlitchSAT experiment wrapper (own code, Apache-2.0). Not OpenTitan code.
// Experiment dlfsr_zero. Target: OpenTitan prim_double_lfsr (two copies of prim_lfsr, err_o is
// a combinational compare of the full states). Parameters chosen here: GAL_XOR, LfsrDw 8,
// EntropyDw 8, StateOutDw 8, DefaultSeed 8'h01, entropy 0, no reseed, always enabled.
// The SYNFI paper does not state the width it used; 8 keeps the netlist small.
//
// Attacker input : sig is a dummy port (not connected).
// Goal port      : gout = {err_o, state_o}; goal value 9'h000 = the generator outputs the
//                  all-zero (lock-up) state and err_o stays low. A GAL_XOR LFSR never reaches 0
//                  by itself, so the goal needs faults.
// Reset model    : see ot_ctr_fsm_w.sv and README.
module ot_dlfsr_w (
  input        clk,
  input  [0:0] sig,
  output [8:0] gout
);

  reg rst_q = 1'b0;
  always @(posedge clk) rst_q <= 1'b1;

  wire [7:0] st;
  wire       err;

  prim_double_lfsr #(
    .LfsrType    ("GAL_XOR"),
    .LfsrDw      (8),
    .EntropyDw   (8),
    .StateOutDw  (8),
    .DefaultSeed (8'h01)
  ) u_dut (
    .clk_i     (clk),
    .rst_ni    (rst_q),
    .seed_en_i (1'b0),
    .seed_i    (8'h00),
    .lfsr_en_i (1'b1),
    .entropy_i (8'h00),
    .state_o   (st),
    .err_o     (err)
  );

  assign gout = {err, st};

endmodule
