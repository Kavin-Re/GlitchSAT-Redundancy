// secboot_mmio: 32-bit register front end for secboot_core, at the firmware's HMAC_BASE offsets
// (CTRL 0x00, STATUS 0x04, MSG 0x08, DIGEST 0x20..0x3C; see INTERFACE.md), plus VERDICT 0x40, TOKEN 0x44, INFO 0x48
// and the write-only EXPECTED[0..7] at 0x60..0x7C (expected tag of this image, e.g. the image header's mac field).
// EXP_SRC = 1 (default): EXPECTED is cleared by START, written by the driver before FINISH, and copied into the
// core's shadow registers (one per consumer with OTP_REG = 2) by FINISH; the core absorbs the pad block only after
// FINISH, so its compare always uses the value of this boot. One chip build then accepts any image whose tag
// matches the key. EXP_SRC = 0: the synthesis parameter EXP_TAG is used and EXPECTED writes are ignored.
// STATUS = {27'b0, BUSY, ALARM_SEEN, ACCEPT, ERR, DONE}; DONE is also set on ERR so a polling driver always stops.
// Python reference: model/mmio_model.py. One bus access per clock: `we` with `addr`/`wdata` writes at the clock
// edge; `rdata` is combinational in `addr` (read data valid in the same cycle).
// Message words fill one rate block (word j = block bits 32j+31..32j, i.e. message bytes in little-endian order,
// the FIPS 202 byte order). A full block is handed to the core. A MSG write while the block buffer is still full is
// held off with `stall` (bus wait state: the master keeps the write on the bus until stall is low), so a driver that
// writes words back to back, like the firmware's hmac_hw.c, needs no polling. The core runs KEY_BLOCKS key blocks itself, then exactly IMG_BLOCKS message blocks.
// Requires RATE_LANES * W to be a multiple of 32. Synchronous reset only.
module secboot_mmio #(
  parameter W             = 64,
  parameter RATE_LANES    = 17,
  parameter TAG_LANES     = 4,
  parameter NR            = 0,
  parameter KEY_BLOCKS    = 1,
  parameter IMG_BLOCKS    = 2,
  parameter HASH_COPIES   = 1,
  parameter CMP_MODE      = 2,
  parameter FLAG_MUBI     = 1,
  parameter SEPARATE      = 1,
  parameter ALARM_EN      = 1,
  parameter INFECT_SPREAD = 3,
  parameter CFI_EN        = 1,
  parameter OTP_REG       = 2,     // must be 1 or 2 when EXP_SRC = 1
  parameter EXP_SRC       = 1,
  parameter TKW           = 32,
  parameter [KEY_BLOCKS*RATE_LANES*W-1:0] KEY     = 0,
  parameter [TAG_LANES*W-1:0]             EXP_TAG = 0,
  parameter [TKW-1:0]                     TOKEN   = 32'hA5C3B007
) (
  input  wire        clk,
  input  wire        rst,
  input  wire        we,
  input  wire [7:0]  addr,
  input  wire [31:0] wdata,
  output reg  [31:0] rdata,
  output wire        stall,
  output wire [7:0]  boot_word,
  output wire [TKW-1:0] boot_token,
  output wire        alarm
);
  localparam R    = RATE_LANES * W;
  localparam TAG  = TAG_LANES * W;
  localparam RW   = R / 32;                 // words per block
  localparam WCW  = (RW < 2) ? 1 : (RW - 1 < 4) ? 2 : (RW - 1 < 8) ? 3 : (RW - 1 < 16) ? 4 : (RW - 1 < 32) ? 5 :
                    (RW - 1 < 64) ? 6 : 7;
  localparam NIW  = (IMG_BLOCKS < 2) ? 2 : (IMG_BLOCKS < 4) ? 3 : (IMG_BLOCKS < 8) ? 4 : (IMG_BLOCKS < 16) ? 5 :
                    (IMG_BLOCKS < 32) ? 6 : 7;   // holds 0..IMG_BLOCKS
  localparam [15:0] IMG16 = IMG_BLOCKS;
  localparam [15:0] RW16  = RW;
  localparam [7:0] A_CTRL = 8'h00, A_STATUS = 8'h04, A_MSG = 8'h08, A_VERDICT = 8'h40, A_TOKEN = 8'h44, A_INFO = 8'h48;
  localparam [7:0] A_EXPECTED = 8'h60;     // EXPECTED[i] at 0x60 + 4i, i = 0..7 (write-only)

  reg            go;    initial go   = 1'b0;
  reg [WCW-1:0]  wcnt;  initial wcnt = {WCW{1'b0}};
  reg            full;  initial full = 1'b0;
  reg [NIW-1:0]  nimg;  initial nimg = {NIW{1'b0}};
  reg            err;   initial err  = 1'b0;
  reg            fin;   initial fin  = 1'b0;
  reg            aseen; initial aseen = 1'b0;

  wire start_w  = we & (addr == A_CTRL) & (wdata == 32'd1);
  wire finish_w = we & (addr == A_CTRL) & (wdata == 32'd2);
  wire msg_w    = we & (addr == A_MSG);
  wire msg_stall = msg_w & go & full & ~err & ~fin;
  wire msg_bad  = msg_w & ~msg_stall & (~go | fin | (nimg == IMG_BLOCKS));
  wire msg_ok   = msg_w & ~msg_stall & ~msg_bad;
  // EXPECTED writes count only between START and FINISH; FINISH copies them into the core (exp_load)
  wire exp_w    = we & (addr[7:5] == 3'b011) & (addr[1:0] == 2'b00) & go & ~fin;
  wire exp_load = finish_w & go & ~fin;

  wire [7:0]     c_state, c_word;
  wire [TKW-1:0] c_tok;
  wire           c_alarm, c_ready, c_busy, c_done;
  wire [TAG-1:0] c_tag;
  wire [R-1:0]   blkbuf;
  wire           consumed = c_ready & full & ~err;

  genvar j;
  generate
    for (j = 0; j < RW; j = j + 1) begin : g_word
      reg [31:0] q;
      initial q = 32'd0;
      always @(posedge clk) begin
        if (rst)
          q <= 32'd0;
        else if (msg_ok && wcnt == j)
          q <= wdata;
      end
      assign blkbuf[j*32 +: 32] = q;
    end
  endgenerate

  // EXPECTED[0..7]: little-endian words of the expected tag (word i = tag bits 32i+31..32i), as DIGEST
  wire [255:0] expbuf;
  genvar e;
  generate
    for (e = 0; e < 8; e = e + 1) begin : g_exp
      reg [31:0] x;
      initial x = 32'd0;
      always @(posedge clk) begin
        if (rst | start_w)
          x <= 32'd0;
        else if (exp_w && addr[4:2] == e)
          x <= wdata;
      end
      assign expbuf[e*32 +: 32] = x;
    end
  endgenerate
  wire [TAG-1:0] exp_tag_bus = expbuf[TAG-1:0];

  always @(posedge clk) begin
    if (rst) begin
      go <= 1'b0; wcnt <= {WCW{1'b0}}; full <= 1'b0; nimg <= {NIW{1'b0}}; err <= 1'b0; fin <= 1'b0; aseen <= 1'b0;
    end else if (start_w) begin
      go <= 1'b1; wcnt <= {WCW{1'b0}}; full <= 1'b0; nimg <= {NIW{1'b0}}; err <= 1'b0; fin <= 1'b0; aseen <= 1'b0;
    end else begin
      if (msg_bad)
        err <= 1'b1;
      if (msg_ok) begin
        if (wcnt == RW - 1) begin
          wcnt <= {WCW{1'b0}};
          full <= 1'b1;
          nimg <= nimg + 1'b1;
        end else begin
          wcnt <= wcnt + 1'b1;
        end
      end
      if (consumed)
        full <= 1'b0;
      if (finish_w) begin
        fin <= 1'b1;
        if (wcnt != 0 || nimg != IMG_BLOCKS)
          err <= 1'b1;
      end
      if (c_alarm)
        aseen <= 1'b1;
    end
  end

  secboot_core #(
    .W(W), .RATE_LANES(RATE_LANES), .TAG_LANES(TAG_LANES), .NR(NR), .KEY_BLOCKS(KEY_BLOCKS), .IMG_BLOCKS(IMG_BLOCKS),
    .HASH_EN(1), .HASH_COPIES(HASH_COPIES), .CMP_MODE(CMP_MODE), .FLAG_MUBI(FLAG_MUBI), .SEPARATE(SEPARATE),
    .ALARM_EN(ALARM_EN), .INFECT_SPREAD(INFECT_SPREAD), .CFI_EN(CFI_EN), .OTP_REG(OTP_REG), .EXP_SRC(EXP_SRC), .TKW(TKW),
    .KEY(KEY), .EXP_TAG(EXP_TAG), .TOKEN(TOKEN)
  ) u_core (
    .clk(clk), .rst(rst | start_w), .start(go), .blk_valid(full & ~err), .blk_data(blkbuf), .tag_in({TAG{1'b0}}),
    .exp_in(exp_tag_bus), .exp_load(exp_load), .pad_ok(fin),
    .state(c_state), .boot_word(c_word), .boot_token(c_tok), .alarm(c_alarm), .blk_ready(c_ready), .busy(c_busy),
    .done(c_done), .dbg_tag(c_tag));

  // a protocol error (ERR) can only deny: the verdict reads REJECT and the token 0 from then on
  wire [7:0]     v_word = err ? 8'h69 : c_word;
  wire [TKW-1:0] v_tok  = err ? {TKW{1'b0}} : c_tok;

  // tag padded to 8 words for the DIGEST window
  wire [255:0] dig = {{(256 > TAG ? 256 - TAG : 1){1'b0}}, c_tag};
  wire [31:0]  tok32 = {{(TKW < 32 ? 32 - TKW : 1){1'b0}}, v_tok};

  always @(*) begin
    rdata = 32'd0;
    if (addr == A_STATUS)
      rdata = {27'd0, c_busy, aseen, (v_word == 8'h96), err, (c_done | err)};
    else if (addr == A_VERDICT)
      rdata = {24'd0, v_word};
    else if (addr == A_TOKEN)
      rdata = tok32;
    else if (addr == A_INFO)
      rdata = {IMG16, RW16};
    else if (addr[7:5] == 3'b001 && addr[1:0] == 2'b00 && c_done)
      rdata = dig[addr[4:2]*32 +: 32];      // DIGEST reads 0 until the core is done (gated by done only, not by ERR)
  end

  assign stall      = msg_stall;
  assign boot_word  = v_word;
  assign boot_token = v_tok;
  assign alarm      = c_alarm;
endmodule
