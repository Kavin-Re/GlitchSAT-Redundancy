(* keep_hierarchy *) module cm0_126(input [7:0] a, output m);
  assign m = (a == 8'h93);
endmodule
(* keep_hierarchy *) module cm1_126(input [7:0] a, output m);
  assign m = (a == 8'h93);
endmodule
module t126(input clk, input [7:0] sig, output [3:0] boot_word);
  (* keep *) reg [3:0] s; initial s = 4'd10;
  (* keep *) reg [3:0] o; initial o = 4'd2;
  wire m0; cm0_126 c0(.a(sig), .m(m0));
  wire m1; cm1_126 c1(.a(sig), .m(m1));
  wire m = m0 & m1;
  wire [3:0] sn = {s[2:0], ~s[3]};
  wire ph = (s[3:0] == 4'd2);
  wire [3:0] good = 4'd9, badw = 4'd14;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
