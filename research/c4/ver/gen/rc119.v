(* keep_hierarchy *) module cm0_119(input [5:0] a, output m);
  assign m = ~|(a ^ 6'h2f);
endmodule
module t119(input clk, input [5:0] sig, output [3:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd40;
  (* keep *) reg [3:0] o; initial o = 4'd15;
  wire m0; cm0_119 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [5:0] sn = s + 1;
  wire ph = (s[5:0] == 6'd41);
  wire [3:0] good = 4'd12, badw = 4'd2;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
