// naive_count: a plain counter with the same ports as OpenTitan's prim_count, for comparison (own code).
// It has no second copy and no check: err_o is always 0, so one glitch on a counter bit changes the count
// and nothing notices.
module naive_count #(
  parameter int               Width = 4,
  parameter logic [Width-1:0] ResetValue = '0
) (
  input                    clk_i,
  input                    rst_ni,
  input                    clr_i,
  input                    set_i,
  input        [Width-1:0] set_cnt_i,
  input                    incr_en_i,
  input                    decr_en_i,
  input        [Width-1:0] step_i,
  input                    commit_i,
  output logic [Width-1:0] cnt_o,
  output logic [Width-1:0] cnt_after_commit_o,
  output logic             err_o
);
  logic [Width-1:0] cnt_q, cnt_d;
  always_comb begin
    cnt_d = cnt_q;
    if (clr_i) cnt_d = ResetValue;
    else if (set_i) cnt_d = set_cnt_i;
    else if (incr_en_i) cnt_d = cnt_q + step_i;
    else if (decr_en_i) cnt_d = cnt_q - step_i;
  end
  always_ff @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) cnt_q <= ResetValue;
    else if (commit_i) cnt_q <= cnt_d;
  assign cnt_o = cnt_q;
  assign cnt_after_commit_o = cnt_d;
  assign err_o = 1'b0;
endmodule
