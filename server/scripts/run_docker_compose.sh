#!/usr/bin/env sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${DIR}/docker"
docker compose up -d --build
