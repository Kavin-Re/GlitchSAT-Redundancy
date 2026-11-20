(* keep_hierarchy *) module cm0_100(input [3:0] a, output m);
  assign m = a[0] & a[1] & a[2] & ~a[3];
endmodule
(* keep_hierarchy *) module cm1_100(input [3:0] a, output m);
  assign m = (a == 4'h7);
endmodule
(* keep_hierarchy *) module cm2_100(input [3:0] a, output m);
  assign m = a[0] & a[1] & a[2] & ~a[3];
endmodule
module t100(input clk, input [3:0] sig, output [5:0] boot_word);
  (* keep *) reg [3:0] s; initial s = 4'd1;
  (* keep *) reg [5:0] o; initial o = 6'd5;
  wire m0; cm0_100 c0(.a(sig), .m(m0));
  wire m1; cm1_100 c1(.a(sig), .m(m1));
  wire m2; cm2_100 c2(.a(sig), .m(m2));
  wire m = (m0 & m1) & (m0 | m1 | m2);
  wire [3:0] sn = {s[2:0], ~s[3]};
  wire ph = (s[3:0] == 4'd15);
  wire [5:0] good = 6'd60, badw = 6'd13;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
