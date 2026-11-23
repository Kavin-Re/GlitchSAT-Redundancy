#!/usr/bin/env bash
# Fetch PicoSoC at the pinned commit into <work>/src/picorv32. ISC licence (file COPYING in that repository).
# Usage: bash chips/picosoc/fetch.sh [work dir]   (default: ext/soc/work)
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${1:-$HERE/../../work}
URL=https://github.com/YosysHQ/picorv32
COMMIT=ef203c2b0a3fb793280f5114941416c425c5b461
D=$WORK/src/picorv32
mkdir -p "$WORK/src"
if [ ! -d "$D/.git" ]; then git clone --quiet "$URL" "$D"; fi
git -C "$D" checkout --quiet "$COMMIT"
have=$(git -C "$D" rev-parse HEAD)
[ "$have" = "$COMMIT" ] || { echo "fetch: $D is at $have, expected $COMMIT" >&2; exit 3; }
grep -q "ISC License" "$D/COPYING" || { echo "fetch: licence file changed" >&2; exit 3; }
echo "picorv32 at $have (ISC) in $D"
