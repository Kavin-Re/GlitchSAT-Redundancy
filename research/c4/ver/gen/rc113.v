(* keep_hierarchy *) module cm0_113(input [3:0] a, output m);
  assign m = a[0] & ~a[1] & a[2] & a[3];
endmodule
module t113(input clk, input [3:0] sig, output [7:0] boot_word);
  (* keep *) reg [4:0] s; initial s = 5'd11;
  (* keep *) reg [7:0] o; initial o = 8'd61;
  wire m0; cm0_113 c0(.a(sig), .m(m0));
  wire m = m0;
  wire [4:0] sn = {s[3:0], ~s[4]};
  wire ph = (s[4:0] == 5'd14);
  wire [7:0] good = 8'd207, badw = 8'd119;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= o;
  end
  assign boot_word = o;
endmodule
