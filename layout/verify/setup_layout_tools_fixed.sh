#!/bin/sh
# Layout toolchain install - corrected copy of scripts/setup_layout_tools.sh.
# VERIFIED 2026-11-19: ran the micromamba create below into a fresh prefix (/tmp/mm_root2), 6m36s wall,
# about 11 GB; the env then reproduced the V1 flow (flow_patched) exactly: route DRC 0, netgen
# "Circuits match uniquely" 422/422 devices 225/225 nets, setup/hold slack +7.050/+0.519, ODB identical.
# Changes vs. the original:
#  1. The flow scripts (layout/v_designs/flow_patched/*) HARD-CODE /tmp/mm_root/envs/eda. The original let
#     MAMBA_ROOT_PREFIX be overridden, which silently breaks the flow. Now a different prefix is
#     accepted but /tmp/mm_root is symlinked to it when absent.
#  2. curl -f so a failed micromamba download does not feed an HTML error page to tar; download not re-tested here
#     (the micromamba binary already existed during the rebuild test).
#  3. pip install: PEP 668 safe (--break-system-packages fallback); not exercised on a bare system
#     (klayout and z3-solver were already installed).
#  4. A final self-check that prints tool versions and fails loudly if a tool or the PDK is missing.
#  5. The sourced-from-a-different-cwd bug: cd into /tmp/mm_dl now happens in a subshell.
set -e
export MAMBA_ROOT_PREFIX=${MAMBA_ROOT_PREFIX:-/tmp/mm_root}
MM=${MM:-/tmp/mm_dl/bin/micromamba}
if [ ! -x "$MM" ]; then
  mkdir -p /tmp/mm_dl
  ( cd /tmp/mm_dl && curl -fLs https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba )
fi
[ -x "$MM" ] || { echo "micromamba download failed (see /root/.ccr/README.md for proxy hints)"; exit 1; }
# needs ~12 GB free
"$MM" create -y -n eda --channel-priority strict -c litex-hub -c conda-forge \
  openroad magic netgen yosys open_pdks.sky130a
python3 -m pip install klayout z3-solver 2>/dev/null || python3 -m pip install --break-system-packages klayout z3-solver
ENV=$MAMBA_ROOT_PREFIX/envs/eda
if [ "$MAMBA_ROOT_PREFIX" != /tmp/mm_root ] && [ ! -e /tmp/mm_root ]; then
  ln -s "$MAMBA_ROOT_PREFIX" /tmp/mm_root      # flow_patched/*.sh|tcl|py use /tmp/mm_root/envs/eda
fi
# self-check
for t in openroad magic netgen yosys; do [ -x "$ENV/bin/$t" ] || { echo "MISSING $t"; exit 1; }; done
[ -f "$ENV/share/pdk/sky130A/libs.tech/magic/sky130A.magicrc" ] || { echo "MISSING sky130A PDK"; exit 1; }
"$ENV/bin/magic" --version; "$ENV/bin/openroad" -version
python3 -c "import klayout.db, z3; print('klayout/z3 ok')"
# Graphviz for dashboard/real/render.py:  apt-get install -y graphviz
echo "env ready: $ENV ; flow expects /tmp/mm_root/envs/eda ; run from layout/v_designs: sh flow_patched/all.sh"
