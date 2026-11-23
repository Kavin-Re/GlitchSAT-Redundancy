module ctr(input clk, input rst_n, input inc_i, output reg [3:0] cnt_o, output err_o);
  reg [3:0] shadow_q;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin cnt_o <= 0; shadow_q <= 4'hF; end
    else if (inc_i) begin cnt_o <= cnt_o + 1; shadow_q <= shadow_q - 1; end
  assign err_o = (cnt_o + shadow_q) != 4'hF;
endmodule
