#!/bin/sh
# cloud_run.sh: the part of the secure-boot hardware work that needs real tools.
#
# Target: a cloud VM with Ubuntu 24.04 (apt: yosys 0.33, iverilog; pip in a venv: $ROOT/ci/requirements-ci.txt,
# i.e. z3-solver==5.4.1.0, the version the repository's results were recorded with, and pytest).
# Status: UNTESTED HERE. The machine these files were written on has no Yosys, no Icarus Verilog and no z3, so
# nothing below has been run yet; every number it prints is measured by the run itself.
#
#   GLITCHSAT_ROOT=/path/to/glitchsat sh ext/secboot_hw/cloud/cloud_run.sh
#
# Environment:
#   GLITCHSAT_ROOT   repository root (contains scripts/glitchsat.py and scripts/synth.sh); default: two levels up
#   OUT              output directory (default ext/secboot_hw/cloud_out/<UTC timestamp>)
#   KMAX=3           largest flip budget; budgets 1..KMAX are run
#   TIMEOUT=1800     solver seconds per (variant, flow, k); a timeout is recorded as UNKNOWN, never as "no attack"
#   FLOWS=plain,opt  synthesis flows of scripts/synth.sh
#   WORKERS          parallel variants (default nproc)
#   LARGE=1          also the full-round hash variants (h_single_full, h_all_full: 51 cycles, slow)
#   ALL_K=1          solve every budget even after a smaller one already found an attack
#   ONLY=a,b         only these variants
#   NO_INSTALL=1     tools are already installed
#
# Steps:
#   1. install tools, record versions (env.txt)
#   2. pytest (model, generated files, static RTL rules)
#   3. regenerate wrappers, vectors and testbenches, and check that nothing changed (generated files are committed)
#   4. Icarus Verilog: compile every RTL file with -g2005, then run every self-checking testbench
#      (23 variant benches replaying the model vectors with faults, the hash known-answer test, the MMIO bench)
#   5. Yosys: read every one-file design in Verilog-2005 mode (`read_verilog`, `hierarchy -check`, `check`)
#   6. engine/run_glitchsat.py: per variant and flow, synthesise with scripts/synth.sh, replay the vectors on the
#      gate-level netlist (engine/netsim.py), run scripts/glitchsat.py at k = 1..KMAX
#   7. summary.md, summary.json, studio_secboot_hw.json, and a tarball of $OUT
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
ROOT=${GLITCHSAT_ROOT:-$(cd "$HERE/../.." && pwd)}
[ -f "$ROOT/scripts/glitchsat.py" ] && [ -f "$ROOT/scripts/synth.sh" ] || {
  echo "cloud_run.sh: repository not found at $ROOT (set GLITCHSAT_ROOT)" >&2; exit 3; }
export GLITCHSAT_ROOT="$ROOT"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=${OUT:-$HERE/cloud_out/$STAMP}
KMAX=${KMAX:-3}
TIMEOUT=${TIMEOUT:-1800}
FLOWS=${FLOWS:-plain,opt}
WORKERS=${WORKERS:-$(nproc)}
mkdir -p "$OUT" "$HERE/build/sim"
cd "$HERE"

# 1. tools ------------------------------------------------------------------------------------------------------
if [ "${NO_INSTALL:-0}" != 1 ]; then
  SUDO=""; [ "$(id -u)" = 0 ] || SUDO=sudo
  $SUDO apt-get update -q
  $SUDO apt-get install -y -q yosys iverilog python3-venv python3-pip
  python3 -m venv "$HERE/.venv"
  . "$HERE/.venv/bin/activate"
  [ -f "$ROOT/ci/requirements-ci.txt" ] || { echo "cloud_run.sh: $ROOT/ci/requirements-ci.txt not found" >&2; exit 3; }
  python3 -m pip install -q -r "$ROOT/ci/requirements-ci.txt"
fi
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "os: $(. /etc/os-release && echo "$PRETTY_NAME")"
  echo "yosys: $(yosys -V)"
  echo "iverilog: $(iverilog -V 2>&1 | head -1)"
  echo "python: $(python3 -V 2>&1)"
  python3 -c "import z3; print('z3:', z3.get_version_string())" 2>/dev/null || echo "z3: not installed"
  echo "cpus: $(nproc)"
  echo "repository: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'not a git checkout'))"
  echo "pip freeze:"
  python3 -m pip freeze 2>/dev/null | sed 's/^/  /'
} | tee "$OUT/env.txt"

FAIL=0
note_fail() { echo "FAILED: $1" | tee -a "$OUT/failures.txt"; FAIL=1; }

# 2. tests ------------------------------------------------------------------------------------------------------
python3 -m pytest -q tests > "$OUT/pytest.txt" 2>&1 || note_fail "pytest (see pytest.txt)"
tail -3 "$OUT/pytest.txt"

