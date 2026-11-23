#!/usr/bin/env bash
# fetch_datasets.sh - download the public data sets listed in DATASETS.md for GlitchSAT
# software-only validation. Intended to run in a cloud Ubuntu 24.04 VM (also works on Linux Mint).
#
#   bash fetch_datasets.sh                 # default set (clear, permissive or copyleft licences)
#   bash fetch_datasets.sh --github-only   # only the git sources on github.com (no allowlist change needed)
#   bash fetch_datasets.sh --big           # also HWMCC'25 bit-level safety benchmarks (about 92 MB)
#   bash fetch_datasets.sh --noncommercial # also the FIVER artifact (non-commercial licence)
#   bash fetch_datasets.sh --hosts         # print the non-GitHub hosts needed, then exit
#   bash fetch_datasets.sh --manual        # only print the items left for manual licence review
#   bash fetch_datasets.sh --dry-run       # print what would be fetched, fetch nothing
#
# Network: a VM whose trusted network covers GitHub, PyPI and Ubuntu archives reaches all git
# sources; with --github-only the script needs only github.com. The direct file downloads need these extra hosts on a custom allowlist:
#   zenodo.org, rtfm.newae.com, eprint.iacr.org, artifacts.iacr.org (only with --noncommercial).
# A blocked host is reported as FAILED for that item; the other items still run.
# Target folder: $HOME/GlitchSAT-data (override with GLITCHSAT_DATA=/path).
# Every git source is pinned to a full commit hash and checked after checkout. Every file
# download prints its sha256; where the host publishes an md5 it is checked too. Static files are
# checked against a sha256: either one pinned in this script (5th argument of `get`) or, while no
# pin is written here yet, the sha256 of the first fetch, kept in $DEST/FIRST_FETCH.sha256 and
# checked on every later run (so a truncated or replaced file is caught). The two NewAE tutorial
# pages are rebuilt by the host from time to time and are deliberately left unpinned.
# For git checkouts the script prints one sha256 over the sorted per-file sha256 list
# (written to <dir>/MANIFEST.sha256), so a later run can be compared byte for byte.
# Needs: bash, git (2.25 or newer), curl, sha256sum, md5sum.
# Nothing downloaded is executed by this script. Treat all downloaded files as untrusted data:
# do not run scripts from them without reading them, and never unpickle files from them.

set -u
set -o pipefail

DEST="${GLITCHSAT_DATA:-$HOME/GlitchSAT-data}"
BIG=0
GHONLY=0
NONCOM=0
MANUAL_ONLY=0
DRY=0
for a in "$@"; do
  case "$a" in
    --big) BIG=1 ;;
    --github-only) GHONLY=1 ;;
    --hosts) printf '%s\n' zenodo.org rtfm.newae.com eprint.iacr.org 'artifacts.iacr.org (only with --noncommercial)'; exit 0 ;;
    --noncommercial) NONCOM=1 ;;
    --manual) MANUAL_ONLY=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

FAILED=()
SUMS=""

log() { printf '%s\n' "$*"; }

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing tool: $1" >&2; exit 3; }
}

record() {  # record <sha256> <label>
  SUMS+="$1  $2"$'\n'
  log "  sha256 $1  $2"
}

