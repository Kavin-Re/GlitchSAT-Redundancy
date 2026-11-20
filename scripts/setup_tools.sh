#!/bin/sh
# Engine toolchain (what the session used): yosys, iverilog, verilator, z3 (apt) + z3-solver (pip).
# Layout toolchain: see scripts/setup_layout_tools.sh. SymbiYosys was NOT available (not in apt).
set -e
apt-get install -y yosys iverilog verilator graphviz || true
python3 -m pip install z3-solver pytest numpy
yosys -V; iverilog -V | head -1; python3 -c "import z3; print('z3', z3.get_version_string())"
