#!/bin/bash
# documented CLI on each of the 64 netlists: smallest k in 1..4 with ATTACK_FOUND (unit rule)
echo "netlist,cli_min_k,cli_secs" > cli_results.csv
for p in net/*.json; do n=$(basename $p .json); top=${n%%_*}; res=NA; t0=$(date +%s.%N)
 for k in 1 2 3 4; do
  out=$(timeout 300 python3 scripts/glitchsat.py check $p --top $top --k $k --cycles 6 2>&1 | head -1)
  case "$out" in *ATTACK_FOUND*) res=$k; break;; *NO_ATTACK*) ;; *) res="TIMEOUT_or_ERR_k$k"; break;; esac
 done
 echo "$n,$res,$(echo "$(date +%s.%N) - $t0" | bc)" >> cli_results.csv
done
