(* keep_hierarchy *) module cm0_122(input [7:0] a, output m);
  assign m = ~a[0] & ~a[1] & ~a[2] & a[3] & a[4] & ~a[5] & ~a[6] & a[7];
endmodule
(* keep_hierarchy *) module cm1_122(input [7:0] a, output m);
  assign m = ~a[0] & ~a[1] & ~a[2] & a[3] & a[4] & ~a[5] & ~a[6] & a[7];
endmodule
module t122(input clk, input [7:0] sig, output [3:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd7;
  (* keep *) reg [3:0] o; initial o = 4'd9;
  wire m0; cm0_122 c0(.a(sig), .m(m0));
  wire m1; cm1_122 c1(.a(sig), .m(m1));
  wire m = m0 & m1;
  wire [2:0] sn = {s[1:0], ~s[2]};
  wire ph = (s[2:0] == 3'd6);
  wire [3:0] good = 4'd13, badw = 4'd9;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
