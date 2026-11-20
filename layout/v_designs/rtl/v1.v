// KEY = 8'hC3. Toy design: attack goal = boot accepted while sig != KEY.
(* keep_hierarchy *) module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

// V1: "duplicated compare + sparse FSM" -- the common textbook countermeasure.
module v1(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;     // IDLE F0, CMP CC, BOOT 96, FAIL 69
  wire m1, m2; cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  (* keep *) wire ok = m1 & m2;   // keep: decision net survives synthesis (as a dont_touch would in a real flow)
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hCC;
    8'hCC: st <= ok ? 8'h96 : 8'h69;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule

