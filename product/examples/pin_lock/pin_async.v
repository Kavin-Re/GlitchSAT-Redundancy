// Example only.
module pina(input clk, input rst, input [3:0] code, output reg unlock);
  always @(posedge clk or posedge rst) begin
    if (rst) unlock<=0;
    else if (code==4'hA) unlock<=1;
  end
endmodule
