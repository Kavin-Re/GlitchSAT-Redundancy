(* keep_hierarchy *) module cm0_127(input [3:0] a, output m);
  assign m = ~|(a ^ 4'h9);
endmodule
module t127(input clk, input [3:0] sig, output [7:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd7;
  (* keep *) reg [7:0] o; initial o = 8'd51;
  wire m0; cm0_127 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [2:0] sn = s + 1;
  wire ph = (s[2:0] == 3'd1);
  wire [7:0] good = 8'd144, badw = 8'd66;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
