#!/usr/bin/env bash
# Whole-chip front end and first analyses for OpenTitan Earl Grey and English Breakfast.
# Target: Ubuntu 24.04 cloud VM, 4 cores, 16 GB RAM, 40 GB disk. STATUS: WRITTEN, NOT RUN.
#
# Why this script exists: on the 2-core / 7 GB build machine the Earl Grey front end reads and elaborates the
# chip (38 s, 2.7 GB) and reaches 280,436 word-level cells (148 s, 2.9 GB), then gate mapping (Yosys techmap) is
# killed for lack of memory at 6.1 GB, flat and hierarchical alike (results/opentitan_attempt.json). This script
# repeats those steps where memory allows the next one and records time and peak memory of every step.
#
# Usage (from the repository root):   bash ext/soc/cloud/run_opentitan.sh 2>&1 | tee ot_run.log
# Send back: ext/soc/work/earlgrey/*.stat, *.log tails printed below, and ext/soc/results/ after the run.
# Each numbered step can be re-run alone:  STEPS="4 5" bash ext/soc/cloud/run_opentitan.sh
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SOC=$(cd "$HERE/.." && pwd)
export GSOC_WORK=${GSOC_WORK:-$SOC/work}
export STEP_TIMEOUT=${STEP_TIMEOUT:-14400}
STEPS=${STEPS:-"1 2 3 4 5 6 7 8"}
OSS=$GSOC_WORK/tools/oss-cad-suite
has() { case " $STEPS " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

if has 1; then
  echo "== 1. packages"
  sudo apt-get update -y
  sudo apt-get install -y git curl python3 python3-pip python3-yaml python3-numpy python3-pytest build-essential
  python3 -m pip install --user --break-system-packages hjson mako      # topgen (English Breakfast only)
fi

if has 2; then
  echo "== 2. Yosys with the SystemVerilog front end (OSS CAD Suite release; read_slang is a plugin there)"
  # Pinned release: set OSS_URL to the asset you verified; the default is the one named in ext/opentitan/fetch_osscad.sh.
  mkdir -p "$GSOC_WORK/tools"
  if [ ! -x "$OSS/bin/yosys" ]; then
    : "${OSS_URL:?set OSS_URL to an oss-cad-suite-linux-x64-*.tgz release asset (see ext/opentitan/fetch_osscad.sh)}"
    curl -L --fail -o "$GSOC_WORK/tools/oss.tgz" "$OSS_URL"
    sha256sum "$GSOC_WORK/tools/oss.tgz"
    tar -xzf "$GSOC_WORK/tools/oss.tgz" -C "$GSOC_WORK/tools"
  fi
  "$OSS/bin/yosys" -V
  "$OSS/bin/yosys" -p "plugin -i slang; help read_slang" | head -5
fi
export YOSYS="$OSS/bin/yosys"
export GSOC_YOSYS_SLANG="$YOSYS" GSOC_SLANG_PLUGIN=1

if has 3; then
  echo "== 3. fetch OpenTitan at Earlgrey-PROD-M6 (commit checked)"
  bash "$SOC/chips/earlgrey/frontend.sh" fetch
fi

if has 4; then
  echo "== 4. Earl Grey: elaborate and coarse (expected: as on the build machine, 675,182 then 280,436 RTL cells)"
  bash "$SOC/chips/earlgrey/frontend.sh" elab
  bash "$SOC/chips/earlgrey/frontend.sh" coarse
  grep -A6 "=== top_earlgrey ===" "$GSOC_WORK/earlgrey/coarse.stat" || true
fi

if has 5; then
  echo "== 5. Earl Grey: gates (this is the step that did not fit in 7 GB)"
  bash "$SOC/chips/earlgrey/frontend.sh" gates
  tail -40 "$GSOC_WORK/earlgrey/gates.stat" || true
  echo "If this step is killed again: run 'bash chips/earlgrey/frontend.sh hier' for per-module counts and report both."
fi

if has 6; then
  echo "== 6. Earl Grey: load, clock domains, black boxes, reset state; list the nets each draft goal names"
  cd "$SOC"
  python3 - <<'PY'
import sys, json
sys.path.insert(0, '.')
from gsoc import run, chip as chipmod
cfg = run.load_cfg('earlgrey')
s = run.Session(cfg, None, 'written')
rec = run.chip_step(s)
print(json.dumps({k: v for k, v in rec['stats'].items() if k != 'cell_types'}, indent=1)[:6000])
print('reset:', rec['reset'])
import re
for g in cfg['goals']:
    for spec in (g.get('hit') or []) + (g.get('quiet') or []):
        name = spec.split('=')[0]
        try:
            s.chip.word(name); print('OK      ', g['id'], name)
        except chipmod.ChipError:
            stem = name.split('.')[-1]
            cands = [n for n in s.chip.bits if stem in n][:12]
            print('MISSING ', g['id'], name, '-> candidates:', cands)
PY
fi

if has 7; then
  echo "== 7. Earl Grey: slices and searches for the goals whose nets exist (interval answers after 30 min each)"
  cd "$SOC"
  python3 glitchsat_soc.py analyse earlgrey --flow written --time-s 1800 --workers 2 || echo "analyse exit code $? (2 = BOUNDED only, 3 = a goal net is missing)"
  python3 glitchsat_soc.py report
fi

if has 8; then
  echo "== 8. English Breakfast: generate the top, then the same front end"
  OT=$GSOC_WORK/src/opentitan
  git -C "$OT" sparse-checkout add '/util/' '/hw/ip_templates/' '/hw/top_englishbreakfast/' '/hw/ip/' '/hw/lint/' '/hw/formal/' '/hw/data/'
  (cd "$OT" && python3 util/topgen.py -t hw/top_englishbreakfast/data/top_englishbreakfast.hjson -o hw/top_englishbreakfast/)
  ls "$OT/hw/top_englishbreakfast/rtl/autogen"
  echo "Next (manual, because the generated file list must be read first): copy chips/earlgrey/frontend.sh's elab step"
  echo "with hw/top_earlgrey replaced by hw/top_englishbreakfast and TOP=top_englishbreakfast, then steps 5-7."
fi
echo "== done. Report: every 'exit=... wall_s=... peak_rss_mb=...' line above, and work/earlgrey/*.stat."
