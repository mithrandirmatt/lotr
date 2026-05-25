#!/usr/bin/env bash
# start_services.sh -- entrypoint for lotr-ai container
# Ollama serve uses OLLAMA_HOST env var (set in Dockerfile) -- no --host/--port flags.
set -uo pipefail

# -----------------------------
# AI startup configuration
# Edit these variables (or set the corresponding env vars) to control
# automatic model startup/warmup behavior. Values here replace the old
# `ai.ini` file and are loaded at container start.
# -----------------------------
# Enable automatic model warmup/run at startup ('true' or 'false')
AI_USE=${AI_USE:-'True'}
# Model to warm/load (e.g. 'llama3.1:8b' or 'qwen3.5-claude-4.6-opus:latest')
AI_MODEL=${AI_MODEL:-'sorc/qwen3.5-claude-4.6-opus:latest'}
# Arbitrary args string to show in logs and include in warmup payload (value is informational)
AI_ARGS=${AI_ARGS:-'trust_remote_code=True'}
# Host-facing port you may publish Ollama to (for informational logs)
AI_HOST_PORT=${AI_HOST_PORT:-11435}
# Container port Ollama binds to (default used by image)
# The Ollama image binds to 11434 by default; keep that as the container default.
AI_CONTAINER_PORT=${AI_CONTAINER_PORT:-11434}

OLLAMA_BIN=${OLLAMA_BIN:-/usr/local/bin/ollama}
OLLAMA_HOST_CACHE=${OLLAMA_HOST_CACHE:-/ollama-cache}
OLLAMA_READY_TIMEOUT=${OLLAMA_READY_TIMEOUT:-120}
OLLAMA_LOG=${OLLAMA_LOG:-/var/log/ollama.log}
MCP_LOG=${MCP_LOG:-/var/log/mcp.log}
OLLAMA_PID=""
MCP_PID=""

mkdir -p "$OLLAMA_HOST_CACHE" /var/log

term() {
    echo "[start_services] Shutting down..."
    [ -n "$MCP_PID" ]    && kill -TERM "$MCP_PID"    2>/dev/null || true
    [ -n "$OLLAMA_PID" ] && kill -TERM "$OLLAMA_PID" 2>/dev/null || true
    wait
    exit 0
}
trap term SIGTERM SIGINT

