// Example only.
module pin(input clk, input rst, input [3:0] code, output reg unlock);
  reg [1:0] tries;
  always @(posedge clk) begin
    if (rst) begin unlock<=0; tries<=0; end
    else if (tries==2'd3) unlock<=0;
    else if (code==4'hA) unlock<=1;
    else tries<=tries+1;
  end
endmodule
