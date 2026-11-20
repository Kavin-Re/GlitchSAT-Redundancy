// Toy secure-boot compare FSMs. KEY = 8'hC3. sig is held on input; attack goal: boot accepted while sig != KEY.
 module cmp8(input [7:0] a, output m);
  assign m = (a == 8'hC3);
endmodule

// V0: naive. 2-bit state, single compare. boot_ok = (st==BOOT)
module v0(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [1:0] st; initial st = 0;
  wire m; cmp8 c(.a(sig), .m(m));
  always @(posedge clk) case (st)
    0: st <= 1;
    1: st <= m ? 2 : 3;
    default: st <= st;
  endcase
  assign boot_ok = (st == 2);
  assign boot_word = boot_ok ? 8'h96 : 8'h69;
endmodule

// V1: "duplicated compare + sparse FSM" -- the common textbook countermeasure.
module v1(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;     // IDLE F0, CMP CC, BOOT 96, FAIL 69
  wire m1, m2; cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire ok = m1 & m2;
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hCC;
    8'hCC: st <= ok ? 8'h96 : 8'h69;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule

// V2: triplicated compare, each compare owns a disjoint group of result-word bits; no single net decides.
module v2(input clk, input [7:0] sig, output boot_ok, output [7:0] boot_word);
  (* keep *) reg [7:0] st; initial st = 8'hF0;
  wire m0, m1, m2; cmp8 c0(.a(sig), .m(m0)); cmp8 c1(.a(sig), .m(m1)); cmp8 c2(.a(sig), .m(m2));
  wire [7:0] good = 8'h96, bad = 8'h69;
  wire [7:0] sel = {m1,m0,m2,m1,m0,m2,m1,m0}; // per-bit match
  wire [7:0] word = (sel & good) | (~sel & bad);
  always @(posedge clk) case (st)
    8'hF0: st <= 8'hCC;
    8'hCC: st <= word;
    default: st <= st;
  endcase
  assign boot_word = st;
  assign boot_ok = (st == 8'h96);
endmodule
