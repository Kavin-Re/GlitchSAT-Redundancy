#!/usr/bin/env bash
# GlitchSAT ext/opentitan: convert and synthesise every experiment in experiments.tsv.
# Own code, Apache-2.0.
#
# Usage:  bash ext/opentitan/build.sh [EXPERIMENT_ID ...]      (no id = all)
# Env:    OT_FRONTEND=sv2v (default) | slang
#           sv2v : sv2v v0.0.13 (from fetch.sh) converts SystemVerilog to Verilog, then the
#                  apt Yosys (0.33 on Ubuntu 24.04) reads it with read_verilog.
#           slang: the Yosys from OSS CAD Suite (fetch_osscad.sh) reads the SystemVerilog
#                  directly with its slang plugin (read_slang). A cross-check only: it is a
#                  different Yosys version, so netlists can differ from the sv2v path.
#         OT_NO_SIM=1  skip the `sim -w` reset write-back (fallback if it fails; the solver's
#                  cycle 0 is then the reset cycle and run.sh adds one cycle).
#         SV2V, YOSYS, PY, OT_WORK override tool paths / work dir.
# Output: work/build/<id>/ with <top>.v (sv2v path), synth.ys, yosys.log, stat.txt,
#         <top>.json (the netlist the solver reads), meta.txt, reset_mode.
# Exit:   0 all requested experiments built, 3 any failure (the others are still attempted).
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${OT_WORK:-$HERE/work}
SRC=$WORK/src
OUT=$WORK/build
FRONTEND=${OT_FRONTEND:-sv2v}
PY=${PY:-python3}

die() { echo "build.sh: error: $*" >&2; exit 3; }
[ -f "$SRC/.fetched" ] || die "sources missing in $SRC: run 'bash ext/opentitan/fetch.sh' first"
case $FRONTEND in
  sv2v)
    SV2V=${SV2V:-$WORK/tools/sv2v-Linux/sv2v}
    YOSYS=${YOSYS:-yosys}
    [ -x "$SV2V" ] || die "sv2v not found at $SV2V (run fetch.sh, or set SV2V=/path/to/sv2v)"
    ;;
  slang)
    YOSYS=${YOSYS:-$WORK/oss-cad-suite/bin/yosys}
    ;;
  *) die "OT_FRONTEND must be sv2v or slang, not '$FRONTEND'" ;;
esac
command -v "$YOSYS" >/dev/null 2>&1 || [ -x "$YOSYS" ] || die "yosys not found ($YOSYS). sv2v path: sudo apt install -y yosys; slang path: run fetch_osscad.sh"
RESET_MODE=sim
[ "${OT_NO_SIM:-0}" = 1 ] && RESET_MODE=cycle0

YV=$("$YOSYS" -V 2>&1 | head -n1)
echo "== build.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ)  frontend=$FRONTEND  reset_mode=$RESET_MODE"
echo "yosys: $YV"
[ "$FRONTEND" = sv2v ] && echo "sv2v: $("$SV2V" --version 2>&1 | head -n1)"
[ "$FRONTEND" = slang ] && OUT=$WORK/build_slang

# Files added to every experiment: generic primitive implementations, the security anchor
# buffer, and the local stand-ins (shims/) for the abstract primitives prim_flop, prim_buf,
# prim_xor2 and prim_flop_2sync.
COMMON_SRC=(prim_generic_flop.sv prim_generic_buf.sv prim_generic_xor2.sv prim_generic_flop_2sync.sv prim_sec_anchor_buf.sv)

# H3-style path rule (same idea as scripts/synth.sh): names go into a Yosys script file.
safe_path() {
  case $1 in
    '' | -* | *[[:cntrl:]]* | *\"* | *\'* | *\`* | *\;* | *\\* | *\#* | *' '*) return 1 ;;
  esac
  return 0
}
safe_top() {
  case $1 in '' | [!A-Za-z_]* | *[!A-Za-z0-9_]*) return 1 ;; esac
  return 0
}

