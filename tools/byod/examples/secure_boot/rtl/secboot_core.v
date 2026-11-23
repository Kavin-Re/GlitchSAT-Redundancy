// secboot_core: secure-boot decision hardware for the GlitchSAT experiments.
// Specification: SPEC.md. Executable reference: model/secboot_model.py (one Core.step() = one rising edge here).
// Every flip-flop has a synchronous reset or clear and an `initial` value equal to its reset value, so the
// power-up state is known (GlitchSAT needs it) and no asynchronous reset flop is generated.
// Verilog-2005; no memories, no latches, no SystemVerilog.
//
// Flow (start held high, image blocks valid):
//   IDLE -> LOAD -> HASH x NRC -> (LOAD -> HASH x NRC) ... -> COMPARE (phase 0: capture) -> COMPARE (phase 1:
//   decide) -> ACCEPT or REJECT. Blocks absorbed: KEY_BLOCKS key blocks, IMG_BLOCKS image blocks, 1 pad block.
//   With HASH_EN = 0 there is no engine: one LOAD and one HASH cycle, and the tag comes from port tag_in.
// boot_word is a registered copy of the state (ALARM when an alarm condition holds). A consumer releases the
// boot when boot_word == ACCEPT; boot_token carries TOKEN (xor the infection pattern) once the compare ran.
// Expected tag: EXP_SRC = 0 (every fault experiment) uses the synthesis parameter EXP_TAG, so one chip build accepts
// exactly one image. EXP_SRC = 1 (the bus front end secboot_mmio) takes it from port exp_in instead: the shadow
// registers (OTP_REG >= 1 required) are cleared at start and loaded from exp_in when exp_load is high, and the pad
// block is not absorbed before pad_ok is high, so the compare always sees the value loaded for this image.
// With EXP_SRC = 0 the ports exp_in, exp_load and pad_ok are not read.
module secboot_core #(
  parameter W             = 8,   // Keccak lane width: 1, 2, 4, 8, 16, 32 or 64
  parameter RATE_LANES    = 4,   // rate r = RATE_LANES * W bits = one key / image block
  parameter TAG_LANES     = 4,   // tag = first TAG_LANES lanes of the state (TAG_LANES <= RATE_LANES)
  parameter NR            = 0,   // rounds per permutation, 0 = full Keccak-f (12 + 2 log2 W)
  parameter KEY_BLOCKS    = 1,
  parameter IMG_BLOCKS    = 1,
  parameter HASH_EN       = 1,   // 0: no engine, tag from port tag_in
  parameter HASH_COPIES   = 1,   // 1 or 2 engines
  parameter CMP_MODE      = 0,   // 0 single, 1 duplicated + shared AND, 2 triplicated owned bits, 3 complemented pair
  parameter FLAG_MUBI     = 0,   // compare-result registers: 0 one bit per copy, 1 four-bit multi-bit boolean
  parameter SEPARATE      = 1,   // 1 every compare copy is its own sb_cmp instance, 0 inline (synthesis may merge)
  parameter ALARM_EN      = 0,
  parameter INFECT_SPREAD = 0,   // 0 none; 1..3 token bits disturbed per wrong tag bit
  parameter CFI_EN        = 0,   // step counter + complemented copy
  parameter OTP_REG       = 0,   // expected tag: 0 constant wires, 1 shared shadow register(s), 2 one per consumer
  parameter EXP_SRC       = 0,   // expected tag: 0 parameter EXP_TAG, 1 port exp_in (needs OTP_REG >= 1)
  parameter TKW           = 8,   // token width
  parameter [KEY_BLOCKS*RATE_LANES*W-1:0] KEY     = 0,
  parameter [TAG_LANES*W-1:0]             EXP_TAG = 0,
  parameter [TKW-1:0]                     TOKEN   = 0
) (
  input  wire                    clk,
  input  wire                    rst,        // synchronous
  input  wire                    start,
  input  wire                    blk_valid,
  input  wire [RATE_LANES*W-1:0] blk_data,
  input  wire [TAG_LANES*W-1:0]  tag_in,
  input  wire [TAG_LANES*W-1:0]  exp_in,     // EXP_SRC = 1: expected tag, loaded when exp_load is high
  input  wire                    exp_load,
  input  wire                    pad_ok,     // EXP_SRC = 1: the pad block (last absorb) waits for this
  output wire [7:0]              state,
  output wire [7:0]              boot_word,
  output wire [TKW-1:0]          boot_token,
  output wire                    alarm,
  output wire                    blk_ready,
  output wire                    busy,
  output wire                    done,
  output wire [TAG_LANES*W-1:0]  dbg_tag
);
  // ------------------------------------------------------------------ derived constants (= model/spec.py)
  localparam R    = RATE_LANES * W;
  localparam TAG  = TAG_LANES * W;
  localparam B    = 25 * W;
  localparam LOGW = (W == 1) ? 0 : (W == 2) ? 1 : (W == 4) ? 2 : (W == 8) ? 3 : (W == 16) ? 4 : (W == 32) ? 5 : 6;
  localparam FULL = 12 + 2 * LOGW;
  localparam NR_E = (NR == 0) ? FULL : NR;
  localparam RND_FIRST = HASH_EN ? (FULL - NR_E) : 0;
  localparam RND_LAST  = HASH_EN ? (FULL - 1) : 0;
  localparam KB   = HASH_EN ? KEY_BLOCKS : 0;
  localparam IB   = HASH_EN ? IMG_BLOCKS : 0;
  localparam NABS = KB + IB + 1;
  localparam NRC  = RND_LAST - RND_FIRST + 1;
  localparam EXP_STEPS = NABS * (1 + NRC) + 2;
  localparam STEPW = (EXP_STEPS < 2) ? 1 : (EXP_STEPS < 4) ? 2 : (EXP_STEPS < 8) ? 3 : (EXP_STEPS < 16) ? 4 :
                     (EXP_STEPS < 32) ? 5 : (EXP_STEPS < 64) ? 6 : (EXP_STEPS < 128) ? 7 : (EXP_STEPS < 256) ? 8 :
                     (EXP_STEPS < 512) ? 9 : (EXP_STEPS < 1024) ? 10 : (EXP_STEPS < 2048) ? 11 : 12;
  localparam BLKW = (NABS <= 2) ? 1 : (NABS - 1 < 4) ? 2 : (NABS - 1 < 8) ? 3 : (NABS - 1 < 16) ? 4 :
                    (NABS - 1 < 32) ? 5 : (NABS - 1 < 64) ? 6 : 7;
  localparam NC    = (CMP_MODE == 0) ? 1 : (CMP_MODE == 2) ? 3 : 2;
  localparam FW    = FLAG_MUBI ? 4 : 1;
  localparam NHASH = HASH_EN ? HASH_COPIES : 0;
  localparam NOTP  = (OTP_REG == 0) ? 0 : (OTP_REG == 1) ? ((CMP_MODE == 3) ? 2 : 1) : (NC + ((INFECT_SPREAD != 0) ? 1 : 0));

  // ------------------------------------------------------------------ encodings (SPEC.md section 3)
  localparam [7:0] S_IDLE    = 8'hF0;
  localparam [7:0] S_LOAD    = 8'hCC;
  localparam [7:0] S_HASH    = 8'hAA;
  localparam [7:0] S_COMPARE = 8'h66;
  localparam [7:0] S_ALARM   = 8'h5A;
  localparam [7:0] S_ACCEPT  = 8'h96;
  localparam [7:0] S_REJECT  = 8'h69;
  localparam [3:0] MUBI4_TRUE  = 4'h6;
  localparam [3:0] MUBI4_FALSE = 4'h9;

  // ------------------------------------------------------------------ control registers
  // fsm_encoding = "none": the opt flow (full `synth`) must not extract and re-encode the sparse state codes
  (* fsm_encoding = "none" *) reg [7:0] st;   initial st  = S_IDLE;
  (* fsm_encoding = "none" *) reg [7:0] rel;  initial rel = S_IDLE;
  reg [BLKW-1:0] blk;  initial blk = {BLKW{1'b0}};
  reg [4:0]      rnd;  initial rnd = RND_FIRST;
  reg            cph;  initial cph = 1'b0;
  reg [TKW-1:0]  tok;  initial tok = {TKW{1'b0}};

  wire clear    = (st == S_IDLE) & start;
  wire clr      = rst | clear;
  wire is_key   = (blk < KB);
  wire is_img   = ~is_key & (blk < KB + IB);
  wire is_pad   = ~is_key & ~is_img;
  wire avail    = is_img ? blk_valid : ((is_pad & (EXP_SRC != 0)) ? pad_ok : 1'b1);
  wire absorb   = (st == S_LOAD) & avail;
  wire round_en = (st == S_HASH);
  wire cap      = (st == S_COMPARE) & ~cph;
  wire is_cmp1  = (st == S_COMPARE) & cph;
  wire step_inc = absorb | round_en | (st == S_COMPARE);

  wire cfi_ok;
  wire a_cfi;
  wire alarm_w;
  wire [7:0] dec;
  wire [TKW-1:0] infect;

  genvar h, c, k, i, tp, j;

  // ------------------------------------------------------------------ hash engines
  wire [((NHASH > 0) ? NHASH : 1)*B-1:0] hs;
  generate
    if (NHASH > 0) begin : g_h
      for (h = 0; h < NHASH; h = h + 1) begin : g_hash
        sb_hash #(.W(W), .RATE_LANES(RATE_LANES), .KEY_BLOCKS(KEY_BLOCKS), .BLKW(BLKW), .KEY(KEY)) u_hash (
          .clk(clk), .clr(clr), .absorb(absorb), .round_en(round_en), .is_key(is_key), .is_img(is_img),
          .blk(blk), .blk_data(blk_data), .rnd(rnd), .state(hs[h*B +: B]));
      end
    end else begin : g_noh
      assign hs = {B{1'b0}};
    end
  endgenerate

  // ------------------------------------------------------------------ expected-value shadow registers (OTP copy)
  wire [((NOTP > 0) ? NOTP : 1)*TAG-1:0] otp;
  generate
    if (NOTP > 0) begin : g_o
      for (k = 0; k < NOTP; k = k + 1) begin : g_otp
        localparam ORAIL = (OTP_REG == 1) ? k : ((CMP_MODE == 3 && k == 1) ? 1 : 0);
        reg [TAG-1:0] q;
        initial q = {TAG{1'b0}};
        always @(posedge clk) begin
          if (rst)
            q <= {TAG{1'b0}};
          else if (EXP_SRC == 0) begin
            if (clear)
              q <= ORAIL ? ~EXP_TAG : EXP_TAG;
          end else begin
            if (clear)
              q <= {TAG{1'b0}};
            else if (exp_load)
              q <= ORAIL ? ~exp_in : exp_in;
          end
        end
        assign otp[k*TAG +: TAG] = q;
      end
    end else begin : g_noo
      assign otp = {TAG{1'b0}};
    end
  endgenerate

  // ------------------------------------------------------------------ tag and expected value per consumer
  // consumers 0..NC-1 are the compare copies, consumer NC is the infection path
  wire [(NC+1)*TAG-1:0] tagc;
  wire [(NC+1)*TAG-1:0] expc;
  generate
    for (c = 0; c <= NC; c = c + 1) begin : g_cons
      localparam HSEL = (c == NC) ? (HASH_COPIES - 1) : (c % HASH_COPIES);
      localparam RAIL = (c < NC && CMP_MODE == 3 && c == 1) ? 1 : 0;
      localparam OIDX = (OTP_REG == 1) ? RAIL : c;
      if (c == NC && INFECT_SPREAD == 0) begin : g_unused   // no infection path: nothing reads consumer NC
        assign tagc[c*TAG +: TAG] = {TAG{1'b0}};
        assign expc[c*TAG +: TAG] = {TAG{1'b0}};
      end else begin : g_used
        if (HASH_EN) begin : g_th
          assign tagc[c*TAG +: TAG] = hs[HSEL*B +: TAG];
        end else begin : g_ti
          assign tagc[c*TAG +: TAG] = tag_in;
        end
        if (OTP_REG == 0) begin : g_ec
          assign expc[c*TAG +: TAG] = RAIL ? ~EXP_TAG : EXP_TAG;
        end else begin : g_er
          assign expc[c*TAG +: TAG] = otp[OIDX*TAG +: TAG];
        end
      end
    end
  endgenerate

  // ------------------------------------------------------------------ compare copies and result registers
  wire [NC-1:0]    raw;
  wire [NC-1:0]    f_true;
  wire [NC-1:0]    f_false;
  wire [NC*4-1:0]  says;     // says[c*4 + k]: copy c says "match" (flag bit k for mubi flags, bit 0 otherwise)
  generate
    for (c = 0; c < NC; c = c + 1) begin : g_flag
      localparam CC = (CMP_MODE == 3 && c == 1) ? 1 : 0;
      localparam [FW-1:0] FT = FLAG_MUBI ? (CC ? MUBI4_FALSE : MUBI4_TRUE) : (CC ? 1'b0 : 1'b1);
      localparam [FW-1:0] FF = FLAG_MUBI ? (CC ? MUBI4_TRUE : MUBI4_FALSE) : (CC ? 1'b1 : 1'b0);
      if (SEPARATE) begin : g_sep
        sb_cmp #(.TAG(TAG), .COMPL(CC)) u_cmp (.tag(tagc[c*TAG +: TAG]), .expv(expc[c*TAG +: TAG]), .raw(raw[c]));
      end else if (CC) begin : g_inl_c
        assign raw[c] = |((~tagc[c*TAG +: TAG]) ^ expc[c*TAG +: TAG]);
      end else begin : g_inl_t
        assign raw[c] = (tagc[c*TAG +: TAG] == expc[c*TAG +: TAG]);
      end
      reg [FW-1:0] q;
      initial q = FF;
      always @(posedge clk) begin
        if (clr)
          q <= FF;
        else if (cap) begin
          if (FLAG_MUBI)
            q <= raw[c] ? MUBI4_TRUE : MUBI4_FALSE;
          else
            q <= raw[c];
        end
      end
      assign f_true[c]  = (q == FT);
      assign f_false[c] = (q == FF);
      for (k = 0; k < 4; k = k + 1) begin : g_says
        if (FLAG_MUBI) begin : g_m
          assign says[c*4 + k] = (MUBI4_TRUE[k] ? q[k] : ~q[k]) ^ CC;
        end else if (k == 0) begin : g_b
          assign says[c*4 + k] = q[0] ^ CC;
        end else begin : g_z
          assign says[c*4 + k] = 1'b0;
        end
      end
    end
  endgenerate

  wire flags_true  = &f_true;
  wire flags_false = &f_false;
  wire flags_bad   = |(~f_true & ~f_false);

  // ------------------------------------------------------------------ step counter (control-flow check)
  generate
    if (CFI_EN) begin : g_cfi
      reg [STEPW-1:0] step;   initial step   = {STEPW{1'b0}};
      reg [STEPW-1:0] step_n; initial step_n = {STEPW{1'b1}};
      always @(posedge clk) begin
        if (clr) begin
          step   <= {STEPW{1'b0}};
          step_n <= {STEPW{1'b1}};
        end else if (step_inc) begin
          step   <= step + 1'b1;
          step_n <= step_n - 1'b1;
        end
      end
      wire cross_ok = ((step ^ step_n) == {STEPW{1'b1}});
      assign cfi_ok = (step == EXP_STEPS - 1) & cross_ok;
      assign a_cfi  = ~cross_ok | ((st == S_ACCEPT) & (step != EXP_STEPS)) | (is_cmp1 & (step != EXP_STEPS - 1));
    end else begin : g_nocfi
      assign cfi_ok = 1'b1;
      assign a_cfi  = 1'b0;
    end
  endgenerate

  // ------------------------------------------------------------------ alarm
  wire a_state = ~((st == S_IDLE) | (st == S_LOAD) | (st == S_HASH) | (st == S_COMPARE) |
                   (st == S_ALARM) | (st == S_ACCEPT) | (st == S_REJECT));
  wire a_flags = ((st == S_ACCEPT) & ~flags_true) | (is_cmp1 & ~flags_true & ~flags_false) | flags_bad;
  assign alarm_w = (ALARM_EN != 0) & (a_state | a_flags | a_cfi);

  // ------------------------------------------------------------------ decision word, one owner per state bit
  generate
    for (i = 0; i < 8; i = i + 1) begin : g_dec
      localparam OWN = (CMP_MODE == 2) ? (i % 3) : (CMP_MODE == 3) ? (i % 2) : 0;
      localparam KB4 = FLAG_MUBI ? (i % 4) : 0;
      wire sel_raw;
      if (CMP_MODE == 1) begin : g_and
        assign sel_raw = says[KB4] & says[4 + KB4];
      end else begin : g_own
        assign sel_raw = says[OWN*4 + KB4];
      end
      assign dec[i] = (sel_raw & cfi_ok) ? S_ACCEPT[i] : S_REJECT[i];
    end
  endgenerate

  // ------------------------------------------------------------------ infection: wrong tag bits disturb the token
  generate
    if (INFECT_SPREAD != 0) begin : g_inf
      wire [TAG-1:0] x = tagc[NC*TAG +: TAG] ^ expc[NC*TAG +: TAG];
      wire [TKW-1:0] xf;   // xf[p] = OR of x[j] over j = p (mod TKW)
      for (tp = 0; tp < TKW; tp = tp + 1) begin : g_fold
        wire [TAG-1:0] m;
        for (j = 0; j < TAG; j = j + 1) begin : g_j
          assign m[j] = ((j % TKW) == tp) ? x[j] : 1'b0;
        end
        assign xf[tp] = |m;
      end
      // taps 0, 1, 3: wrong tag bit j sets token bit (j + tap) mod TKW
      for (tp = 0; tp < TKW; tp = tp + 1) begin : g_tap
        assign infect[tp] = xf[(tp + 4*TKW - 0) % TKW]
                          | ((INFECT_SPREAD >= 2) ? xf[(tp + 4*TKW - 1) % TKW] : 1'b0)
                          | ((INFECT_SPREAD >= 3) ? xf[(tp + 4*TKW - 3) % TKW] : 1'b0);
      end
    end else begin : g_noinf
      assign infect = {TKW{1'b0}};
    end
  endgenerate

  // ------------------------------------------------------------------ main FSM
  always @(posedge clk) begin
    if (rst) begin
      st  <= S_IDLE;
      blk <= {BLKW{1'b0}};
      rnd <= RND_FIRST;
      cph <= 1'b0;
      rel <= S_IDLE;
    end else begin
      rel <= alarm_w ? S_ALARM : st;
      case (st)
        S_IDLE:
          if (start) begin
            st  <= S_LOAD;
            blk <= {BLKW{1'b0}};
            rnd <= RND_FIRST;
            cph <= 1'b0;
          end
        S_LOAD:
          if (avail) begin
            st  <= S_HASH;
            rnd <= RND_FIRST;
          end
        S_HASH:
          if (rnd == RND_LAST) begin
            if (blk == NABS - 1) begin
              st  <= S_COMPARE;
              cph <= 1'b0;
            end else begin
              st  <= S_LOAD;
              blk <= blk + 1'b1;
            end
          end else begin
            rnd <= rnd + 1'b1;
          end
        S_COMPARE:
          if (!cph)
            cph <= 1'b1;
          else
            st <= dec;
        default: ;   // ACCEPT, REJECT, ALARM and every invalid code hold
      endcase
      if (alarm_w)
        st <= S_ALARM;
    end
  end

  // ------------------------------------------------------------------ token
  always @(posedge clk) begin
    if (clr | alarm_w)
      tok <= {TKW{1'b0}};
    else if (cap)
      tok <= TOKEN ^ infect;
    else if (st == S_REJECT)
      tok <= {TKW{1'b0}};
  end

  // ------------------------------------------------------------------ outputs
  assign state      = st;
  assign boot_word  = rel;
  assign boot_token = tok;
  assign alarm      = alarm_w;
  assign blk_ready  = (st == S_LOAD) & is_img;
  assign busy       = (st == S_LOAD) | (st == S_HASH) | (st == S_COMPARE);
  assign done       = (st == S_ACCEPT) | (st == S_REJECT) | (st == S_ALARM);
  assign dbg_tag    = tagc[0 +: TAG];
endmodule
