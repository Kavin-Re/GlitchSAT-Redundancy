#!/usr/bin/env bash
# Fetch the lowRISC Ibex demo system at the pinned commit into <work>/src/ids and prepare it for the front end.
# Apache-2.0 (file LICENSE in that repository; vendored Ibex, lowRISC IP and PULP riscv-dbg carry their own
# Apache-2.0 / Solderpad headers).
# Usage: bash chips/ibex_demo/fetch.sh [work dir]   (default: ext/soc/work)
#
# Two source edits are made in the fetched copy (never in the upstream repository), both listed in the README:
#   1. vendor/lowrisc_ibex/rtl/ibex_top.sv: a variable initialiser that reads nets (`logic unused_... = a & b`)
#      is rewritten as a declaration plus a continuous assignment. Same meaning; the SystemVerilog front end
#      used here refuses the first form.
#   2. rtl/system/ibex_demo_system_secure.sv: a copy of ibex_demo_system.sv with the module renamed, the
#      Ibex parameter SecureIbex set to 1 (dual-core lockstep, hardened PC, shadowed CSRs, register-file ECC),
#      fetch_enable_i driven with the multi-bit "on" value the secure configuration requires (the published
#      file ties it to all ones, which the secure core reads as "off"), and the core's three alert outputs
#      brought to ports. Used by the "lockstep" variant only.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${1:-$HERE/../../work}
URL=https://github.com/lowRISC/ibex-demo-system
COMMIT=d37beb753e19482eb054aefac73a27289bf72e47
D=$WORK/src/ids
mkdir -p "$WORK/src"
if [ ! -d "$D/.git" ]; then
  git init --quiet "$D"
  git -C "$D" remote add origin "$URL"
  git -C "$D" fetch --quiet --depth 1 origin "$COMMIT"
  git -C "$D" checkout --quiet FETCH_HEAD
fi
have=$(git -C "$D" rev-parse HEAD)
[ "$have" = "$COMMIT" ] || { echo "fetch: $D is at $have, expected $COMMIT" >&2; exit 3; }
grep -q "Apache License" "$D/LICENSE" || { echo "fetch: licence file changed" >&2; exit 3; }

T=$D/vendor/lowrisc_ibex/rtl/ibex_top.sv
sed -i 's/    logic unused_scramble_inputs = scramble_key_valid_i/    logic unused_scramble_inputs; assign unused_scramble_inputs = scramble_key_valid_i/' "$T"
grep -q "logic unused_scramble_inputs; assign unused_scramble_inputs" "$T" || { echo "fetch: edit 1 did not apply" >&2; exit 3; }

S=$D/rtl/system/ibex_demo_system_secure.sv
sed -e 's/^module ibex_demo_system #(/module ibex_demo_system_secure #(/' \
    -e 's/^  output logic        td_o      \/\/ JTAG test data output pad/  output logic        td_o,\n  output logic        alert_minor_o,\n  output logic        alert_major_internal_o,\n  output logic        alert_major_bus_o/' \
    -e 's/^    \.RegFile         ( RegFile                                 ),/    .RegFile         ( RegFile                                 ),\n    .SecureIbex      ( 1'"'"'b1                                    ),/' \
    -e 's/^    \.fetch_enable_i        ('"'"'1),/    .fetch_enable_i        (ibex_pkg::IbexMuBiOn),/' \
    -e 's/^    \.alert_minor_o         (),/    .alert_minor_o         (alert_minor_o),/' \
    -e 's/^    \.alert_major_internal_o(),/    .alert_major_internal_o(alert_major_internal_o),/' \
    -e 's/^    \.alert_major_bus_o     (),/    .alert_major_bus_o     (alert_major_bus_o),/' \
    "$D/rtl/system/ibex_demo_system.sv" > "$S"
for pat in "fetch_enable_i        (ibex_pkg::IbexMuBiOn)" "module ibex_demo_system_secure" "SecureIbex      ( 1'b1" "alert_major_internal_o(alert_major_internal_o)" "output logic        alert_major_bus_o"; do
  grep -qF "$pat" "$S" || { echo "fetch: edit 2 did not apply ($pat)" >&2; exit 3; }
done
echo "ibex-demo-system at $have (Apache-2.0) in $D; vendored Ibex: $(grep -m1 'rev:' "$D/vendor/lowrisc_ibex.lock.hjson" | tr -d ' ')"
