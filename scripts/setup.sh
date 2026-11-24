#!/usr/bin/env bash
# Create .venv and install everything needed to run the courses.
# Usage: ./scripts/setup.sh [extra ...]   extras: sql deep-learning geospatial explainability data-cleaning game-ai legacy all
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in python3.11 python3.12 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
[ -n "$PY" ] || { echo "Python 3.10-3.12 not found. Install it first (see README)."; exit 1; }
VER=$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo "Using $PY ($VER)"
case "$VER" in 3.10|3.11|3.12) ;; *) echo "Warning: Python $VER is untested; 3.10-3.12 recommended (TensorFlow needs <=3.12).";; esac

[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install --no-build-isolation "git+https://github.com/Kaggle/learntools.git"

for extra in "$@"; do
  f="requirements/$extra.txt"
  [ -f "$f" ] || { echo "Unknown extra '$extra' (see requirements/)"; exit 1; }
  pip install -r "$f"
done

if [ "$(uname)" = "Darwin" ] && ! python -c "import xgboost" >/dev/null 2>&1; then
  echo
  echo "NOTE: XGBoost can't load. Install OpenMP with:  brew install libomp"
fi

echo
echo "Done. Next:"
echo "  source .venv/bin/activate"
echo "  python scripts/download_data.py --list      # then download a course's data"
echo "  jupyter lab"
