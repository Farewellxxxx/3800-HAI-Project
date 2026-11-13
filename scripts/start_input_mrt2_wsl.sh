#!/usr/bin/env bash
# Start this checkout's existing web demo with the real MRT2 environment.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
python_bin="${JAMMATE_MRT2_PYTHON:-/home/wenhan/jammate-mrt2-venv/bin/python}"
export MAGENTA_HOME="${MAGENTA_HOME:-/mnt/e/study documents/2026 Fall/AIAA 3800 HAI/runtime/Magenta}"
export PYTHONPATH="$repo_dir/src:$repo_dir:$repo_dir/renderer_experiments"
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export JAMMATE_MRT2_MODEL=mrt2_small
export JAMMATE_MRT2_ENGINE=jax
if [[ ! -x "$python_bin" ]]; then
  echo 'Missing MRT2 Python environment; see docs/integration/INPUT_MRT2_REPORT.md.' >&2
  exit 1
fi
for variant in baseline optimized; do
  if [[ ! -f "web/$variant/dist/index.html" ]]; then
    echo "Build web/$variant first (node web/$variant/scripts/build.mjs)." >&2
    exit 1
  fi
done
exec "$python_bin" -u -m jammate.input_server --implementation workspace --port "${1:-4197}"
