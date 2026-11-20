#!/usr/bin/env bash
# Clean-unzip acceptance test for bundle B (full tree). Never touches the project tree.
# Usage: scripts/verify_bundle.sh [path/to/project_full_tree_*.zip]   (default: newest in /tmp/bundle_out)
# Work dir /tmp/bundle_verify (recreated only if it carries our marker), venv /tmp/bundle_verify_venv.
# Every step is run, failures are recorded (not fatal). Log: /tmp/bundle_verify_log.txt. Exit 1 if any step failed.
set -u
ZIP="${1:-$(ls -t /tmp/bundle_out/project_full_tree_*.zip 2>/dev/null | head -1)}"
[ -f "$ZIP" ] || { echo "no zip given/found" >&2; exit 2; }
D=/tmp/bundle_verify; V=/tmp/bundle_verify_venv; LOG=/tmp/bundle_verify_log.txt
if [ -e "$D" ]; then [ -f "$D/.bundle_verify_marker" ] && rm -rf "$D" || { echo "$D exists without marker; refusing" >&2; exit 2; }; fi
if [ -e "$V" ]; then [ -f "$V/.bundle_verify_marker" ] && rm -rf "$V" || { echo "$V exists without marker; refusing" >&2; exit 2; }; fi
mkdir -p "$D" && touch "$D/.bundle_verify_marker"
: > "$LOG"; FAILS=0; SUMMARY=""
step() { # name timeout cmd...
  local n="$1" t="$2"; shift 2
  echo "### $n :: $*" >> "$LOG"
  ( cd "$D" && timeout "$t" "$@" ) >> "$LOG" 2>&1; local rc=$?
  echo "### $n rc=$rc" >> "$LOG"
  if [ $rc -eq 0 ]; then SUMMARY="$SUMMARY\nPASS  $n"; else SUMMARY="$SUMMARY\nFAIL  $n (rc=$rc)"; FAILS=$((FAILS+1)); fi
}
unzip -q "$ZIP" -d "$D" || { echo "unzip failed"; exit 2; }
(cd "$D" && sha256sum dashboard/index.html | cut -d' ' -f1) > /tmp/bundle_verify_index.sha
python3 -m venv "$V" && touch "$V/.bundle_verify_marker"
PY="$V/bin/python"
step pip_install_product 600 "$PY" -m pip install -q "./product[test]" pytest z3-solver pyyaml
step pip_install_ci_requirements 300 "$PY" -m pip install -q -r ci/requirements-ci.txt
export PATH="$V/bin:$PATH"
step check_reproduce 120 "$PY" ci/check_reproduce.py
step check_reproduce_rerun 600 "$PY" ci/check_reproduce.py --rerun
step pytest_tests 900 "$PY" -m pytest tests -q -p no:cacheprovider
step pytest_product_tests 900 "$PY" -m pytest product/tests -q -p no:cacheprovider
step wow_checks 120 "$PY" docs/wow/check_hub.py
step check_numbers 300 "$PY" scripts/check_numbers.py
# the three START.md commands (START.md says: cp -r <repo> /tmp/proj_copy; here we run them inside the unzipped copy)
step start_cmd1_v1_k1 300 "$PY" scripts/glitchsat.py check reference/spike_netlists/v1.json --top v1 --k 1 --cycles 6
step start_cmd2_v2_k2 300 "$PY" scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 2 --cycles 6
step start_cmd3_v2_boot_ok 300 "$PY" scripts/glitchsat.py check reference/spike_netlists/v2.json --top v2 --k 1 --cycles 6 --goal-out boot_ok --goal-value 1
step dashboard_build 300 "$PY" dashboard/build.py
NEW=$(cd "$D" && sha256sum dashboard/index.html | cut -d' ' -f1)
if [ "$NEW" = "$(cat /tmp/bundle_verify_index.sha)" ]; then SUMMARY="$SUMMARY\nPASS  dashboard_index_unchanged"
else SUMMARY="$SUMMARY\nFAIL  dashboard_index_unchanged (sha differs after build.py)"; FAILS=$((FAILS+1)); fi
# unzip check: forbidden paths
BAD=$(unzip -Z1 "$ZIP" | grep -E '(^|/)(third_party_derived|compare|backup|shots|dl_repo|venv|__pycache__)/|\.zip$|\.egg-info|\.pyc$|\.(odb|vcd|fst|vvp)$' | grep -v '^docs/wow/shots/' | head)
if [ -z "$BAD" ]; then SUMMARY="$SUMMARY\nPASS  no_forbidden_paths_in_zip"; else SUMMARY="$SUMMARY\nFAIL  forbidden paths: $BAD"; FAILS=$((FAILS+1)); fi
# absolute-path inventory (in the pristine zip contents, re-extracted so test runs do not add files)
P=/tmp/bundle_verify_paths.txt; : > $P
unzip -Z1 "$ZIP" | while read -r f; do
  [ -f "$D/$f" ] || continue
  c=$(grep -I -c -E '/tmp/|<home>' "$D/$f" 2>/dev/null) || true
  [ "${c:-0}" -gt 0 ] && echo "$c $f"
done | sort -k2 > $P
RUNPATH=$(grep -E ' (scripts|ci|product/src|product/tests|product/scripts|tests|dashboard/build\.py|Makefile|formal/src|validation)(/|$)' $P | wc -l)
echo -e "$SUMMARY" | tee -a "$LOG"
echo "files with /tmp or <home>: $(wc -l < $P) (in run path dirs: $RUNPATH); list: $P"
echo "fails: $FAILS ; full log $LOG"
[ "$FAILS" -eq 0 ]
