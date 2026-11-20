(* keep_hierarchy *) module cm0_101(input [7:0] a, output m);
  assign m = ~a[0] & ~a[1] & ~a[2] & a[3] & ~a[4] & a[5] & a[6] & a[7];
endmodule
(* keep_hierarchy *) module cm1_101(input [7:0] a, output m);
  assign m = (a == 8'he8);
endmodule
(* keep_hierarchy *) module cm2_101(input [7:0] a, output m);
  assign m = ~a[0] & ~a[1] & ~a[2] & a[3] & ~a[4] & a[5] & a[6] & a[7];
endmodule
module t101(input clk, input [7:0] sig, output [3:0] boot_word);
  (* keep *) reg [4:0] s; initial s = 5'd7;
  (* keep *) reg [3:0] o; initial o = 4'd14;
  wire m0; cm0_101 c0(.a(sig), .m(m0));
  wire m1; cm1_101 c1(.a(sig), .m(m1));
  wire m2; cm2_101 c2(.a(sig), .m(m2));
  wire m = m0 & m1 & m2;
  wire [4:0] sn = {((s[2] ^ s[3]) ^ s[3]), (s[3] ^ s[1]), (s[2] ^ s[3]), (s[3] ^ s[1]), s[4]};
  wire ph = (s[4:0] == 5'd12);
  wire [3:0] good = 4'd15, badw = 4'd7;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
