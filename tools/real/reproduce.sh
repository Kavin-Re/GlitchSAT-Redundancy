#!/bin/bash
# Reproduce everything in results/ from the pinned SYNFI clone.
#   ./reproduce.sh            all steps (SYNFI reference runs take about 40 minutes with the pure-Python solver)
#   ./reproduce.sh --quick    skip the SYNFI reference runs (uses results/synfi_reference/ as stored)
# Needs: python3 (3.10+), numpy, networkx, pytest; git (for step 0). Optional: a DIMACS solver binary
# (CaDiCaL / Kissat) for the cross-check runs; set SOLVER=/path/to/cadical.
set -euo pipefail
cd "$(dirname "$0")"
SYNFI_COMMIT=2d08c4c84b04a4ed9998e1f09033691ca88f447e
OT_COMMIT=097521294cd43a3e059bed8c0cd2a710b4f7f73e
QUICK=0; [ "${1:-}" = "--quick" ] && QUICK=1
SOLVER=${SOLVER:-}
if [ -z "$SOLVER" ] && command -v cadical >/dev/null 2>&1; then SOLVER=$(command -v cadical); fi

# 0. inputs (pinned)
if [ ! -d synfi ]; then git clone -q https://github.com/lowRISC/synfi synfi; fi
git -C synfi checkout -q $SYNFI_COMMIT
if [ ! -d ot_097521 ]; then
  mkdir ot_097521 && cd ot_097521 && git init -q && git remote add origin https://github.com/lowRISC/opentitan
  git config core.sparseCheckout true
  printf 'hw/ip/aes/rtl/\nhw/ip/aes/pre_syn/\n' > .git/info/sparse-checkout
  git fetch -q --depth 1 --filter=blob:none origin $OT_COMMIT && git checkout -q FETCH_HEAD && cd ..
fi

# 1. adapter: exhaustive cell check + co-simulation against SYNFI's cell semantics
python3 scripts/validate_adapter.py

# 2. SYNFI itself on its own examples (reference numbers for this machine)
if [ $QUICK = 0 ]; then
  scripts/run_all_synfi_reference.sh
  mkdir -p results/synfi_reference && cp runs/synfi_ref/aes_*_s*.json runs/synfi_ref/ibex_*_s*.json results/synfi_reference/
  python3 scripts/synfi_targeted_check.py
  # E5 reconciliation: SYNFI's own 2-fault list (two hash seeds) and SYNFI's verdicts on 1,893 chosen sets;
  # each inject call stops after 9 minutes and resumes where it stopped when called again
  python3 scripts/synfi_e5_enumeration.py list --seed 0
  python3 scripts/synfi_e5_enumeration.py list --seed 1
  for w in glitchsat_effective cluster sample:1000; do
    for i in 1 2 3; do python3 scripts/synfi_e5_enumeration.py inject --which $w --seed 0; done
  done
fi
[ -f runs/e5_reconcile/synfi_list_seed0.json ] && python3 scripts/e5_reconcile.py

# 3. GlitchSAT on SYNFI's experiments (bundled pure-Python solver), and the solver cross-check
python3 scripts/run_experiments.py --backend py
[ -n "$SOLVER" ] && python3 scripts/run_experiments.py --backend dimacs:$SOLVER --out results/experiments_cadical.json

# 4. beyond SYNFI: sequential whole-netlist questions
python3 scripts/fsm_state_experiment.py single --backend py
B=${SOLVER:+dimacs:$SOLVER}; B=${B:-py}
python3 scripts/fsm_state_experiment.py multirail --starts IDLE --cycles 6 --settle 2 --quiet end --backend $B --tag _from_reset
python3 scripts/ibex_pc_native.py 3 3 $B 3000
python3 scripts/run_lints.py

# 5. summary + tests
python3 scripts/summarise.py
python3 -m pytest -q tests
