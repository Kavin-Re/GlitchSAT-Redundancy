#!/bin/sh
# Fetch the OpenTitan files this example needs, at tag Earlgrey-PROD-M6 (commit a78922f14a8cc20c7ee569f322a04626f2ac6127),
# into ./ot/, and check every sha256 against ot_sources.sha256. OpenTitan is Apache-2.0 (ot/LICENSE).
#   sh fetch_ot.sh                 # git, sparse and blob-less (downloads only these files)
#   OT_LOCAL=/path/to/checkout sh fetch_ot.sh   # copy from a checkout you already have (same checks)
set -eu
cd "$(dirname "$0")"
COMMIT=a78922f14a8cc20c7ee569f322a04626f2ac6127
mkdir -p ot
if [ -n "${OT_LOCAL:-}" ]; then
  while read -r sum path; do
    case $sum in \#*) continue;; esac
    f=$OT_LOCAL/$path; [ -f "$f" ] || f=$OT_LOCAL/$(basename "$path"); [ -f "$f" ] || f=$OT_LOCAL/OPENTITAN_$(basename "$path")
    cp "$f" "ot/$(basename "$path")"
  done < ot_sources.sha256
else
  command -v git >/dev/null || { echo "git is needed" >&2; exit 3; }
  T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
  git init -q "$T/ot"; git -C "$T/ot" remote add origin https://github.com/lowRISC/opentitan
  git -C "$T/ot" sparse-checkout set --no-cone $(awk '!/^#/{print "/"$2}' ot_sources.sha256) >/dev/null 2>&1 || true
  git -C "$T/ot" config core.sparseCheckout true
  git -C "$T/ot" fetch -q --depth 1 --filter=blob:none origin "$COMMIT"
  git -C "$T/ot" checkout -q FETCH_HEAD
  awk '!/^#/{print $2}' ot_sources.sha256 | while read -r p; do cp "$T/ot/$p" "ot/$(basename "$p")"; done
fi
awk '!/^#/{n=split($2,a,"/"); print $1"  ot/"a[n]}' ot_sources.sha256 | sha256sum -c --quiet - && echo "OpenTitan sources ready in ot/ (checked)."
