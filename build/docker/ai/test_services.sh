#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for Ollama (11434) and AI server (3100)..."
for i in $(seq 1 60); do
  ok=true
  if ! curl -sSf http://localhost:11434/ >/dev/null 2>&1; then
    ok=false
  fi
  if ! curl -sSf http://localhost:3100/ >/dev/null 2>&1; then
    ok=false
  fi
  if $ok; then
    echo "Both services responding"
    exit 0
  fi
  sleep 1
done
echo "Services did not become ready in time" >&2
exit 2
