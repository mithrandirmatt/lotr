#!/usr/bin/env bash
set -euo pipefail

MODELS_SCRIPT_NAME="ai_list.sh"

# Prefer direct Ollama HTTP API when running inside the dev container on the
# Docker network (no docker socket needed).
if command -v ollama >/dev/null 2>&1; then
  echo "Using local ollama CLI"
  ollama list || true
  exit 0
fi

# Determine base URL: prefer OLLAMA_URL env var, then service name on Docker
# network (lotr-ai), then host.docker.internal fallback (published port).
base_url="${OLLAMA_URL:-http://lotr-ai:11434}"

if command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
  echo "Querying Ollama HTTP API at $base_url/v1/models"
  if command -v curl >/dev/null 2>&1; then
    data=$(curl -sS --fail "$base_url/v1/models" 2>/dev/null || true)
  else
    data=$(wget -qO - "$base_url/v1/models" 2>/dev/null || true)
  fi
  if [ -n "$data" ]; then
    # Prefer jq for robust JSON parsing, fallback to grep+sed
    if command -v jq >/dev/null 2>&1; then
      out=$(printf '%s' "$data" | jq -r 'if has("data") then .data[] | (.id // .name // .model) elif has("models") then .models[] | (.id // .name // .model) elif type=="array" then .[] | (.id // .name // .model) else empty end' 2>/dev/null || true)
    else
      out=$(printf '%s' "$data" | grep -o '"id":"[^"]*"' | sed -E 's/"id":"([^"]+)"/\1/' || true)
    fi
    if [ -n "$out" ]; then
      printf '%s\n' "$out"
      exit 0
    fi
  else
        echo "HTTP query to $base_url/v1/models failed or returned empty; trying network name http://lotr-ai:11434/v1/models..." >&2
      # Try Docker network service name as fallback (works when dev container is on lotr-net)
      if command -v curl >/dev/null 2>&1; then
        data=$(curl -sS --fail "http://lotr-ai:11434/v1/models" 2>/dev/null || true)
      else
        data=$(wget -qO - "http://lotr-ai:11434/v1/models" 2>/dev/null || true)
      fi
      if [ -n "$data" ]; then
        if command -v jq >/dev/null 2>&1; then
          out=$(printf '%s' "$data" | jq -r 'if has("data") then .data[] | (.id // .name // .model) elif has("models") then .models[] | (.id // .name // .model) elif type=="array" then .[] | (.id // .name // .model) else empty end' 2>/dev/null || true)
        else
          out=$(printf '%s' "$data" | grep -o '"id":"[^"]*"' | sed -E 's/"id":"([^"]+)"/\1/' || true)
        fi
        if [ -n "$out" ]; then
          printf '%s\n' "$out"
          exit 0
        fi
      fi
  fi
fi

# Fallbacks: try docker CLI, then WSL (previous behavior)
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  cid=$(docker ps --filter "name=lotr-ai" --filter "status=running" -q || true)
  if [ -z "$cid" ]; then
    echo "No running lotr-ai container found; trying any ollama container..."
    cid=$(docker ps --filter "name=ollama" --filter "status=running" -q || true)
  fi
  if [ -z "$cid" ]; then
    echo "No running Ollama container found."
    exit 1
  fi
  echo "Using local docker CLI. Container: $cid"
  docker exec "$cid" ollama list || true
  exit 0
fi

if command -v wsl >/dev/null 2>&1; then
  echo "Using WSL docker in 'lotr-docker-service'"
  wsl -d lotr-docker-service -u root -- bash -lc 'cid=$(docker ps --filter "name=lotr-ai" --filter "status=running" -q || true); if [ -z "$$cid" ]; then echo "No running lotr-ai container found; trying any ollama container..."; cid=$(docker ps --filter "name=ollama" --filter "status=running" -q || true); fi; if [ -z "$$cid" ]; then echo "No running Ollama container found."; exit 1; fi; echo "Container: $$cid"; docker exec "$$cid" ollama list || true'
  exit $?
fi

echo "Could not discover Ollama models (no ollama CLI, HTTP API unreachable, and no docker/wsl available)." >&2
exit 2
