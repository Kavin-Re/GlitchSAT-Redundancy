#!/usr/bin/env bash
# One command: Verilog -> Yosys JSON netlist, using the project's documented 'plain' recipe
# (identical to YOSYS_PLAIN in src/faultbound_wt/runner.py and scripts/synth.sh of the repository).
# Usage: yosys_flow.sh design.v TOP out.json
# Prints the Yosys version and the netlist SHA-256 (a verdict belongs to ONE netlist hash: keep them together).
# Exit: 0 ok, 3 usage/input/yosys failure (same meaning as faultbound-wt exit 3).
set -u
if [ "$#" -ne 3 ]; then
  echo "usage: $0 design.v TOP out.json" >&2; exit 3
fi
V=$1; TOP=$2; OUT=$3
if ! command -v yosys >/dev/null 2>&1; then
  echo "error: yosys not found on PATH. Install it (e.g. 'sudo apt install yosys' or use product/Dockerfile) or pass an existing Yosys JSON netlist to faultbound-wt directly." >&2
  exit 3
fi
[ -f "$V" ] || { echo "error: no such file: $V" >&2; exit 3; }
# H2 (N1): TOP and the file names are VALIDATED, then written as double-quoted tokens into a Yosys SCRIPT FILE (a fixed template) that is run as
# `yosys -q -s file`; they are never pasted into a `-p` string or a shell command line. Yosys `exec`/shell tricks in a name cannot run.
case "$TOP" in [A-Za-z_\$]*) ;; *) echo "error: TOP must be a plain module name ([A-Za-z_\$][A-Za-z0-9_\$]*)" >&2; exit 3;; esac
case "$TOP" in *[!A-Za-z0-9_\$]*) echo "error: TOP must be a plain module name ([A-Za-z_\$][A-Za-z0-9_\$]*)" >&2; exit 3;; esac
for P in "$V" "$OUT"; do
  case "$P" in -*|"") echo "error: file name must not be empty or start with '-'" >&2; exit 3;; esac
  if printf '%s' "$P" | LC_ALL=C grep -q '[^ -~]'; then echo "error: file names with control or non-ASCII characters are not accepted" >&2; exit 3; fi
  case "$P" in *\;*|*\"*|*\'*|*\`*|*\\*|*\#*) echo "error: file names with quotes, backtick, ';', backslash or '#' are not accepted (they go into a Yosys script)" >&2; exit 3;; esac
done
VER=$(yosys -V 2>&1 | head -n1)
YS=$(mktemp "${TMPDIR:-/tmp}/yosys_flow.XXXXXX") || { echo "error: cannot create a temp file" >&2; exit 3; }
trap 'rm -f "$YS"' EXIT
{
  printf 'read_verilog "%s"\n' "$V"
  printf 'hierarchy -top %s\n' "$TOP"
  printf 'proc; opt_clean; techmap; opt_clean\n'
  printf 'abc -g AND,OR,XOR,MUX\n'
  printf 'opt_clean; setattr -mod -unset keep_hierarchy *; flatten; opt_clean\n'
  printf 'techmap; opt_clean\n'
  printf 'write_json "%s"\n' "$OUT"
} > "$YS"
if ! timeout 600 env -i PATH="$PATH" LC_ALL=C yosys -q -s "$YS" 2>"$OUT.log"; then
  echo "error: yosys failed (log: $OUT.log):" >&2; tail -n 20 "$OUT.log" >&2; exit 3
fi
rm -f "$OUT.log"
[ -s "$OUT" ] || { echo "error: yosys produced no output" >&2; exit 3; }
if command -v sha256sum >/dev/null 2>&1; then SHA=$(sha256sum "$OUT" | cut -d' ' -f1); else SHA=$(shasum -a 256 "$OUT" | cut -d' ' -f1); fi
echo "yosys: $VER"
echo "netlist: $OUT"
echo "netlist_sha256: $SHA"
echo "note: a verdict from faultbound-wt belongs to this netlist hash only (the report scope block repeats it)."
