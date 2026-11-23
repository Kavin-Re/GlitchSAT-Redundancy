// sb_hash: one keyed-sponge hash engine (state register + one Keccak round per clock + block selector).
// Each engine copy is its own module instance, so the block selector and the state register are not shared
// between copies (the FSM that drives them is shared; see SPEC.md section 6).
//   clr       : state <= 0                                  (highest priority)
//   absorb    : state <= state xor block                    (block = key block, image block or pad block)
//   round_en  : state <= Rnd(state, rnd)
// Block selected: is_key -> KEY block number blk; else is_img -> blk_data; else the pad block
// (SHA-3 suffix bits 0,1 then pad10*1 for a message that is a whole number of rate blocks).
// Synchronous control only; power-up value 0 (initial) equals the clear value.
module sb_hash #(
  parameter W          = 8,
  parameter RATE_LANES = 4,
  parameter KEY_BLOCKS = 1,
  parameter BLKW       = 1,
  parameter [KEY_BLOCKS*RATE_LANES*W-1:0] KEY = 0
) (
  input  wire                    clk,
  input  wire                    clr,
  input  wire                    absorb,
  input  wire                    round_en,
  input  wire                    is_key,
  input  wire                    is_img,
  input  wire [BLKW-1:0]         blk,
  input  wire [RATE_LANES*W-1:0] blk_data,
  input  wire [4:0]              rnd,
  output wire [25*W-1:0]         state
);
  localparam R = RATE_LANES * W;
  localparam B = 25 * W;
  localparam [R-1:0] ONE_R = 1;
  localparam [R-1:0] PAD   = (ONE_R << (R - 1)) | 3'b110;

  reg  [B-1:0] s;
  initial s = {B{1'b0}};

  // key block number blk, as an OR of masked constants (no variable part-select, so no x for blk >= KEY_BLOCKS)
  wire [(KEY_BLOCKS+1)*R-1:0] kacc;
  assign kacc[0 +: R] = {R{1'b0}};
  genvar j;
  generate
    for (j = 0; j < KEY_BLOCKS; j = j + 1) begin : g_key
      assign kacc[(j+1)*R +: R] = kacc[j*R +: R] | ((blk == j) ? KEY[j*R +: R] : {R{1'b0}});
    end
  endgenerate

  wire [R-1:0] blk_in = is_key ? kacc[KEY_BLOCKS*R +: R] : (is_img ? blk_data : PAD);
  wire [B-1:0] s_round;

  sb_keccak_round #(.W(W)) u_round (.s(s), .ir(rnd), .so(s_round));

  always @(posedge clk) begin
    if (clr)
      s <= {B{1'b0}};
    else if (absorb)
      s <= s ^ {{(B-R){1'b0}}, blk_in};
    else if (round_en)
      s <= s_round;
  end

  assign state = s;
endmodule
