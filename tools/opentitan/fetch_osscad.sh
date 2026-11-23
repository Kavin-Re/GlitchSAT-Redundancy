#!/usr/bin/env bash
# GlitchSAT ext/opentitan: OPTIONAL. Download OSS CAD Suite (a recent Yosys with the slang
# SystemVerilog plugin) for the cross-check frontend `OT_FRONTEND=slang bash build.sh`.
# Own code, Apache-2.0. Not needed for the main path (sv2v + apt Yosys).
#
# Usage:  bash ext/opentitan/fetch_osscad.sh
# Size:   about 754 MB download (754,243,903 bytes for the pinned file, checked 2026-11-20).
# The archive's sha256 is not pinned here (not downloaded when this script was written); it
# is printed and written to work/oss-cad-suite.sha256 so a later run can be compared.
# Release page: https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-11-19
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${OT_WORK:-$HERE/work}
OSSCAD_TAG=2026-11-19
OSSCAD_FILE=oss-cad-suite-linux-x64-20261119.tgz
OSSCAD_URL=https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$OSSCAD_TAG/$OSSCAD_FILE
OSSCAD_BYTES=754243903

die() { echo "fetch_osscad.sh: error: $*" >&2; exit 3; }
command -v curl >/dev/null 2>&1 || die "missing curl (sudo apt install -y curl)"
DL=$WORK/dl_osscad
mkdir -p "$DL"
echo "OSS CAD Suite: downloading $OSSCAD_URL"
curl -fL --retry 3 -C - -o "$DL/$OSSCAD_FILE" "$OSSCAD_URL" || die "download failed"
size=$(stat -c %s "$DL/$OSSCAD_FILE")
[ "$size" = "$OSSCAD_BYTES" ] || die "size $size bytes, expected $OSSCAD_BYTES"
sum=$(sha256sum "$DL/$OSSCAD_FILE" | cut -d' ' -f1)
echo "$sum  $OSSCAD_FILE" | tee "$WORK/oss-cad-suite.sha256"
rm -rf "$WORK/oss-cad-suite"
tar -xzf "$DL/$OSSCAD_FILE" -C "$WORK"
[ -x "$WORK/oss-cad-suite/bin/yosys" ] || die "archive did not contain oss-cad-suite/bin/yosys"
echo "yosys: $("$WORK/oss-cad-suite/bin/yosys" -V 2>&1 | head -n1)"
if "$WORK/oss-cad-suite/bin/yosys" -q -p 'plugin -i slang; help read_slang' > /dev/null 2>&1; then
  echo "slang plugin: loads"
else
  echo "slang plugin: did NOT load with 'plugin -i slang'; the slang frontend will not work" >&2
fi
echo "Use with: OT_FRONTEND=slang bash ext/opentitan/build.sh"
