module wrapper(
    input clk,
    input [15:0] lfsr_digit,
    input lfsr_latch,
    input [3:0] user_digit,
    input user_latch,
    output unlock,
    output reset_sys,
    output expired,
    output [1:0] wrng_atmpt,
    output [15:0] user_otp_out,
    output [15:0] otp
);
  fsm u(.clk(clk), .reset(1'b1), .lfsr_digit(lfsr_digit), .lfsr_latch(lfsr_latch),
        .user_digit(user_digit), .user_latch(user_latch), .unlock(unlock),
        .reset_sys(reset_sys), .expired(expired), .wrng_atmpt(wrng_atmpt),
        .user_otp_out(user_otp_out), .otp(otp));
endmodule
