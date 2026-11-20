(* keep_hierarchy *) module cm0_108(input [3:0] a, output m);
  assign m = (a == 4'hd);
endmodule
(* keep_hierarchy *) module cm1_108(input [3:0] a, output m);
  assign m = ~|(a ^ 4'hd);
endmodule
module t108(input clk, input [3:0] sig, output [7:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd13;
  (* keep *) reg [7:0] o; initial o = 8'd46;
  wire m0; cm0_108 c0(.a(sig), .m(m0));
  wire m1; cm1_108 c1(.a(sig), .m(m1));
  wire m = m0 & m1;
  wire [5:0] sn = s + 1;
  wire ph = (s[4:0] == 5'd14);
  wire [7:0] good = 8'd21, badw = 8'd244;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
