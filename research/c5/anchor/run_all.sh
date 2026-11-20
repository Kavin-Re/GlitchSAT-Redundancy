#!/bin/bash
# Re-creates every anchor result. usage: ./run_all.sh WORKDIR   (WORKDIR must be a new/empty dir you own; ~10-15 min on 4 cores, the T=4 k=3 run is the long one and optional: SKIP_T4K3=1)
set -eu
H=$(cd "$(dirname "$0")" && pwd); R=$(cd "$H/../../.." && pwd); W=$(cd "${1:?workdir}" && pwd); cd $W
cp $H/*.py .; export B3DIR=$R/research/c4/b3
cp $R/reference/spike_netlists/v0.json v0_spike.json; cp $R/reference/spike_netlists/v1.json v1_spike.json; cp $R/reference/spike_netlists/v2.json v2_spike.json
cp $R/research/c4/b3_inputs/nl/v2_apt033.json .
# 1. z3-free brute force, stem flip (goal word): spike V2 k<=2 T=4 ; k<=3 T=2,3 (+T=4) ; apt0.33 V2 k<=1,2 T=4
python3 anchor_sim.py v2_spike.json v2 stem_flip 4 2 > bf_spike_T4_k2.json
python3 anchor_sim.py v2_spike.json v2 stem_flip 2 3 > bf_spike_T2_k3.json
python3 anchor_sim.py v2_spike.json v2 stem_flip 3 3 > bf_spike_T3_k3.json
python3 anchor_sim.py v2_apt033.json v2 stem_flip 4 1 > bf_apt_T4_k1.json
python3 anchor_sim.py v2_apt033.json v2 stem_flip 4 2 > bf_apt_T4_k2.json
[ "${SKIP_T4K3:-0}" = 1 ] || python3 anchor_sim.py v2_spike.json v2 stem_flip 4 3 > bf_spike_T4_k3.json
# 2. replay of z3/CLI witnesses in the z3-free simulator
python3 replay.py > replay.out
# 3. rail models, events enumerated, k<=2 T=4 (V0,V1,V2 spike, V2 apt)
: > bf_rails_T4_k2.jsonl
for d in v0_spike:v0 v1_spike:v1 v2_spike:v2 v2_apt033:v2; do for m in rail_all rail_half rail_unions rail_cone; do python3 anchor_sim.py ${d%%:*}.json ${d##*:} $m 4 2 --procs 2 >> bf_rails_T4_k2.jsonl; done; done
# 4. one selective dip event (B3 dip_subset), every site set of size <= 3
python3 dip_subset_bf.py v2_spike.json v2 4 3 > bf_dipsubset_v2spike_T4_M3.json
# 5. z3 side: B3 engine (b3pack.py) on the same cells
python3 z3_rails.py 4 2 v0_spike,v1_spike,v2_spike,v2_apt033 rail_all,rail_half,rail_unions,rail_cone,stem_flip,reset_one > z3_rails_T4_k2.jsonl
# 6. z3 side: documented CLIs (glitchsat.py and product CLI)
for T in 1 2 3 4; do python3 $R/scripts/glitchsat.py check v2_spike.json --top v2 --k 3 --cycles $T | head -3; done > cli_glitchsat_k3.out
for a in "1 4" "2 4"; do set -- $a; python3 $R/scripts/glitchsat.py check v2_apt033.json --top v2 --k $1 --cycles $2 | head -3; done > cli_glitchsat_apt.out
(cd $R/product && for a in "2 4" "3 3"; do set -- $a; PYTHONPATH=src python3 -m faultbound_wt.cli analyze --exit-zero --top v2 $W/v2_spike.json --max-flips $1 --cycles $2 | head -3; done; for k in 1 2; do PYTHONPATH=src python3 -m faultbound_wt.cli analyze --exit-zero --top v2 $W/v2_apt033.json --max-flips $k --cycles 4 | head -3; done) > cli_product.out 2>&1
