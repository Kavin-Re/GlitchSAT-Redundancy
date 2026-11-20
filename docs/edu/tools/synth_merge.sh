#!/bin/sh
# Classroom variant of product/scripts/yosys_flow.sh: the SAME recipe plus ONE extra command, opt_merge, after flatten.
# opt_merge = common-subexpression elimination: identical gates reading identical inputs become one gate.
# usage: synth_merge.sh design.v TOP out.json     (prints Yosys version and netlist sha256)
# Safety (RT3 F1): TOP must be a plain identifier and the file names may not contain shell/Yosys metacharacters;
# the Yosys script is written to a temporary file with quoted arguments and run with `yosys -q -s` (no `-p` string built from user text).
set -eu
[ $# -eq 3 ] || { echo "usage: synth_merge.sh design.v TOP out.json" >&2; exit 3; }
V=$1; TOP=$2; OUT=$3
case "$TOP" in
  ''|[0-9]*|*[!A-Za-z0-9_\$]*) echo "error: TOP '$TOP' is not a plain module identifier" >&2; exit 3;;
esac
for P in "$V" "$OUT"; do
  case "$P" in
    ''|-*|*[!A-Za-z0-9_./+-]*) echo "error: path '$P' contains characters that are not allowed (letters, digits, _ . / + - only; no leading '-')" >&2; exit 3;;
  esac
done
[ -f "$V" ] || { echo "error: no such file: $V" >&2; exit 3; }
T=$(mktemp -d "${TMPDIR:-/tmp}/synth_merge.XXXXXX")
trap 'rm -rf "$T"' EXIT INT TERM
cat > "$T/flow.ys" <<YS
read_verilog "$V"
hierarchy -top $TOP
proc
opt_clean
techmap
opt_clean
abc -g AND,OR,XOR,MUX
opt_clean
setattr -mod -unset keep_hierarchy *
flatten
opt_merge
opt_clean
techmap
opt_clean
write_json "$OUT"
YS
echo "yosys: $(yosys -V 2>&1 | head -n1)"
yosys -q -s "$T/flow.ys"
echo "netlist: $OUT"
echo "netlist_sha256: $(sha256sum "$OUT" | cut -d' ' -f1)"
