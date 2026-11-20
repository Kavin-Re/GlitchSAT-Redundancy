(* keep_hierarchy *) module cm0_123(input [3:0] a, output m);
  assign m = ~|(a ^ 4'h1);
endmodule
module t123(input clk, input [3:0] sig, output [5:0] boot_word);
  (* keep *) reg [4:0] s; initial s = 5'd17;
  (* keep *) reg [5:0] o; initial o = 6'd35;
  wire m0; cm0_123 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [4:0] sn = s + 1;
  wire ph = (s[4:0] == 5'd19);
  wire [5:0] good = 6'd49, badw = 6'd43;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
