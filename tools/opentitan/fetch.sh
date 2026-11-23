#!/usr/bin/env bash
# GlitchSAT ext/opentitan: download the pinned OpenTitan sources and the pinned sv2v converter.
# Own code, Apache-2.0.
#
# Usage (from anywhere):  bash ext/opentitan/fetch.sh
# Needs: git, curl, unzip, sha256sum (Ubuntu 24.04: sudo apt install -y git curl unzip).
# Writes only below ext/opentitan/work/ (or $OT_WORK).
#
# What it does
#   1. Shallow, blob-less, sparse clone of lowRISC/opentitan at tag Earlgrey-PROD-M6 (only
#      hw/ip/prim/rtl, hw/ip/prim_generic/rtl, hw/ip/aes/rtl are checked out), and checks the
#      commit hash. If git fails, it downloads the single files from raw.githubusercontent.com
#      at the same commit instead.
#   2. Copies the files listed in SOURCES.sha256 to work/src/ and checks every sha256.
#   3. Downloads sv2v v0.0.13 (sv2v-Linux.zip), checks its sha256 and unpacks it to work/tools/.
#      Set SV2V=/path/to/sv2v to use your own binary instead (its version is printed).
# Exit codes: 0 ok, 3 missing tool, download failure or checksum mismatch.
# Network (for a cloud VM with a host allowlist): github.com (git clone and the sv2v release URL),
#   objects.githubusercontent.com and release-assets.githubusercontent.com (the release-asset redirect
#   target of github.com/.../releases/download), raw.githubusercontent.com (single-file fallback of step 1).
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${OT_WORK:-$HERE/work}
SRC=$WORK/src

OT_URL=https://github.com/lowRISC/opentitan
OT_TAG=Earlgrey-PROD-M6
OT_COMMIT=a78922f14a8cc20c7ee569f322a04626f2ac6127
OT_RAW=https://raw.githubusercontent.com/lowRISC/opentitan/$OT_COMMIT
OT_DIRS=(hw/ip/prim/rtl hw/ip/prim_generic/rtl hw/ip/aes/rtl)

SV2V_VERSION=v0.0.13
SV2V_URL=https://github.com/zachjs/sv2v/releases/download/$SV2V_VERSION/sv2v-Linux.zip
# sha256 of sv2v-Linux.zip as downloaded from SV2V_URL on 2026-11-20.
SV2V_ZIP_SHA256=552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569288abeff28e1ff8

die() { echo "fetch.sh: error: $*" >&2; exit 3; }
need() {
  command -v "$1" >/dev/null 2>&1 || die "missing tool '$1'. On Ubuntu 24.04: sudo apt install -y git curl unzip"
}
need git; need curl; need unzip; need sha256sum

mkdir -p "$WORK"
echo "== fetch.sh  $(date -u +%Y-%m-%dT%H:%M:%SZ)  work dir: $WORK"

# ------------------------------------------------------------------ 1. OpenTitan sources
CLONE=$WORK/opentitan
ORIGIN=""
if [ -d "$CLONE/.git" ]; then
  have=$(git -C "$CLONE" rev-parse HEAD)
  [ "$have" = "$OT_COMMIT" ] || die "$CLONE is at commit $have, expected $OT_COMMIT. Delete $CLONE and run again."
  echo "OpenTitan: reusing $CLONE (commit $have)"
  git -C "$CLONE" sparse-checkout set "${OT_DIRS[@]}"
  ORIGIN=$CLONE
else
  echo "OpenTitan: cloning $OT_URL at tag $OT_TAG (shallow, blob-less, sparse)"
  if GIT_LFS_SKIP_SMUDGE=1 git clone --quiet --depth 1 --filter=blob:none --sparse --branch "$OT_TAG" "$OT_URL" "$CLONE" \
     && git -C "$CLONE" sparse-checkout set "${OT_DIRS[@]}"; then
    have=$(git -C "$CLONE" rev-parse HEAD)
    [ "$have" = "$OT_COMMIT" ] || die "tag $OT_TAG resolved to $have, expected $OT_COMMIT (the tag moved?). Stopping."
    echo "OpenTitan: commit $have"
    ORIGIN=$CLONE
  else
    echo "OpenTitan: git clone failed; downloading single files from $OT_RAW" >&2
    rm -rf "$CLONE"
    RAWDIR=$WORK/raw_opentitan
    rm -rf "$RAWDIR"; mkdir -p "$RAWDIR"
    while read -r sum path; do
      case $sum in ''|'#'*) continue ;; esac
      mkdir -p "$RAWDIR/$(dirname "$path")"
      curl -fsSL --retry 3 -o "$RAWDIR/$path" "$OT_RAW/$path" || die "download failed: $OT_RAW/$path"
    done < "$HERE/SOURCES.sha256"
    ORIGIN=$RAWDIR
  fi
