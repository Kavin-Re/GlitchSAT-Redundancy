#!/bin/sh
# Start GlitchSAT Studio from a clone of the repository (no install needed). Arguments are passed on,
# for example: bash tools/studio/glitchsat-studio.sh --port 8765 --no-browser
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
[ -x "$HERE/../../.venv/bin/python" ] && PY="$HERE/../../.venv/bin/python"
exec "$PY" "$HERE/studio.py" "$@"
