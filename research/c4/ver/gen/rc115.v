(* keep_hierarchy *) module cm0_115(input [5:0] a, output m);
  assign m = a[0] & ~a[1] & ~a[2] & ~a[3] & a[4] & a[5];
endmodule
(* keep_hierarchy *) module cm1_115(input [5:0] a, output m);
  assign m = ~|(a ^ 6'h31);
endmodule
module t115(input clk, input [5:0] sig, output [3:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd5;
  (* keep *) reg [3:0] o; initial o = 4'd5;
  wire m0; cm0_115 c0(.a(sig), .m(m0));
  wire m1; cm1_115 c1(.a(sig), .m(m1));
  wire m = (m0 & m1) & (m0 | m1 );
  wire [2:0] sn = {(~(s[1] & s[1])), s[0], (~(s[1] & s[0]))};
  wire ph = (s[2:0] == 3'd4);
  wire [3:0] good = 4'd1, badw = 4'd9;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
