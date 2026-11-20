#!/bin/sh
# usage: synth.sh <verilog> <top> <out.json> [flow]    flow = plain (default) | opt
# Output: flattened gate-level JSON (AND/OR/XOR/NOT/MUX + $_DFF_P_). Each module is mapped BEFORE flattening and no
# opt_merge runs after flatten, so redundant copies (duplicated compares) stay independent gates.
#  plain: proc; techmap; abc            (structure follows the RTL; used for the headline V0/V1/V2 results)
#  opt  : full yosys `synth` + dffunmap (aggressive optimisation; re-encodes the FSM next-state logic)
# H3 hardening: TOP must be a plain identifier and the file names plain paths (same rules as product/src runner.check_top /
# check_path). They are written as double-quoted tokens into a script FILE run as `yosys -q -s` (no shell, no -p with user text).
# The yosys commands and their order are unchanged, so the netlists are byte-identical to the previous version.
set -e
FLOW=${4:-plain}
die() { echo "synth.sh: error: $1" >&2; exit 3; }
[ $# -ge 3 ] || die "usage: synth.sh <verilog> <top> <out.json> [flow]"
chk_top() {
  case $1 in
    '' | [!A-Za-z_\$]* | *[!A-Za-z0-9_\$]*) die "top is not a plain module identifier ([A-Za-z_\$][A-Za-z0-9_\$]*)" ;;
  esac
  [ "${#1}" -le 255 ] || die "top is longer than 255 characters"
}
chk_path() {   # $1 = what, $2 = path
  case $2 in
    '') die "$1 path is empty" ;;
    -*) die "$1 path must not start with '-'" ;;
    *[[:cntrl:]]* | *\"* | *\'* | *\`* | *\;* | *\\* | *\#*) die "$1 path contains control characters, quotes, backtick, ';', backslash or '#'" ;;
  esac
}
chk_top "$2"
chk_path verilog "$1"
chk_path output "$3"
[ -f "$1" ] || die "verilog file not found: not a regular file"
SCR=$(mktemp "${TMPDIR:-/tmp}/synth_h3.XXXXXX") || die "cannot create script file"
trap 'rm -f "$SCR"' EXIT HUP INT TERM
{
  printf 'read_verilog "%s"\n' "$1"
  printf 'hierarchy -top %s\n' "$2"
  if [ "$FLOW" = opt ]; then
    printf 'synth -top %s\n' "$2"
    printf 'dffunmap\n'
  else
    printf 'proc\nopt_clean\ntechmap\nopt_clean\n'
  fi
  printf 'abc -g AND,OR,XOR,MUX\nopt_clean\nsetattr -mod -unset keep_hierarchy *\nflatten\nopt_clean\ntechmap\nopt_clean\n'
  printf 'write_json "%s"\n' "$3"
} > "$SCR"
yosys -q -s "$SCR"