# git_pin <name> <repo-url> <full-commit> [sparse pattern ...]
# Shallow, blob-filtered fetch of exactly one commit; optional sparse checkout (non-cone patterns).
git_pin() {
  local name="$1" url="$2" commit="$3"; shift 3
  local dir="$DEST/$name"
  log ""
  log "== $name"
  log "   $url @ $commit"
  [ "$#" -gt 0 ] && log "   paths: $*"
  if [ "$DRY" = 1 ]; then return 0; fi
  if [ -d "$dir/.git" ]; then
    local have
    have="$(git -C "$dir" rev-parse HEAD 2>/dev/null || true)"
    if [ "$have" = "$commit" ]; then
      log "   already present at the pinned commit"
    else
      log "   $dir exists at '$have', expected $commit: delete it and run again"
      FAILED+=("$name (wrong commit in existing folder)")
      return 1
    fi
  else
    mkdir -p "$dir" || { FAILED+=("$name"); return 1; }
    (
      set -e
      cd "$dir"
      git init -q
      git remote add origin "$url"
      if [ "$#" -gt 0 ]; then
        git config core.sparseCheckout true
        printf '%s\n' "$@" > .git/info/sparse-checkout
      fi
      GIT_LFS_SKIP_SMUDGE=1 git fetch -q --depth 1 --filter=blob:none origin "$commit"
      GIT_LFS_SKIP_SMUDGE=1 git -c advice.detachedHead=false checkout -q FETCH_HEAD
    ) || { log "   FAILED to fetch $name"; FAILED+=("$name"); return 1; }
    local got
    got="$(git -C "$dir" rev-parse HEAD)"
    if [ "$got" != "$commit" ]; then
      log "   commit mismatch: got $got"
      FAILED+=("$name (commit mismatch)")
      return 1
    fi
  fi
  ( cd "$dir" && find . -type f -not -path './.git/*' -not -name MANIFEST.sha256 -print0 \
      | LC_ALL=C sort -z | xargs -0 -r sha256sum > MANIFEST.sha256 )
  local n h
  n="$(wc -l < "$dir/MANIFEST.sha256")"
  h="$(sha256sum "$dir/MANIFEST.sha256" | cut -d' ' -f1)"
  log "   files: $n, size: $(du -sh --exclude=.git "$dir" | cut -f1)"
  record "$h" "$name/MANIFEST.sha256 (manifest of $n files)"
}

# get <subdir> <filename> <url> [md5] [sha256]
#   md5:    as published by the host ("" if none).
#   sha256: pinned value; "" = check against the first fetch ($DEST/FIRST_FETCH.sha256);
#           "unpinned" = page that changes upstream, sha256 printed only.
get() {
  local sub="$1" fname="$2" url="$3" md5="${4:-}" pin="${5:-}"
  local dir="$DEST/$sub" out="$DEST/$sub/$2" label="$1/$2"
  log ""
  log "== $sub/$fname"
  log "   $url"
  if [ "$GHONLY" = 1 ]; then log "   skipped (--github-only; host not on github.com)"; return 0; fi
  if [ "$DRY" = 1 ]; then return 0; fi
  mkdir -p "$dir" || { FAILED+=("$label"); return 1; }
  if [ ! -s "$out" ]; then
    curl -fL --retry 3 --connect-timeout 30 -A "GlitchSAT-data-fetch" -o "$out.part" "$url" \
      && mv "$out.part" "$out" \
      || { rm -f "$out.part"; log "   FAILED download"; FAILED+=("$label"); return 1; }
  else
    log "   already present"
  fi
  if [ -n "$md5" ]; then
    local m
    m="$(md5sum "$out" | cut -d' ' -f1)"
    if [ "$m" != "$md5" ]; then
      log "   md5 MISMATCH: got $m, published $md5"
      FAILED+=("$label (md5 mismatch)")
      return 1
    fi
    log "   md5 ok ($md5, as published by the host)"
  fi
  local sha first="$DEST/FIRST_FETCH.sha256"
  sha="$(sha256sum "$out" | cut -d' ' -f1)"
  if [ "$pin" = unpinned ]; then
    log "   sha256 not pinned (page changes upstream)"
  elif [ -n "$pin" ]; then
    if [ "$sha" != "$pin" ]; then
      log "   sha256 MISMATCH: got $sha, pinned $pin (delete $out and run again)"
      FAILED+=("$label (sha256 mismatch)")
      return 1
    fi
    log "   sha256 ok (pinned)"
  else
    local was
    was="$(awk -v l="$label" '$2 == l { print $1 }' "$first" 2>/dev/null | tail -n 1)"
    if [ -z "$was" ]; then
      printf '%s  %s\n' "$sha" "$label" >> "$first"
      log "   sha256 recorded as first fetch in $first (copy it into this script as the pin)"
    elif [ "$sha" != "$was" ]; then
      log "   sha256 MISMATCH: got $sha, first fetch $was (delete $out and run again)"
      FAILED+=("$label (sha256 differs from first fetch)")
      return 1
    else
      log "   sha256 ok (same as first fetch)"
    fi
  fi
  log "   size: $(du -h "$out" | cut -f1)"
  record "$sha" "$label"
}

