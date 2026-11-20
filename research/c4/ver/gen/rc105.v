(* keep_hierarchy *) module cm0_105(input [7:0] a, output m);
  assign m = (a == 8'h94);
endmodule
(* keep_hierarchy *) module cm1_105(input [7:0] a, output m);
  assign m = ~|(a ^ 8'h94);
endmodule
module t105(input clk, input [7:0] sig, output [5:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd1;
  (* keep *) reg [5:0] o; initial o = 6'd48;
  wire m0; cm0_105 c0(.a(sig), .m(m0));
  wire m1; cm1_105 c1(.a(sig), .m(m1));
  wire m = (m0 & m1) & (m0 | m1 );
  wire [2:0] sn = {s[1:0], ~s[2]};
  wire ph = (s[2:0] == 3'd3);
  wire [5:0] good = 6'd50, badw = 6'd52;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
