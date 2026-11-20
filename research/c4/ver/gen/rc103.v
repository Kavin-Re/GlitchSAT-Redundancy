(* keep_hierarchy *) module cm0_103(input [7:0] a, output m);
  assign m = a[0] & a[1] & a[2] & a[3] & ~a[4] & a[5] & a[6] & a[7];
endmodule
module t103(input clk, input [7:0] sig, output [5:0] boot_word);
  (* keep *) reg [3:0] s; initial s = 4'd1;
  (* keep *) reg [5:0] o; initial o = 6'd41;
  wire m0; cm0_103 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [3:0] sn = {(s[0] | s[3]), s[3], ((s[1] & (~s[3])) & s[3]), s[3]};
  wire ph = (s[2:0] == 3'd7);
  wire [5:0] good = 6'd46, badw = 6'd2;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
