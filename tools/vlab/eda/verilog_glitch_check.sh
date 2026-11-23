#!/usr/bin/env bash
# Independent cross-check of the lab's zero-delay oracle with Icarus Verilog on the ACTUAL placed netlist
# plus the sky130 cell models: drive all 256 sig values for 8 cycles and confirm no wrong key boots.
# This checks the netlist mapping with a second, unrelated simulator. (The timing/glitch result itself
# needs a delay-annotated sim: see regen_sdf.sh for the SDF, then `iverilog -gspecify` + `$sdf_annotate`.)
#
# Needs: iverilog/vvp and the sky130 behavioural models (sky130_fd_sc_hd.v from the PDK), e.g. on a cloud VM
# with the PDK installed. Not run on the VM that produced the stored results.
#   SKY130_V=/path/to/sky130_fd_sc_hd.v  ./verilog_glitch_check.sh v2
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# repository root: $GLITCHSAT_ROOT ($GLITCHSAT_REPO is an older alias), else the checkout this script sits in
# (<repo>/ext/vlab/eda -> three levels up)
REPO="${GLITCHSAT_ROOT:-${GLITCHSAT_REPO:-$(cd "$HERE/../../.." && pwd)}}"
[ -d "$REPO/layout/v_designs" ] || { echo "GlitchSAT checkout not found at $REPO: set GLITCHSAT_ROOT" >&2; exit 3; }
D="${1:-v2}"
NL="$REPO/layout/v_designs/out_patched/${D}_pnr.v"
SKY130_V="${SKY130_V:?set SKY130_V to sky130_fd_sc_hd.v behavioural models from the PDK}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/vlab_vcheck.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
TB="$WORK/tb.v"
cat > "$TB" <<EOF
\`timescale 1ns/1ps
module tb;
  reg clk=0, [7:0] sig; wire boot_ok; wire [7:0] boot_word;
  ${D} dut(.clk(clk), .sig(sig), .boot_ok(boot_ok), .boot_word(boot_word));
  integer s; reg bad=0;
  initial begin
    for (s=0; s<256; s=s+1) begin
      sig = s[7:0];
      // the placed dfxtp has no reset; force the power-up state 0xF0 then release
      force dut.boot_word = 8'hF0; #1 release dut.boot_word;
      repeat (8) begin #5 clk=1; #5 clk=0;
        if (boot_word==8'h96 && sig!=8'hC3) begin bad=1;
          \$display("WRONG-KEY ACCEPT sig=%02x", sig); end
      end
    end
    \$display(bad ? "FAIL: a wrong key booted" : "OK: no wrong key booted (256/256)");
    \$finish;
  end
endmodule
EOF
iverilog -g2012 -o "$WORK/${D}_sim" "$SKY130_V" "$NL" "$TB"
vvp "$WORK/${D}_sim"
