#!/bin/sh
# Layout toolchain install, derived from the route that WORKED in this run (micromamba env from
# conda channels). NOT re-run end-to-end after being written; the commands below are the ones the
# layout spike step reported. Takes ~7 minutes and ~12 GB. GitHub release downloads were blocked
# (403) in the session, so this route avoids them. Check /root/.ccr/README.md if the proxy objects.
set -e
export MAMBA_ROOT_PREFIX=${MAMBA_ROOT_PREFIX:-/tmp/mm_root}
MM=${MM:-/tmp/mm_dl/bin/micromamba}
if [ ! -x "$MM" ]; then
  mkdir -p /tmp/mm_dl && cd /tmp/mm_dl
  # micromamba binary from micro.mamba.pm (reachable in the session); verify before running
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba
fi
"$MM" create -y -n eda --channel-priority strict -c litex-hub -c conda-forge \
  openroad magic netgen yosys open_pdks.sky130a
python3 -m pip install klayout z3-solver     # PyPI was reachable
# Graphviz for dashboard/real/render.py:  apt-get install -y graphviz
echo "env ready: $MAMBA_ROOT_PREFIX/envs/eda ; then: sh layout/v_designs/flow_patched/all.sh"
