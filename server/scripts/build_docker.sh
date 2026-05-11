#!/usr/bin/env sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "Building Docker image in ${DIR}"
docker build -t lotr-server:dev "${DIR}"
