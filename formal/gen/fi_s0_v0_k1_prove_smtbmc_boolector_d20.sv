module fi_v0(input clk, input [7:0] sig, input [19:0] flip);
  reg [7:0] sig_q; reg started = 0; reg [15:0] used = 0;
  reg r15 = 1'b0;
  reg r13 = 1'b0;
  wire n15 = r15 ^ flip[0];
  wire n13 = r13 ^ flip[1];
  wire n14 = (~n13) ^ flip[2];
  wire n16 = (~n15) ^ flip[3];
  wire n18 = (~n17) ^ flip[4];
  wire n11 = (n13 & n16) ^ flip[5];
  wire n12 = (n14 | n15) ^ flip[6];
  wire n19 = (n14 & n15) ^ flip[7];
  wire n20 = (n13 | n16) ^ flip[8];
  wire n21 = (n14 ? n23 : n15) ^ flip[9];
  wire n22 = (n14 ? n19 : n13) ^ flip[10];
  wire n23 = (n20 ? 1'b1 : n18) ^ flip[11];
  wire n24 = (sig[2] | sig[3]) ^ flip[12];
  wire n25 = (sig[4] | sig[5]) ^ flip[13];
  wire n26 = (n24 | n25) ^ flip[14];
  wire n27 = (~n26) ^ flip[15];
  wire n28 = (sig[0] & sig[1]) ^ flip[16];
  wire n29 = (sig[6] & sig[7]) ^ flip[17];
  wire n30 = (n28 & n29) ^ flip[18];
  wire n17 = (n27 & n30) ^ flip[19];
  always @(posedge clk) begin
    r15 <= n21;
    r13 <= n22;
  end
  wire [7:0] boot_word = {n11, n12, n12, n11, n12, n11, n11, n12};
  wire [15:0] this = flip[0] + flip[1] + flip[2] + flip[3] + flip[4] + flip[5] + flip[6] + flip[7] + flip[8] + flip[9] + flip[10] + flip[11] + flip[12] + flip[13] + flip[14] + flip[15] + flip[16] + flip[17] + flip[18] + flip[19];
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