manual_list() {
  cat <<'EOF'

Left for MANUAL licence review (not downloaded by this script):
  1. FIRMER tool + benchmark netlists (AES/CRAFT/LED/GIFT/PRESENT/SIMON, .v/.nl/blacklists)
     https://github.com/S3L-official/FIRMER  commit 42c71b16b1fb1968b36310149ce175e0fde9e521
     Reason: repository has no LICENSE file; netlists derive from FIVER (non-commercial licence).
     Ask the authors before use beyond private comparison.
  2. ISCAS'85 + EPFL netlists re-synthesised with Cadence Genus
     https://github.com/jpsety/verilog_benchmark_circuits  commit b4c6b6203b95b5314d47365f4a8196c08145519b
     Reason: no LICENSE file.
  3. ISCAS'85/'89, ITC'99, LGSynth, IWLS 2005 archives at CTU Prague
     https://ddd.fit.cvut.cz/www/prj/Benchmarks/   (e.g. ISCAS.7z)
     Reason: page states no licence or terms of use. ITC'99 is available under EUPL-1.2 from
     cad-polito-it/I99T (fetched below), and EPFL under MIT from lsils/benchmarks (fetched below).
  4. Trust-Hub benchmarks  https://trust-hub.org/   Reason: registration and site terms; they are
     hardware-Trojan benchmarks, not fault countermeasures.
  5. GlitchResistor (DSN 2021) emulation results
     https://github.com/ucsb-seclab/glitch_resistor  commit 03fe4fb8cced4c00b27357ca8faba085fa5b0841
     Reason: no LICENSE file. Results are Python pickle files: never load them with pickle.
  6. FDTC 2018 slides "Laser Fault Injection at the CMOS 28 nm Technology Node"
     https://fdtc.deib.polimi.it/FDTC18/shared/FDTC%202018%20-%20session%201.1.pdf
     Reason: no licence stated. Facts are transcribed with citation in DATASETS.md.
  7. Bartkewitz et al., "Beware of Insufficient Redundancy", TCHES 2022(3):438-462, CC BY 4.0
     https://tches.iacr.org/index.php/TCHES/article/view/9708
     Reason: licence is clear but the host blocks scripted downloads; open it in a browser.
  8. Papers whose arXiv page shows no licence (read in a browser, transcribe with citation):
     SYNFI   https://arxiv.org/pdf/2205.04775
     FIRMER  https://arxiv.org/pdf/2307.00561  and  https://ches.iacr.org/2024/papers-issue-4/4_7.pdf
     CRAFT   https://arxiv.org/pdf/2503.03877
     Moro et al. EMFI fault model  https://arxiv.org/pdf/1402.6421
     Spensky et al. DSN 2021  https://gzs715.github.io/pubs/GLITCHING_DSN21.pdf
     Zussa et al. power-glitch / timing-violation papers  https://hal-emse.ccsd.cnrs.fr/emse-01109131
  9. FIVER artifact (licence: non-commercial use only, share-alike). Fetched only with --noncommercial.
EOF
}

if [ "$MANUAL_ONLY" = 1 ]; then manual_list; exit 0; fi

need git; need curl; need sha256sum; need md5sum
log "Target folder: $DEST"
[ "$DRY" = 1 ] && log "(dry run: nothing is downloaded)"
[ "$DRY" = 1 ] || mkdir -p "$DEST"

# sha256 pins of the static files: not written yet. The hosts (zenodo.org, eprint.iacr.org,
# artifacts.iacr.org) were not reachable from the machine these lines were written on, so the
# first fetch records them in $DEST/FIRST_FETCH.sha256; copy those values into the empty ''
# 5th arguments below to pin them for everyone.

