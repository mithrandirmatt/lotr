#!/usr/bin/env sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${DIR}"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install --upgrade pip
pip install -e .[tests]
echo "Starting dev server (uvicorn)"
python -m server.server.cli --dev
