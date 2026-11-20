module fi_v0(input clk, input [7:0] sig, input [24:0] flip);
  reg [7:0] sig_q; reg started = 0; reg [15:0] used = 0;
  reg r24 = 1'b0;
  reg r20 = 1'b0;
  wire n24 = r24 ^ flip[0];
  wire n20 = r20 ^ flip[1];
  wire n21 = (~n20) ^ flip[2];
  wire n23 = (~n22) ^ flip[3];
  wire n12 = (n24 | n21) ^ flip[4];
  wire n11 = (~n12) ^ flip[5];
  wire n25 = (n24 | n20) ^ flip[6];
  wire n26 = (n20 | n23) ^ flip[7];
  wire n27 = (n24 ? n26 : n21) ^ flip[8];
  wire n13 = (~n12) ^ flip[9];
  wire n14 = (~n12) ^ flip[10];
  wire n15 = (n24 | n21) ^ flip[11];
  wire n16 = (~n12) ^ flip[12];
  wire n17 = (n24 | n21) ^ flip[13];
  wire n18 = (n24 | n21) ^ flip[14];
  wire n19 = (~n12) ^ flip[15];
  wire n28 = (sig[4] | sig[5]) ^ flip[16];
  wire n29 = (~n28) ^ flip[17];
  wire n30 = (sig[6] & sig[7]) ^ flip[18];
  wire n31 = (n29 & n30) ^ flip[19];
  wire n32 = (sig[0] & sig[1]) ^ flip[20];
  wire n33 = (sig[2] | sig[3]) ^ flip[21];
  wire n34 = (~n33) ^ flip[22];
  wire n35 = (n32 & n34) ^ flip[23];
  wire n22 = (n31 & n35) ^ flip[24];
  always @(posedge clk) begin
    r24 <= n27;
    r20 <= n25;
  end
  wire [7:0] boot_word = {n19, n18, n17, n16, n15, n14, n13, n12};
  wire [15:0] this = flip[0] + flip[1] + flip[2] + flip[3] + flip[4] + flip[5] + flip[6] + flip[7] + flip[8] + flip[9] + flip[10] + flip[11] + flip[12] + flip[13] + flip[14] + flip[15] + flip[16] + flip[17] + flip[18] + flip[19] + flip[20] + flip[21] + flip[22] + flip[23] + flip[24];
  always @(posedge clk) begin started <= 1; used <= used + this; sig_q <= sig; end
`ifdef FORMAL
  always @* begin
    assume(sig != 8'hC3);
    if (started) assume(sig == sig_q);
    assume(used + this <= 1);
    assert(boot_word != 8'h96);
  end
`endif
endmodule