# ---------------------------------------------------------------- 1. comparison tools and targets
# SYNFI (Apache-2.0): tool + Yosys-JSON netlists of aes_cipher_control_fsm, aes_cipher_control
# round counter and ibex_if_stage (paper Tables 1 and 7).
git_pin synfi https://github.com/lowRISC/synfi 2d08c4c84b04a4ed9998e1f09033691ca88f447e

# OpenTitan (Apache-2.0) at Earlgrey-PROD-M6: countermeasure primitives and the AES / life-cycle
# control logic analysed by SYNFI.
git_pin opentitan-Earlgrey-PROD-M6 https://github.com/lowRISC/opentitan a78922f14a8cc20c7ee569f322a04626f2ac6127 \
  '/LICENSE' '/hw/ip/prim/rtl/' '/hw/ip/prim_generic/rtl/' '/hw/ip/aes/rtl/' '/hw/ip/lc_ctrl/rtl/'

# OpenTitan at the commit the SYNFI examples name (097521294cd4...), AES control only.
git_pin opentitan-synfi-097521 https://github.com/lowRISC/opentitan 097521294cd43a3e059bed8c0cd2a710b4f7f73e \
  '/LICENSE' '/hw/ip/aes/rtl/' '/hw/ip/prim/rtl/prim_count*' '/hw/ip/prim/rtl/prim_double_lfsr*'

# ---------------------------------------------------------------- 2. benchmark circuits
# EPFL combinational benchmarks (MIT): AIG/BLIF/Verilog.
git_pin epfl-benchmarks https://github.com/lsils/benchmarks 82d8cc6910419298e713a46644ed59fd3df53038

# ITC'99 (EUPL-1.2): sequential, RT-level VHDL and gate-level .bench/.blif/.edf.
git_pin itc99-I99T https://github.com/cad-polito-it/I99T 8a2c3b500ee7ff20e7031de92592b737bedc6d8c

# ---------------------------------------------------------------- 3. cell libraries (timing, sizes)
# SkyWater sky130_fd_sc_hd (Apache-2.0): Liberty-as-JSON at 17 PVT corners (1.28 V to 1.95 V).
git_pin sky130_fd_sc_hd-timing https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1 \
  '/LICENSE' '/timing/'

# GF180MCU 7-track 5 V cells (Apache-2.0): Liberty at 1.62 V to 5.5 V corners.
git_pin gf180mcu_fd_sc_mcu7t5v0-liberty https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_sc_mcu7t5v0 43beb45e4d323a76239de436db2df6732e9a689b \
  '/LICENSE' '/liberty/'

# IHP SG13G2 standard cells (Apache-2.0): Liberty at 1.08/1.20/1.32/1.35/1.50/1.65 V and LEF.
git_pin ihp-sg13g2-stdcell https://github.com/IHP-GmbH/IHP-Open-PDK e73adb4045731ddec21634146d536380057f6a26 \
  '/LICENSE' '/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/' '/ihp-sg13g2/libs.ref/sg13g2_stdcell/lef/'

# OpenROAD-flow-scripts platforms: assembled sky130hd Liberty + merged LEF, Nangate45 (Apache-2.0,
# platform LICENSE included) Liberty + LEF. Nangate45 is the library SYNFI uses for Ibex.
git_pin orfs-platforms https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts f5504444e08f756336ed39935baafaaa98d45374 \
  '/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib' \
  '/flow/platforms/sky130hd/lef/sky130_fd_sc_hd.tlef' \
  '/flow/platforms/sky130hd/lef/sky130_fd_sc_hd_merged.lef' \
  '/flow/platforms/nangate45/LICENSE' \
  '/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib' \
  '/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef' \
  '/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.lef'