build_one() {   # id top wrapper packages modules
  local id=$1 top=$2 wrapper=$3 pkgs=$4 mods=$5
  local d=$OUT/$id f
  safe_top "$top" || { echo "[$id] bad top name '$top'" >&2; return 1; }
  rm -rf "$d"; mkdir -p "$d"
  local -a files=() P M
  IFS=, read -r -a P <<< "$pkgs"
  IFS=, read -r -a M <<< "$mods"
  for f in "${P[@]}"; do files+=("$SRC/$f"); done
  for f in "${COMMON_SRC[@]}" "${M[@]}"; do files+=("$SRC/$f"); done
  for f in "$HERE"/shims/*.sv; do files+=("$f"); done
  files+=("$HERE/wrappers/$wrapper")
  for f in "${files[@]}"; do
    [ -f "$f" ] || { echo "[$id] missing source file $f" >&2; return 1; }
    safe_path "$f" || { echo "[$id] path not accepted (spaces, quotes, ';', '#', backslash): $f" >&2; return 1; }
  done
  safe_path "$d" || { echo "[$id] work path not accepted (spaces, quotes, ';', '#', backslash): $d" >&2; return 1; }

  local ys=$d/synth.ys
  if [ "$FRONTEND" = sv2v ]; then
    # --define=SYNTHESIS selects prim_assert_dummy_macros.svh (assertions expand to nothing),
    # as in OpenTitan's own Yosys flow (hw/ip/aes/pre_syn/syn_yosys.sh); sv2v also drops any
    # remaining assertions. --top removes modules the wrapper does not use.
    if ! "$SV2V" --define=SYNTHESIS --incdir="$SRC" --top="$top" --write="$d/$top.v" "${files[@]}" > "$d/sv2v.log" 2>&1; then
      echo "[$id] sv2v failed; last lines of $d/sv2v.log:" >&2; tail -n 30 "$d/sv2v.log" >&2; return 1
    fi
    [ -s "$d/$top.v" ] || { echo "[$id] sv2v wrote no output" >&2; return 1; }
    printf 'read_verilog "%s"\n' "$d/$top.v" > "$ys"
  else
    {
      printf 'plugin -i slang\n'
      printf 'read_slang -D SYNTHESIS -I "%s" --top %s' "$SRC" "$top"
      for f in "${files[@]}"; do printf ' "%s"' "$f"; done
      printf '\n'
    } > "$ys"
  fi
  {
    # The repository's plain flow (scripts/synth.sh), with three additions marked (+).
    printf 'hierarchy -check -top %s\n' "$top"
    printf 'proc\n'
    printf 'memory\n'          # (+) maps any inferred memory to flops and logic (no-op if none)
    printf 'async2sync\n'      # (+) asynchronous-reset flops -> plain flops plus reset muxes
    printf 'opt_clean\ntechmap\nopt_clean\n'
    printf 'abc -g AND,OR,XOR,MUX\nopt_clean\n'
    printf 'setattr -mod -unset keep_hierarchy *\nflatten\nopt_clean\ntechmap\nopt_clean\n'
    if [ "$RESET_MODE" = sim ]; then
      # (+) simulate the one reset cycle and store the resulting state as the power-up state
      printf 'sim -clock clk -n 1 -w %s\n' "$top"
      printf 'opt_clean\n'
    fi
    printf 'tee -q -o "%s" stat\n' "$d/stat.txt"
    printf 'write_json "%s"\n' "$d/$top.json"
  } >> "$ys"

  if ! timeout 1800 "$YOSYS" -q -l "$d/yosys.log" -s "$ys" > /dev/null 2>&1; then
    echo "[$id] yosys failed; last lines of $d/yosys.log:" >&2; tail -n 30 "$d/yosys.log" >&2; return 1
  fi
  [ -s "$d/$top.json" ] || { echo "[$id] yosys wrote no netlist" >&2; return 1; }
  echo "$RESET_MODE" > "$d/reset_mode"
  if ! "$PY" -I "$HERE/check_netlist.py" "$d/$top.json" "$top" "$RESET_MODE" > "$d/check.txt" 2>&1; then
    echo "[$id] netlist check failed:" >&2; cat "$d/check.txt" >&2; return 1
  fi
  {
    echo "experiment: $id"
    echo "top: $top"
    echo "frontend: $FRONTEND"
    echo "yosys: $YV"
    [ "$FRONTEND" = sv2v ] && echo "sv2v: $("$SV2V" --version 2>&1 | head -n1)"
    [ "$FRONTEND" = sv2v ] && echo "sv2v_sha256: $(sha256sum "$SV2V" | cut -d' ' -f1)"
    echo "reset_mode: $RESET_MODE"
    echo "netlist_sha256: $(sha256sum "$d/$top.json" | cut -d' ' -f1)"
    cat "$d/check.txt"
  } > "$d/meta.txt"
  echo "[$id] $(cat "$d/check.txt")"
  echo "[$id] netlist_sha256 $(sha256sum "$d/$top.json" | cut -d' ' -f1)"
  return 0
}

mkdir -p "$OUT"
status=0; built=0
while IFS=$'\t' read -r id top wrapper pkgs mods gv key cyc kmax pred; do
  case $id in ''|'#'*) continue ;; esac
  if [ $# -gt 0 ]; then
    want=0; for a in "$@"; do [ "$a" = "$id" ] && want=1; done
    [ "$want" = 1 ] || continue
  fi
  if build_one "$id" "$top" "$wrapper" "$pkgs" "$mods" < /dev/null; then built=$((built + 1)); else status=3; echo "[$id] NOT BUILT"; fi
done < "$HERE/experiments.tsv"
echo "== build.sh done: $built built, output in $OUT"
exit "$status"
