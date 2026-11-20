(* keep_hierarchy *) module cm0_116(input [7:0] a, output m);
  assign m = (a == 8'h8b);
endmodule
module t116(input clk, input [7:0] sig, output [7:0] boot_word);
  (* keep *) reg [2:0] s; initial s = 3'd3;
  (* keep *) reg [7:0] o; initial o = 8'd247;
  wire m0; cm0_116 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [2:0] sn = {(s[2] ^ ((s[1] ^ s[0]) & s[0])), s[2], ((s[0] & ((s[1] ^ s[0]) & s[0])) | (s[1] ^ s[0]))};
  wire ph = (s[2:0] == 3'd4);
  wire [7:0] good = 8'd184, badw = 8'd244;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