# ---------------------------------------------------------------- 4. physical measurements (real silicon)
# NewAE ChipWhisperer notebooks (GPL, per repository README): the glitching notebook and the
# recorded CW-Husky glitch-generator waveform data (FPGA-internal signals, no target).
git_pin chipwhisperer-jupyter https://github.com/newaetech/chipwhisperer-jupyter 52f124c858178d05a0071459c0df4f3b1f325e2b \
  '/README.md' '/demos/data/husky_glitch_data.npz' '/demos/husky/03 - Husky Glitching.ipynb'

# Executed tutorial pages with printed glitch-sweep outcomes on real targets (STM32F3, XMEGA).
# These pages are rebuilt by NewAE from time to time: the sha256 shows whether they changed.
get newae-rtfm SOLN_Fault_2_1_CWLITEARM.html \
  'https://rtfm.newae.com/tutorials/CWLITEARM/SOLN_Fault%202_1%20-%20Introduction%20to%20Voltage%20Glitching' '' unpinned
get newae-rtfm SOLN_Fault_2_2_CWLITEXMEGA.html \
  'https://rtfm.newae.com/tutorials/CWLITEXMEGA/SOLN_Fault%202_2%20-%20Voltage%20Glitching%20to%20Bypass%20Password' '' unpinned

# Kudera, Negative Voltage Fault Injection Attacks on Microcontrollers (thesis, CC BY 4.0).
get zenodo-2165679 negative_voltage_fault_injection_attacks_on_microcontrollers.pdf \
  'https://zenodo.org/records/2165679/files/Negative%20voltage%20fault%20injection%20attacks%20on%20microcontrollers.pdf?download=1' \
  2f51b4a5327cedde0453c89b3dd7f782

# Plundervolt data/code archive (CC BY 4.0), software undervolting of Intel CPUs.
get zenodo-4726719 plundervolt-master.zip \
  'https://zenodo.org/records/4726719/files/plundervolt-master.zip?download=1' \
  3fa13460c41a74fe98f2b6ddd9336190

# ---------------------------------------------------------------- 5. papers with CC BY 4.0 (for checking transcriptions)
get papers tollec_eprint_2024_247.pdf 'https://eprint.iacr.org/2024/247.pdf'

# ---------------------------------------------------------------- optional
if [ "$BIG" = 1 ]; then
  # HWMCC'25 (CC BY 4.0): bit-level safety model-checking benchmarks + results, for solver scaling.
  get zenodo-17428464 hwmcc25-benchmarks-bitlevel-safety.tar.gz \
    'https://zenodo.org/records/17428464/files/hwmcc25-benchmarks-bitlevel-safety.tar.gz?download=1' \
    3c64b406411a92473b25f79f4780e891
  get zenodo-17428464 hwmcc25-bitlevel-safety.csv \
    'https://zenodo.org/records/17428464/files/hwmcc25-bitlevel-safety.csv?download=1' \
    b1b6484ca7081a17b70e9cebe288e9dc
  get zenodo-17428464 README.md \
    'https://zenodo.org/records/17428464/files/README.md?download=1' \
    ef9d8e01e9a9d54cf0bfe76c9315fa1a
fi

if [ "$NONCOM" = 1 ]; then
  log ""
  log "FIVER: licence permits NON-COMMERCIAL use only; derivatives must use the same licence."
  log "Do not copy FIVER files into the Apache-2.0 GlitchSAT repository."
  get fiver tches-2021-a16.zip 'https://artifacts.iacr.org/files/tches/2021/tches-2021-a16.zip'
  git_pin fiver-src https://github.com/Chair-for-Security-Engineering/FIVER 176a1db7f80764543324db5378b6f82d4adebcbe
fi

# ---------------------------------------------------------------- summary
if [ "$DRY" = 0 ]; then
  printf '%s' "$SUMS" > "$DEST/SHA256SUMS.txt"
  log ""
  log "sha256 list written to $DEST/SHA256SUMS.txt"
fi
manual_list
if [ "${#FAILED[@]}" -gt 0 ]; then
  log ""
  log "FAILED items (${#FAILED[@]}):"
  for f in "${FAILED[@]}"; do log "  - $f"; done
  exit 1
fi
log ""
log "Done."
