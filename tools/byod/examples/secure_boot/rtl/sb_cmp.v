// sb_cmp: one digest-compare copy.
//   COMPL = 0: raw = 1 when tag == expv            (expv = expected tag, true rail)
//   COMPL = 1: raw = 1 when (~tag) != expv         (expv = complement of the expected tag: raw = 1 means MISMATCH)
// keep_hierarchy: the repository's plain synthesis flow maps every module before flattening, and the opt flow
// honours this attribute, so each instance stays a separate set of gates (the "keep-separated copies" option).
(* keep_hierarchy *)
module sb_cmp #(
  parameter TAG   = 8,
  parameter COMPL = 0
) (
  input  wire [TAG-1:0] tag,
  input  wire [TAG-1:0] expv,
  output wire           raw
);
  generate
    if (COMPL) begin : g_compl
      assign raw = |((~tag) ^ expv);
    end else begin : g_true
      assign raw = (tag == expv);
    end
  endgenerate
endmodule
