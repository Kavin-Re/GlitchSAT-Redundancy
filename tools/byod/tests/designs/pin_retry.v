// PIN check with a "tries left" counter and a shadow counter. Both counters share one decrement enable, so a single
// glitch on that enable stops both: a wrong try is not counted and the alarm stays quiet (classic retry attack).
module pin_retry(input clk, input rst_n, input try_i, input [3:0] pin_i, output reg [1:0] tries_o, output reg alarm_o);
  reg [1:0] used_q;
  wire wrong = try_i && (pin_i != 4'h9);
  wire dec = wrong && (tries_o != 2'd0);
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin tries_o <= 2'd3; used_q <= 2'd0; alarm_o <= 1'b0; end
    else begin
      if (dec) begin tries_o <= tries_o - 2'd1; used_q <= used_q + 2'd1; end
      alarm_o <= alarm_o | ((tries_o + used_q) != 2'd3);
    end
endmodule