# 3. generated files up to date ----------------------------------------------------------------------------------
python3 -m engine.wrappers > /dev/null
python3 -m engine.benches > /dev/null
python3 -m engine.studio > /dev/null
if command -v git > /dev/null && git -C "$HERE" rev-parse > /dev/null 2>&1; then
  git -C "$HERE" status --porcelain -- rtl/tops vectors tb/gen studio build/rtl build/manifest.json | tee "$OUT/generated_diff.txt"
  [ -s "$OUT/generated_diff.txt" ] && note_fail "generated files differ from the committed ones (generated_diff.txt)"
fi

# 4. Icarus Verilog -----------------------------------------------------------------------------------------------
SIM="$OUT/sim"; mkdir -p "$SIM"
RTL="rtl/sb_keccak_round.v rtl/sb_hash.v rtl/sb_cmp.v rtl/secboot_core.v rtl/secboot_mmio.v"
# shellcheck disable=SC2086
iverilog -g2005 -Wall -o "$SIM/lint.vvp" $RTL > "$SIM/lint.txt" 2>&1 || note_fail "iverilog -g2005 compile of rtl/ (sim/lint.txt)"
run_tb() {   # $1 = name, rest = sources
  n=$1; shift
  if iverilog -g2005 -o "$SIM/$n.vvp" "$@" > "$SIM/$n.compile.txt" 2>&1; then
    vvp -n "$SIM/$n.vvp" > "$SIM/$n.txt" 2>&1 || true
    if grep -q '^PASS' "$SIM/$n.txt"; then echo "  PASS $n"; else note_fail "testbench $n (sim/$n.txt)"; tail -5 "$SIM/$n.txt"; fi
  else
    note_fail "compile $n (sim/$n.compile.txt)"; tail -5 "$SIM/$n.compile.txt"
  fi
}
echo "simulation:"
run_tb tb_kat rtl/sb_keccak_round.v rtl/sb_hash.v tb/gen/tb_kat.v
# shellcheck disable=SC2086
run_tb tb_mmio $RTL tb/gen/tb_mmio.v
for tb in tb/gen/tb_*.v; do
  n=$(basename "$tb" .v); v=${n#tb_}
  [ "$n" = tb_kat ] || [ "$n" = tb_mmio ] && continue
  # shellcheck disable=SC2086
  run_tb "$n" rtl/sb_keccak_round.v rtl/sb_hash.v rtl/sb_cmp.v rtl/secboot_core.v "rtl/tops/top_$v.v" "$tb"
done | tee "$OUT/sim_summary.txt"
grep -q FAILED "$OUT/failures.txt" 2>/dev/null && FAIL=1

# 5. Yosys front end (Verilog-2005 mode, as scripts/synth.sh reads it) ---------------------------------------------
mkdir -p "$OUT/yosys_read"
for f in build/rtl/*.v; do
  v=$(basename "$f" .v)
  yosys -q -l "$OUT/yosys_read/$v.log" -p "read_verilog $f; hierarchy -check -top top_$v; proc; check" > /dev/null 2>&1 \
    || note_fail "yosys read of $f (yosys_read/$v.log)"
done
yosys -q -l "$OUT/yosys_read/secboot_mmio.log" -p "read_verilog $RTL; hierarchy -check -top secboot_mmio; proc; check" > /dev/null 2>&1 \
  || note_fail "yosys read of secboot_mmio"

# 6. synthesis, gate-level replay, GlitchSAT ------------------------------------------------------------------------
EXTRA=""
[ "${LARGE:-0}" = 1 ] && EXTRA="$EXTRA --large"
[ "${ALL_K:-0}" = 1 ] && EXTRA="$EXTRA --all-k"
[ -n "${ONLY:-}" ] && EXTRA="$EXTRA --only $ONLY"
# shellcheck disable=SC2086
python3 -m engine.run_glitchsat --root "$ROOT" --out "$OUT/glitchsat" --flows "$FLOWS" --kmax "$KMAX" \
  --timeout "$TIMEOUT" --workers "$WORKERS" $EXTRA 2>&1 | tee "$OUT/glitchsat.log"
python3 - "$OUT/glitchsat/summary.json" << 'EOF' || note_fail "netlist checks (gate-level replay or flop count), see glitchsat/summary.md"
import json, sys
d = json.load(open(sys.argv[1]))
bad = []
for r in d['variants']:
    for f, fr in r.get('flows', {}).items():
        if fr['synth']['exit']:
            bad.append(f"{r['name']}/{f}: synthesis failed")
        elif not fr.get('replay', {}).get('ok'):
            bad.append(f"{r['name']}/{f}: gate-level replay does not match the model")
        elif fr.get('flops_vs_model') != 'equal':
            print(f"note {r['name']}/{f}: {fr['flops_vs_model']}")
for b in bad:
    print('FAILED', b)
sys.exit(1 if bad else 0)
EOF

# 7. bundle -------------------------------------------------------------------------------------------------------
cp "$OUT/glitchsat/summary.md" "$OUT/summary.md" 2>/dev/null || true
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo "done: $OUT/summary.md ($OUT.tar.gz)"
[ "$FAIL" = 0 ] || { echo "some checks FAILED, see $OUT/failures.txt"; exit 1; }
