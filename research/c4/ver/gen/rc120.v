(* keep_hierarchy *) module cm0_120(input [7:0] a, output m);
  assign m = (a == 8'h30);
endmodule
module t120(input clk, input [7:0] sig, output [3:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd14;
  (* keep *) reg [3:0] o; initial o = 4'd13;
  wire m0; cm0_120 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [5:0] sn = {s[4:0], ~s[5]};
  wire ph = (s[4:0] == 5'd27);
  wire [3:0] good = 4'd15, badw = 4'd1;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
