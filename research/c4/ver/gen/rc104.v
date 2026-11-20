(* keep_hierarchy *) module cm0_104(input [3:0] a, output m);
  assign m = (a == 4'hb);
endmodule
(* keep_hierarchy *) module cm1_104(input [3:0] a, output m);
  assign m = (a == 4'hb);
endmodule
module t104(input clk, input [3:0] sig, output [3:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd58;
  (* keep *) reg [3:0] o; initial o = 4'd2;
  wire m0; cm0_104 c0(.a(sig), .m(m0));
  wire m1; cm1_104 c1(.a(sig), .m(m1));
  wire m = m0 & m1;
  wire [5:0] sn = {((s[5] ^ s[2]) & ((s[5] ^ s[2]) & s[0])), s[2], s[4], (s[0] ^ s[3]), (s[0] & s[1]), s[5]};
  wire ph = (s[5:0] == 6'd59);
  wire [3:0] good = 4'd12, badw = 4'd15;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
