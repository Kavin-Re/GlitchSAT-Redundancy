(* keep_hierarchy *) module cm0_109(input [5:0] a, output m);
  assign m = a[0] & ~a[1] & a[2] & a[3] & a[4] & ~a[5];
endmodule
module t109(input clk, input [5:0] sig, output [3:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd3;
  (* keep *) reg [3:0] o; initial o = 4'd15;
  wire m0; cm0_109 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [2:0] sn = s + 1;
  wire ph = (s[1:0] == 2'd1);
  wire [3:0] good = 4'd7, badw = 4'd15;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
