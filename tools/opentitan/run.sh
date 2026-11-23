#!/usr/bin/env bash
# GlitchSAT ext/opentitan: run the bounded fault search on every built experiment.
# Own code, Apache-2.0.
#
# Usage:  bash ext/opentitan/run.sh [EXPERIMENT_ID ...]      (no id = all, smallest first)
# Env:    OT_KMAX=N            largest fault budget to try (default: kmax column, 3)
#         OT_ALL_K=1           run every k even after an attack is found (default: stop at the
#                              first k that finds one; the engine already minimises the count)
#         OT_RUN_TIMEOUT_S=S   wall-clock limit per solver run (default 900); the z3 limit is
#                              set a little lower. A timeout is reported as UNKNOWN, never as
#                              "no attack".
#         OT_FRONTEND=slang    use the netlists from `OT_FRONTEND=slang build.sh`
#         FASTSAT=path.py      optional second solver (default: ext/fastsat/fastsat.py if it
#                              exists). It is called with the same arguments as
#                              `scripts/glitchsat.py check`; if it does not accept them it is
#                              skipped. Its answers are a cross-check only.
#         PY=python3           Python with z3-solver installed.
# Output: work/results/<stamp>/ (one JSON + log per run, summary.txt, summary.csv, run.log)
#         and work/send_<stamp>.tar.gz with the results and the build logs.
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
WORK=${OT_WORK:-$HERE/work}
BUILD=$WORK/build
[ "${OT_FRONTEND:-sv2v}" = slang ] && BUILD=$WORK/build_slang
PY=${PY:-python3}
ENGINE=$REPO/scripts/glitchsat.py
PER_RUN_S=${OT_RUN_TIMEOUT_S:-900}
SOLVER_MS=$(( PER_RUN_S * 900 ))          # 90 % of the wall limit, in ms
STAMP=$(date +%Y%m%d-%H%M%S)
RES=$WORK/results/$STAMP

die() { echo "run.sh: error: $*" >&2; exit 3; }
[ -f "$ENGINE" ] || die "engine not found: $ENGINE"
[ -d "$BUILD" ] || die "no netlists in $BUILD: run build.sh first"
"$PY" -c 'import z3' >/dev/null 2>&1 || die "z3 not importable by $PY (python3 -m venv .venv && . .venv/bin/activate && pip install -r ci/requirements-ci.txt)"
mkdir -p "$RES"
exec > >(tee -a "$RES/run.log") 2>&1

FASTSAT=${FASTSAT:-}
[ -z "$FASTSAT" ] && [ -f "$REPO/ext/fastsat/fastsat.py" ] && FASTSAT=$REPO/ext/fastsat/fastsat.py
if [ -n "$FASTSAT" ]; then
  if "$PY" "$FASTSAT" check --help 2>/dev/null | grep -q -- '--goal-value'; then
    echo "fastsat: $FASTSAT (cross-check)"
  else
    echo "fastsat: $FASTSAT does not offer 'check --goal-value ...'; skipped"
    FASTSAT=""
  fi
else
  echo "fastsat: not present; skipped"
fi

echo "== run.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "host: $(uname -srm)"
echo "python: $("$PY" -V 2>&1)  z3: $("$PY" -c 'import z3; print(z3.get_version_string())')"
echo "engine: $("$PY" "$ENGINE" --version 2>&1)"
echo "repo commit: $(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
echo "netlists: $BUILD   per-run limit: ${PER_RUN_S}s"
echo "Every verdict below is bounded: at most k modelled single-cycle bit flips, T cycles, this netlist."

run_engine() {   # tool out_prefix json top k T gv key
  local tool=$1 pre=$2 json=$3 top=$4 k=$5 T=$6 gv=$7 key=$8
  timeout "$PER_RUN_S" "$PY" "$tool" check "$json" --top "$top" --k "$k" --cycles "$T" \
    --goal-out gout --goal-value "$gv" --attack-input sig --key "$key" --reduce full \
    --timeout-ms "$SOLVER_MS" --out "$pre.json" > "$pre.log" 2>&1 < /dev/null
}

while IFS=$'\t' read -r id top wrapper pkgs mods gv key cyc kmax pred; do
  case $id in ''|'#'*) continue ;; esac
  if [ $# -gt 0 ]; then
    want=0; for a in "$@"; do [ "$a" = "$id" ] && want=1; done
    [ "$want" = 1 ] || continue
  fi
  json=$BUILD/$id/$top.json
  if [ ! -s "$json" ] || [ ! -f "$BUILD/$id/meta.txt" ]; then
    echo "[$id] not built or netlist check failed (see build.sh output); skipped"; continue
  fi
  T=$cyc
  [ "$(cat "$BUILD/$id/reset_mode" 2>/dev/null)" = cycle0 ] && T=$((cyc + 1))
  K=${OT_KMAX:-$kmax}
  echo "[$id] $(sed -n 's/^netlist OK: //p' "$BUILD/$id/check.txt" | cut -d' ' -f1-3)  T=$T  goal gout==$gv  key $key"
  for k in $(seq 1 "$K"); do
    pre=$RES/${id}_k$k
    t0=$(date +%s)
    run_engine "$ENGINE" "$pre" "$json" "$top" "$k" "$T" "$gv" "$key"; rc=$?
    dt=$(( $(date +%s) - t0 ))
    case $rc in
      0) line=$(head -n1 "$pre.log") ;;
      124) line="UNKNOWN (wall-clock limit ${PER_RUN_S}s reached)" ;;
      2) line="UNKNOWN (solver limit reached) $(head -n1 "$pre.log")" ;;
      *) line="ERROR exit $rc: $(tail -n1 "$pre.log")" ;;
    esac
    echo "  k=$k  ${dt}s  $line"
    if [ "$rc" = 0 ]; then sed -n '2p' "$pre.log" | sed 's/^/        /'; fi
    if [ -n "$FASTSAT" ]; then
      run_engine "$FASTSAT" "$pre.fastsat" "$json" "$top" "$k" "$T" "$gv" "$key"; frc=$?
      echo "        fastsat exit $frc: $(head -n1 "$pre.fastsat.log")"
    fi
    if [ "$rc" = 0 ] && grep -q ATTACK_FOUND "$pre.log" && [ "${OT_ALL_K:-0}" != 1 ]; then break; fi
    if [ "$rc" != 0 ] && [ "${OT_ALL_K:-0}" != 1 ]; then echo "  (larger k skipped after a non-verdict)"; break; fi
  done
done < "$HERE/experiments.tsv"

"$PY" -I "$HERE/summarise.py" "$RES" "$HERE/experiments.tsv" "$BUILD" | tee "$RES/summary.txt"
tar -czf "$WORK/send_$STAMP.tar.gz" -C "$WORK" "results/$STAMP" \
  $(cd "$WORK" && ls -d "$(basename "$BUILD")"/*/meta.txt "$(basename "$BUILD")"/*/stat.txt "$(basename "$BUILD")"/*/yosys.log "$(basename "$BUILD")"/*/sv2v.log 2>/dev/null) 2>/dev/null
echo "== run.sh done. Send this file: $WORK/send_$STAMP.tar.gz"
