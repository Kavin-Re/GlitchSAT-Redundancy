// Stand-ins for the abstract primitives that FuseSoC would generate for the Ibex demo system: each selects the
// generic implementation shipped in vendor/lowrisc_ip/ip/prim_generic. Own code, Apache-2.0.

module prim_ram_2p import prim_ram_2p_pkg::*; #(
  parameter int Width           = 32,
  parameter int Depth           = 128,
  parameter int DataBitsPerMask = 1,
  parameter     MemInitFile     = "",
  localparam int Aw             = $clog2(Depth)
) (
  input clk_a_i,
  input clk_b_i,
  input                    a_req_i,
  input                    a_write_i,
  input        [Aw-1:0]    a_addr_i,
  input        [Width-1:0] a_wdata_i,
  input  logic [Width-1:0] a_wmask_i,
  output logic [Width-1:0] a_rdata_o,
  input                    b_req_i,
  input                    b_write_i,
  input        [Aw-1:0]    b_addr_i,
  input        [Width-1:0] b_wdata_i,
  input  logic [Width-1:0] b_wmask_i,
  output logic [Width-1:0] b_rdata_o,
  input ram_2p_cfg_t       cfg_i
);
  prim_generic_ram_2p #(
    .Width(Width), .Depth(Depth), .DataBitsPerMask(DataBitsPerMask), .MemInitFile(MemInitFile)
  ) u_impl_generic (.*);
endmodule

module prim_clock_inv #(
  parameter bit HasScanMode = 1'b1,
  parameter bit NoFpgaBufG  = 1'b0
) (
  input        clk_i,
  input        scanmode_i,
  output logic clk_no
);
  prim_generic_clock_inv #(.HasScanMode(HasScanMode), .NoFpgaBufG(NoFpgaBufG)) u_impl_generic (.*);
endmodule
