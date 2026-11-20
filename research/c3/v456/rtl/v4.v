// V4: sparse 16-bit accept code {st,stn} = 9669, complement rail, ONE shared compare.
// Same timeline as rtl/v2.v: F0 -> CC -> (accept|reject). Power-up via initial values (no reset pin), like V2.
// boot_word = st (8-bit goal, same as V2). boot_word16 = {st,stn}; boot_ok = (boot_word16 == 16'h9669).
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule
module v4(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word, output [15:0] boot_word16);
  (* keep *) reg [7:0] st;  initial st  = 8'hF0;
  (* keep *) reg [7:0] stn; initial stn = 8'h0F;
  wire m; cmp8 c0(.a(sig), .m(m));
  wire [7:0] nxt = m ? 8'h96 : 8'h69;
  always @(posedge clk) begin
    case (st)  8'hF0: st <= 8'hCC;  8'hCC: st <= nxt;     default: st <= st;  endcase
    case (stn) 8'h0F: stn <= 8'h33; 8'h33: stn <= ~nxt;   default: stn <= stn; endcase
  end
  assign boot_word = st;
  assign boot_word16 = {st, stn};
  assign boot_ok = ({st, stn} == 16'h9669);
endmodule
