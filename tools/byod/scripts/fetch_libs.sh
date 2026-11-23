#!/bin/sh
# Fetch open standard-cell Liberty files at pinned commits, for the named flows (nangate45, sky130hd, ihp-sg13g2,
# gf180mcu) and the cross-checks. Optional: GlitchSAT itself needs no Liberty file, and a Liberty file you already have
# is read in place (design.liberty). Nothing here is copied into reports.
#
#   sh scripts/fetch_libs.sh            # into $GLITCHSAT_LIBS (default ~/.cache/glitchsat/libs)
#
# Sources (all fetched with git over HTTPS, sparse and blob-less, so only the named files are downloaded):
#   The-OpenROAD-Project/OpenROAD-flow-scripts @ d3043e68528ad089bff4dfad069ec35266276b55 (2026-11-21)
#     flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib   Nangate Open Cell Library (Nangate licence:
#        free use; see the header of the file and flow/platforms/nangate45/LICENSE). The SYNFI repository
#        (lowRISC/synfi) uses this same library through OpenROAD-flow-scripts.
#     flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib     SkyWater sky130_fd_sc_hd, Apache-2.0
#     flow/platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib   IHP SG13G2, Apache-2.0 (header)
#     flow/platforms/gf180/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib.gz  GF180MCU, Apache-2.0 (header)
#   google/skywater-pdk-libs-sky130_fd_sc_hd @ ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1 (main = branch-0.0.2)
#     cells/*/*__tt_025C_1v80.lib.json and LICENSE (Apache-2.0): the same cells as Liberty-in-JSON, used to cross-check
#     the sky130 .lib (that repository holds no .lib text files; they are generated from these JSON files).
# Exit: 0 ok, 3 git missing / download failed / checksum mismatch.
set -eu
DEST=${GLITCHSAT_LIBS:-$HOME/.cache/glitchsat/libs}
ORFS_URL=https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts
ORFS_COMMIT=d3043e68528ad089bff4dfad069ec35266276b55
SKY_URL=https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd
SKY_COMMIT=ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1
die() { echo "fetch_libs.sh: error: $*" >&2; exit 3; }
command -v git >/dev/null 2>&1 || die "git is needed (sudo apt install git)"
mkdir -p "$DEST/src"

sparse() {   # url commit dir paths...
  url=$1; commit=$2; dir=$3; shift 3
  if [ ! -d "$dir/.git" ]; then
    git init -q "$dir"
    git -C "$dir" remote add origin "$url"
    git -C "$dir" config core.sparseCheckout true
    git -C "$dir" config extensions.partialClone origin 2>/dev/null || true
  fi
  git -C "$dir" sparse-checkout set --no-cone "$@" >/dev/null 2>&1 || true
  git -C "$dir" fetch -q --depth 1 --filter=blob:none origin "$commit" || die "git fetch of $url failed"
  git -C "$dir" checkout -q FETCH_HEAD || die "checkout of $commit failed"
  [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ] || die "$url is not at $commit"
}

sparse "$ORFS_URL" "$ORFS_COMMIT" "$DEST/src/orfs" \
  /flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib /flow/platforms/nangate45/LICENSE \
  /flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib \
  /flow/platforms/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib \
  /flow/platforms/gf180/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib.gz /LICENSE
sparse "$SKY_URL" "$SKY_COMMIT" "$DEST/src/sky130_fd_sc_hd" '/LICENSE' '/cells/*/*__tt_025C_1v80.lib.json'

P=$DEST/src/orfs/flow/platforms
link() { mkdir -p "$DEST/$1"; ln -sf "$2" "$DEST/$1/$(basename "$2")"; }
link nangate45 "$P/nangate45/lib/NangateOpenCellLibrary_typical.lib"
link sky130hd "$P/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
link ihp-sg13g2 "$P/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
link gf180mcu "$P/gf180/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib.gz"

check() { echo "$1  $2" | sha256sum -c --quiet - || die "checksum mismatch: $2"; }
check 8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1 "$P/nangate45/lib/NangateOpenCellLibrary_typical.lib"
check ec0e1067a35c8bf20b11e58d1e8ac53326067e4dac84a125cc1b917a3518d0d9 "$P/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
check 7677a8918689f452e80405ad16a83e744709342574f2aedcc507c2758986b396 "$P/ihp-sg13g2/lib/sg13g2_stdcell_typ_1p20V_25C.lib"
check 63ae3cc65f05fca282b9e84eb77d576315c514da636cc1e9b14279a4a6de7ef6 "$P/gf180/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib.gz"
echo "Liberty files ready in $DEST (set GLITCHSAT_LIBS=$DEST if that is not the default)."
