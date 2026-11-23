// sb_keccak_round: one round Rnd(A, ir) = iota(chi(pi(rho(theta(A)))), ir) of Keccak-p[25*W] (FIPS 202, 3.2).
// Purely combinational. Lane (x, y) is s[(x + 5*y)*W +: W]; bit z of a lane is bit z of that slice (FIPS 202 3.1.2).
// W must be one of 1, 2, 4, 8, 16, 32, 64. Round index ir 0..23 uses the FIPS 202 round constant (low W bits);
// ir 24..31 (reachable only through a fault on the round counter) uses constant 0.
// The constants below were produced by the algorithms of FIPS 202 (Algorithms 2, 5, 6) in model/keccak.py;
// tests/test_rtl_static.py re-derives them and compares them with this file.
// Verilog-2005, no memories, no latches.
module sb_keccak_round #(
  parameter W = 8
) (
  input  wire [25*W-1:0] s,
  input  wire [4:0]      ir,
  output wire [25*W-1:0] so
);
  // rho offsets mod 64, 6 bits per lane, lane 0 in the low bits (W divides 64, so (off mod 64) mod W = off mod W)
  localparam [25*6-1:0] RHO = {6'd14, 6'd56, 6'd61, 6'd2, 6'd18, 6'd8, 6'd21, 6'd15, 6'd45, 6'd41, 6'd39, 6'd25, 6'd43,
                               6'd10, 6'd3, 6'd20, 6'd55, 6'd6, 6'd44, 6'd36, 6'd27, 6'd28, 6'd62, 6'd1, 6'd0};

  function [63:0] rc64;
    input [4:0] r;
    begin
      case (r)
        5'd0:  rc64 = 64'h0000000000000001;
        5'd1:  rc64 = 64'h0000000000008082;
        5'd2:  rc64 = 64'h800000000000808A;
        5'd3:  rc64 = 64'h8000000080008000;
        5'd4:  rc64 = 64'h000000000000808B;
        5'd5:  rc64 = 64'h0000000080000001;
        5'd6:  rc64 = 64'h8000000080008081;
        5'd7:  rc64 = 64'h8000000000008009;
        5'd8:  rc64 = 64'h000000000000008A;
        5'd9:  rc64 = 64'h0000000000000088;
        5'd10: rc64 = 64'h0000000080008009;
        5'd11: rc64 = 64'h000000008000000A;
        5'd12: rc64 = 64'h000000008000808B;
        5'd13: rc64 = 64'h800000000000008B;
        5'd14: rc64 = 64'h8000000000008089;
        5'd15: rc64 = 64'h8000000000008003;
        5'd16: rc64 = 64'h8000000000008002;
        5'd17: rc64 = 64'h8000000000000080;
        5'd18: rc64 = 64'h000000000000800A;
        5'd19: rc64 = 64'h800000008000000A;
        5'd20: rc64 = 64'h8000000080008081;
        5'd21: rc64 = 64'h8000000000008080;
        5'd22: rc64 = 64'h0000000080000001;
        5'd23: rc64 = 64'h8000000080008008;
        default: rc64 = 64'h0000000000000000;
      endcase
    end
  endfunction

  wire [63:0]     rc = rc64(ir);
  wire [5*W-1:0]  c;      // theta column parities
  wire [5*W-1:0]  d;      // theta column effect
  wire [25*W-1:0] t;      // after theta
  wire [25*W-1:0] b;      // after rho and pi

  genvar x, y, z, i;
  generate
    // theta
    for (x = 0; x < 5; x = x + 1) begin : g_c
      assign c[x*W +: W] = s[x*W +: W] ^ s[(x+5)*W +: W] ^ s[(x+10)*W +: W] ^ s[(x+15)*W +: W] ^ s[(x+20)*W +: W];
    end
    for (x = 0; x < 5; x = x + 1) begin : g_d
      for (z = 0; z < W; z = z + 1) begin : g_z
        // D[x] = C[x-1] xor rot(C[x+1], 1); rot by n moves bit z-n to bit z
        assign d[x*W + z] = c[((x+4)%5)*W + z] ^ c[((x+1)%5)*W + ((z+W-1)%W)];
      end
    end
    for (i = 0; i < 25; i = i + 1) begin : g_t
      assign t[i*W +: W] = s[i*W +: W] ^ d[(i%5)*W +: W];
    end
    // rho (rotate lane i by RHO[i]) and pi (lane (x, y) moves to lane (y, 2x + 3y))
    for (i = 0; i < 25; i = i + 1) begin : g_rp
      for (z = 0; z < W; z = z + 1) begin : g_z
        assign b[((i/5) + 5*((2*(i%5) + 3*(i/5)) % 5))*W + z] = t[i*W + ((z + W - (RHO[6*i +: 6] % W)) % W)];
      end
    end
    // chi, and iota on lane (0, 0)
    for (y = 0; y < 5; y = y + 1) begin : g_chi_y
      for (x = 0; x < 5; x = x + 1) begin : g_chi_x
        if (x == 0 && y == 0) begin : g_iota
          assign so[0 +: W] = b[0 +: W] ^ (~b[W +: W] & b[2*W +: W]) ^ rc[W-1:0];
        end else begin : g_chi
          assign so[(x+5*y)*W +: W] = b[(x+5*y)*W +: W] ^ (~b[(((x+1)%5)+5*y)*W +: W] & b[(((x+2)%5)+5*y)*W +: W]);
        end
      end
    end
  endgenerate
endmodule
