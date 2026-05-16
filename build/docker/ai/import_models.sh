#!/usr/bin/env bash
set -euo pipefail

MODEL_URLS="${1-}"
MODELS_DIR="/workspace/models"
LOG_DIR="/workspace/build/docker/logs"

mkdir -p "$MODELS_DIR" "$LOG_DIR"

echo "import_models.sh: MODELS_DIR=$MODELS_DIR" >&2

# If models dir already has files, prefer existing contents and try importing
if [ -n "$(ls -A "$MODELS_DIR" 2>/dev/null || true)" ]; then
  echo "Models directory non-empty; skipping downloads." >&2
  # Attempt to import any GGUF files into Ollama if the CLI exists
  if command -v ollama >/dev/null 2>&1; then
    for f in "$MODELS_DIR"/*; do
      if [ -f "$f" ]; then
        case "$f" in
          *.gguf|*.GGUF)
            echo "Attempting to import $f into Ollama" >&2
            ollama import "$f" 2>>"$LOG_DIR/ollama_import.log" || true
            ;;
        esac
      fi
    done
  fi
  exit 0
fi

if [ -z "$MODEL_URLS" ]; then
  echo "No MODEL_DOWNLOAD_URLS provided and models dir empty; nothing to do." >&2
  exit 0
fi

IFS=',' read -r -a urls <<< "$MODEL_URLS"
for url in "${urls[@]}"; do
  url="$(echo "$url" | xargs)"
  [ -z "$url" ] && continue
  fname="$(basename "$url")"
  dest="$MODELS_DIR/$fname"
  if [ -f "$dest" ]; then
    echo "$dest exists; skipping" >&2
    continue
  fi
  echo "Downloading $url -> $dest" >&2
  if command -v wget >/dev/null 2>&1; then
    wget -qO "$dest" "$url" || { echo "wget failed for $url" >&2; continue; }
  else
    curl -fsSL "$url" -o "$dest" || { echo "curl failed for $url" >&2; continue; }
  fi

  case "$dest" in
    *.zip)
      unzip -q "$dest" -d "$MODELS_DIR" && rm -f "$dest" || true
      ;;
    *.tar.gz|*.tgz)
      tar -xzf "$dest" -C "$MODELS_DIR" && rm -f "$dest" || true
      ;;
    *.tar)
      tar -xf "$dest" -C "$MODELS_DIR" && rm -f "$dest" || true
      ;;
    *)
      # leave as-is (gguf, etc)
      ;;
  esac
done

# Try to import any GGUF files into Ollama (best-effort)
if command -v ollama >/dev/null 2>&1; then
  for f in "$MODELS_DIR"/*; do
    if [ -f "$f" ]; then
      case "$f" in
        *.gguf|*.GGUF)
          echo "Importing $f into Ollama" >&2
          ollama import "$f" 2>>"$LOG_DIR/ollama_import.log" || true
          ;;
      esac
    fi
  done
fi

echo "import_models.sh: done" >&2
exit 0
