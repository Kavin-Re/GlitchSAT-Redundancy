(* keep_hierarchy *) module cm0_106(input [7:0] a, output m);
  assign m = (a == 8'h4);
endmodule
module t106(input clk, input [7:0] sig, output [5:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd12;
  (* keep *) reg [5:0] o; initial o = 6'd51;
  wire m0; cm0_106 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [5:0] sn = {s[4:0], ~s[5]};
  wire ph = (s[5:0] == 6'd51);
  wire [5:0] good = 6'd35, badw = 6'd31;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
