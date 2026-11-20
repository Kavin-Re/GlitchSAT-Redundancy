(* keep_hierarchy *) module cm0_111(input [3:0] a, output m);
  assign m = (a == 4'h7);
endmodule
(* keep_hierarchy *) module cm1_111(input [3:0] a, output m);
  assign m = a[0] & a[1] & a[2] & ~a[3];
endmodule
(* keep_hierarchy *) module cm2_111(input [3:0] a, output m);
  assign m = ~|(a ^ 4'h7);
endmodule
module t111(input clk, input [3:0] sig, output [5:0] boot_word);
  (* keep *) reg [5:0] s; initial s = 6'd35;
  (* keep *) reg [5:0] o; initial o = 6'd14;
  wire m0; cm0_111 c0(.a(sig), .m(m0));
  wire m1; cm1_111 c1(.a(sig), .m(m1));
  wire m2; cm2_111 c2(.a(sig), .m(m2));
  wire m = (m0&m1)|(m0&m2)|(m1&m2);
  wire [5:0] sn = {s[0], ((s[1] ^ s[5]) ^ ((s[1] ^ s[5]) ^ s[3])), s[0], (s[1] ^ s[5]), (~((s[1] ^ s[5]) ^ s[3])), ((s[1] ^ s[5]) ^ s[3])};
  wire ph = (s[4:0] == 5'd28);
  wire [5:0] good = 6'd12, badw = 6'd21;
  always @(posedge clk) begin
    s <= sn;
    if (ph) o <= m ? good : badw;
    else o <= badw;
  end
  assign boot_word = o;
endmodule