fi

# ------------------------------------------------------------------ 2. copy + verify
rm -rf "$SRC"; mkdir -p "$SRC"
bad=0; n=0
while read -r sum path; do
  case $sum in ''|'#'*) continue ;; esac
  f=$ORIGIN/$path
  [ -f "$f" ] || { echo "MISSING   $path"; bad=1; continue; }
  got=$(sha256sum "$f" | cut -d' ' -f1)
  name=$(basename "$path")
  [ "$name" = LICENSE ] && name=OPENTITAN_LICENSE
  cp "$f" "$SRC/$name"
  if [ "$got" = "$sum" ]; then echo "OK        $got  $path"; else echo "MISMATCH  $got  $path (expected $sum)"; bad=1; fi
  n=$((n + 1))
done < "$HERE/SOURCES.sha256"
[ "$bad" = 0 ] || die "source check failed (see MISSING/MISMATCH lines above)"
{
  echo "Origin: $OT_URL"
  echo "Tag: $OT_TAG"
  echo "Commit: $OT_COMMIT"
  echo "Licence: Apache-2.0 (OPENTITAN_LICENSE, copied from the repository root)"
  echo "Fetched: $(date -u +%Y-%m-%dT%H:%M:%SZ) by ext/opentitan/fetch.sh"
  echo "Files ($n), sha256 checked against ext/opentitan/SOURCES.sha256"
} > "$SRC/SOURCE.txt"
touch "$SRC/.fetched"
echo "OpenTitan: $n files copied to $SRC, all sha256 OK"

# ------------------------------------------------------------------ 3. sv2v
if [ -n "${SV2V:-}" ]; then
  [ -x "$SV2V" ] || die "SV2V=$SV2V is not an executable file"
  echo "sv2v: using SV2V=$SV2V"
else
  DL=$WORK/dl_sv2v
  rm -rf "$DL"; mkdir -p "$DL"
  echo "sv2v: downloading $SV2V_URL"
  curl -fsSL --retry 3 -o "$DL/sv2v-Linux.zip" "$SV2V_URL" || die "download failed: $SV2V_URL"
  got=$(sha256sum "$DL/sv2v-Linux.zip" | cut -d' ' -f1)
  echo "sv2v: sha256 $got"
  [ "$got" = "$SV2V_ZIP_SHA256" ] || die "sv2v-Linux.zip sha256 is $got, expected $SV2V_ZIP_SHA256"
  rm -rf "$WORK/tools"; mkdir -p "$WORK/tools"
  unzip -q -o "$DL/sv2v-Linux.zip" -d "$WORK/tools"
  SV2V=$WORK/tools/sv2v-Linux/sv2v
  chmod +x "$SV2V"
fi
echo "sv2v: binary sha256 $(sha256sum "$SV2V" | cut -d' ' -f1)"
echo "sv2v: $("$SV2V" --version 2>&1 | head -n1)"

# ------------------------------------------------------------------ 4. other tools (report only)
if command -v yosys >/dev/null 2>&1; then
  yv=$(yosys -V 2>&1 | head -n1)
  echo "yosys: $yv"
  case $yv in *" 0.33"*) ;; *) echo "note: the repository's earlier results used apt Yosys 0.33; another version can give a different netlist." ;; esac
else
  echo "yosys: NOT FOUND (needed by build.sh): sudo apt install -y yosys"
fi
PY=${PY:-python3}
if "$PY" -c 'import z3' >/dev/null 2>&1; then
  echo "z3: $("$PY" -c 'import z3; print(z3.get_version_string())')"
else
  echo "z3: NOT FOUND for $PY (needed by run.sh): python3 -m venv .venv && . .venv/bin/activate && pip install -r ci/requirements-ci.txt"
fi
echo "== fetch.sh done"
