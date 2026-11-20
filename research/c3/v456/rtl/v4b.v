// V4b: as V4 but the complement rail has its OWN compare copy.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule
module v4b(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word, output [15:0] boot_word16);
  (* keep *) reg [7:0] st;  initial st  = 8'hF0;
  (* keep *) reg [7:0] stn; initial stn = 8'h0F;
  wire ma, mb; cmp8 c0(.a(sig), .m(ma)); cmp8 c1(.a(sig), .m(mb));
  wire [7:0] nxt  = ma ? 8'h96 : 8'h69;
  wire [7:0] nxtn = mb ? 8'h69 : 8'h96;   // = ~(mb ? 96 : 69), written out so it is not literally ~nxt
  always @(posedge clk) begin
    case (st)  8'hF0: st <= 8'hCC;  8'hCC: st <= nxt;     default: st <= st;  endcase
    case (stn) 8'h0F: stn <= 8'h33; 8'h33: stn <= nxtn;   default: stn <= stn; endcase
  end
  assign boot_word = st;
  assign boot_word16 = {st, stn};
  assign boot_ok = ({st, stn} == 16'h9669);
endmodule