if [ -x "$OLLAMA_BIN" ]; then
    # OLLAMA_HOST is already set in the image ENV (0.0.0.0:11434)
    export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}"

    # Derive the container bind port from OLLAMA_HOST unless explicitly set
    OLLAMA_BIND_PORT="${AI_CONTAINER_PORT:-${OLLAMA_HOST##*:}}"
    echo "[start_services] Configuration: AI_USE=${AI_USE} AI_MODEL=${AI_MODEL} AI_ARGS=${AI_ARGS} AI_HOST_PORT=${AI_HOST_PORT} AI_CONTAINER_PORT=${AI_CONTAINER_PORT} OLLAMA_BIND_PORT=${OLLAMA_BIND_PORT}"

    # Resolve OLLAMA_MODELS: externally-set env var wins; then auto-detect host-mounted
    # models at /root/.ollama/models (bind-mounted from the Windows host); then fall back
    # to the local cache directory.
    if [ -z "${OLLAMA_MODELS:-}" ]; then
        if [ -d "/root/.ollama/models/manifests" ] && [ -n "$(ls -A /root/.ollama/models/manifests 2>/dev/null)" ]; then
            OLLAMA_MODELS="/root/.ollama/models"
        else
            OLLAMA_MODELS="${OLLAMA_HOST_CACHE}/models"
            mkdir -p "$OLLAMA_MODELS"
        fi
    fi
    export OLLAMA_MODELS
    echo "[start_services] OLLAMA_MODELS=$OLLAMA_MODELS"
    echo "[start_services] Starting Ollama (OLLAMA_HOST=$OLLAMA_HOST)..."
    if [ "${GPU_VARIANT:-}" = "rocm" ] && [ -f "/opt/rocm/lib/librocdxg.so" ]; then
        # Ensure WSL_INTEROP points to a live socket so libdxcore.so can reach the Windows GPU driver.
        # The value passed via --env may be stale (tied to the docker.ps1 wsl.exe session).
        if [ -z "${WSL_INTEROP:-}" ] || [ ! -S "${WSL_INTEROP}" ]; then
            for _s in /run/WSL/*_interop; do
                [ -S "$_s" ] && { export WSL_INTEROP="$_s"; break; }
            done
        fi
        echo "[start_services] WSL_INTEROP=${WSL_INTEROP:-<not set>}"
        # Pre-warm: force the DXG D3D12 compute context open before Ollama starts.
        # The first hipInit() call through DXG can block WSLService for 30-120 s (cold-start
        # shader compilation in the Windows GPU driver).  If that happens inside Ollama's own
        # 30-second discovery timeout the runner falls back to CPU.  By doing it here first,
        # with up to 120 s of patience, the driver context is warm when Ollama asks for it.
        HIP_LIB="/usr/local/lib/ollama/rocm/libamdhip64.so.7"
        if [ -f "$HIP_LIB" ] && command -v python3 >/dev/null 2>&1; then
            echo "[start_services] GPU pre-warm: triggering DXG compute context (up to 120 s)..."
            LD_PRELOAD=/opt/rocm/lib/libhsa-runtime64.so.1:/opt/rocm/lib/librocdxg.so:/usr/lib/wsl/lib/libdxcore.so:/usr/lib/wsl/lib/libd3d12.so:/usr/lib/wsl/lib/libd3d12core.so \
            HSA_ENABLE_DXG_DETECTION=1 HSA_OVERRIDE_GFX_VERSION=11.0.0 \
            timeout 120 python3 - <<'PYEOF'
import ctypes, sys, os
try:
    hip = ctypes.CDLL('/usr/local/lib/ollama/rocm/libamdhip64.so.7')
    hip.hipInit.restype = ctypes.c_int
    r = hip.hipInit(0)
    if r != 0: sys.exit(f'hipInit failed: {r}')
    hip.hipSetDevice.restype = ctypes.c_int
    r = hip.hipSetDevice(0)
    if r != 0: sys.exit(f'hipSetDevice failed: {r}')
    hip.hipStreamCreate.restype = ctypes.c_int
    hip.hipStreamCreate.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    s = ctypes.c_void_p()
    r = hip.hipStreamCreate(ctypes.byref(s))
    if r != 0: sys.exit(f'hipStreamCreate failed: {r}')
    hip.hipStreamDestroy.restype = ctypes.c_int
    hip.hipStreamDestroy(s)
    print('GPU pre-warm OK: DXG compute context established')
except Exception as e:
    print(f'GPU pre-warm error: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF
            _pw_rc=$?
            if [ $_pw_rc -eq 0 ]; then
                echo "[start_services] GPU pre-warm succeeded -- DXG context is warm."
            elif [ $_pw_rc -eq 124 ]; then
                echo "[start_services] GPU pre-warm timed out after 120 s -- DXG compute may be unavailable; Ollama will try anyway."
            else
                echo "[start_services] GPU pre-warm failed (rc=$_pw_rc) -- Ollama will attempt GPU init and may fall back to CPU."
            fi
        else
            echo "[start_services] Skipping GPU pre-warm (HIP lib or python3 not found)."
        fi
        echo "[start_services] Preloading librocdxg + DXCore/D3D12 for ROCDXG/WSL GPU support"
        LD_PRELOAD=/opt/rocm/lib/libhsa-runtime64.so.1:/opt/rocm/lib/librocdxg.so:/usr/lib/wsl/lib/libdxcore.so:/usr/lib/wsl/lib/libd3d12.so:/usr/lib/wsl/lib/libd3d12core.so HSA_ENABLE_DXG_DETECTION=1 "$OLLAMA_BIN" serve >"$OLLAMA_LOG" 2>&1 &
    else
        "$OLLAMA_BIN" serve >"$OLLAMA_LOG" 2>&1 &
    fi
    OLLAMA_PID=$!
    echo "[start_services] Ollama PID $OLLAMA_PID -- waiting up to ${OLLAMA_READY_TIMEOUT}s..."
    elapsed=0
    until curl -sf http://localhost:${OLLAMA_BIND_PORT}/ >/dev/null 2>&1; do
        sleep 2; elapsed=$((elapsed+2))
        if [ "$elapsed" -ge "$OLLAMA_READY_TIMEOUT" ]; then
            echo "[start_services] WARNING: Ollama not ready after ${OLLAMA_READY_TIMEOUT}s -- continuing."
            break
        fi
    done
    curl -sf http://localhost:${OLLAMA_BIND_PORT}/ >/dev/null 2>&1 \
        && echo "[start_services] Ollama ready (bind port ${OLLAMA_BIND_PORT})." \
        || echo "[start_services] Ollama may still be starting."

    # If configured to use an AI model at startup, send a short warmup request
    # Normalize AI_USE: handle literal parameter-expansion patterns like
    # ${AI_USE:-'True'}, strip surrounding quotes/whitespace, and lowercase
    AI_USE_STRIPPED="${AI_USE}"
    # If AI_USE contains a literal parameter expansion such as ${AI_USE:-'True'},
    # extract the default value after ':-' and before the trailing '}'
    if [[ "${AI_USE_STRIPPED}" == \$\{*:-*} ]]; then
        AI_USE_STRIPPED="${AI_USE_STRIPPED#*:-}"
        AI_USE_STRIPPED="${AI_USE_STRIPPED%\}}"
    fi
    AI_USE_STRIPPED="${AI_USE_STRIPPED%\"}"
    AI_USE_STRIPPED="${AI_USE_STRIPPED#\"}"
    AI_USE_STRIPPED="${AI_USE_STRIPPED%\'}"
    AI_USE_STRIPPED="${AI_USE_STRIPPED#\'}"
    AI_USE_LC=$(echo "${AI_USE_STRIPPED}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
    if [ "${AI_USE_LC}" = "true" ] || [ "${AI_USE_LC}" = "1" ] || [ "${AI_USE_LC}" = "yes" ] || [ "${AI_USE_LC}" = "y" ]; then
        echo "[start_services] Auto-running model ${AI_MODEL} (warmup request starting in background)"
        # Build a minimal JSON payload and start the warmup request in background so
        # container startup doesn't block while the model loads (model loading can take minutes).
        payload=$(printf '%s' "{\"model\":\"%s\",\"prompt\":\"startup warmup\",\"max_tokens\":1,\"stream\":false}" "${AI_MODEL}")
        # Send the request in the background; capture output to a log for inspection.
        printf '%s' "${payload}" | curl -sS -X POST "http://localhost:${OLLAMA_BIND_PORT}/api/generate" -H 'Content-Type: application/json' -d @- > /var/log/ollama_warmup.log 2>&1 &
        echo "[start_services] Warmup background started for ${AI_MODEL}; logs -> /var/log/ollama_warmup.log"
    else
        echo "[start_services] Auto-run disabled by AI_USE=${AI_USE_STRIPPED}"
    fi
else
    echo "[start_services] Ollama binary not found at $OLLAMA_BIN -- skipping."
fi

echo "[start_services] Starting MCP/AI server..."
python3 /app/server.py >"$MCP_LOG" 2>&1 &
MCP_PID=$!

tail -n 0 -f "$OLLAMA_LOG" "$MCP_LOG" &
TAIL_PID=$!

wait "$MCP_PID"
RC=$?
echo "[start_services] MCP server exited ($RC)"
kill "$TAIL_PID" 2>/dev/null || true
[ -n "$OLLAMA_PID" ] && kill -TERM "$OLLAMA_PID" 2>/dev/null || true
exit $RC
