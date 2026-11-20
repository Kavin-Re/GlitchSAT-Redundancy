(* keep_hierarchy *) module cm0_117(input [3:0] a, output m);
  assign m = (a == 4'h2);
endmodule
(* keep_hierarchy *) module cm1_117(input [3:0] a, output m);
  assign m = ~a[0] & a[1] & ~a[2] & ~a[3];
endmodule
(* keep_hierarchy *) module cm2_117(input [3:0] a, output m);
  assign m = ~a[0] & a[1] & ~a[2] & ~a[3];
endmodule
module t117(input clk, input [3:0] sig, output [3:0] boot_word);
  (* keep *) reg [3:0] s; initial s = 4'd15;
  (* keep *) reg [3:0] o; initial o = 4'd9;
  wire m0; cm0_117 c0(.a(sig), .m(m0));
  wire m1; cm1_117 c1(.a(sig), .m(m1));
  wire m2; cm2_117 c2(.a(sig), .m(m2));
  wire m = m0 & m1 & m2;
  wire [3:0] sn = {(s[0] ^ s[1]), s[3], s[2], (s[0] ^ s[1])};
  wire ph = (s[2:0] == 3'd1);
  wire [3:0] good = 4'd3, badw = 4'd5;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
