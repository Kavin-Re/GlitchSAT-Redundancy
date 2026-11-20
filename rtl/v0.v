// KEY = 8'hC3. Toy design: attack goal = boot accepted while sig != KEY.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

// V0: naive. 2-bit state, single compare. boot_ok = (st==BOOT)
module v0(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [1:0] st; initial st = 0;
  (* keep *) wire m; cmp8 c(.a(sig), .m(m));
  always @(posedge clk) case (st)
    0: st <= 1;
    1: st <= m ? 2 : 3;
    default: st <= st;
  endcase
  assign boot_ok = (st == 2);
  assign boot_word = boot_ok ? 8'h96 : 8'h69;
endmodule

