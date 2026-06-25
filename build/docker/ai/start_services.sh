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
# Set to 'false' to skip starting the Ollama daemon entirely (e.g. when using a host-side Ollama).
START_OLLAMA=${START_OLLAMA:-false}
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
PREWARM_PID=""

mkdir -p "$OLLAMA_HOST_CACHE" /var/log

term() {
    echo "[start_services] Shutting down..."
    [ -n "$MCP_PID" ]      && kill -TERM "$MCP_PID"      2>/dev/null || true
    [ -n "$OLLAMA_PID" ]   && kill -TERM "$OLLAMA_PID"   2>/dev/null || true
    [ -n "$PREWARM_PID" ]  && kill -TERM "$PREWARM_PID"  2>/dev/null || true
    wait
    exit 0
}
trap term SIGTERM SIGINT

if [ "${START_OLLAMA}" != "true" ]; then
    echo "[start_services] Ollama startup disabled (START_OLLAMA=${START_OLLAMA}) -- skipping."
elif [ -x "$OLLAMA_BIN" ]; then
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
            echo "[start_services] GPU pre-warm: opening DXG compute context and holding it open until Ollama is ready..."
            # The previous approach ran hipInit() in a short-lived child process and then exited.
            # The DXG compute context was released when that process ended, so Ollama's own GPU
            # init still hit a cold-start inside its 30-second discovery deadline.
            #
            # Fix: the pre-warm process now holds the HIP context open in a blocking wait loop.
            # We start it in the background, then later kill it once Ollama's HTTP endpoint
            # responds -- by then Ollama has already completed its own GPU init with the driver
            # context already warm.
            LD_PRELOAD=/opt/rocm/lib/libhsa-runtime64.so.1:/opt/rocm/lib/librocdxg.so:/usr/lib/wsl/lib/libdxcore.so:/usr/lib/wsl/lib/libd3d12.so:/usr/lib/wsl/lib/libd3d12core.so \
            HSA_ENABLE_DXG_DETECTION=1 HSA_OVERRIDE_GFX_VERSION=11.0.0 \
            python3 - <<'PYEOF' &
import ctypes, sys, os, time, signal

def _sig(_s, _f): sys.exit(0)
signal.signal(signal.SIGTERM, _sig)
signal.signal(signal.SIGINT,  _sig)

try:
    hip = ctypes.CDLL('/usr/local/lib/ollama/rocm/libamdhip64.so.7')
    hip.hipInit.restype = ctypes.c_int
    r = hip.hipInit(0)
    if r != 0:
        print(f'[prewarm] hipInit failed: {r}', file=sys.stderr); sys.exit(1)
    hip.hipSetDevice.restype = ctypes.c_int
    r = hip.hipSetDevice(0)
    if r != 0:
        print(f'[prewarm] hipSetDevice failed: {r}', file=sys.stderr); sys.exit(1)
    hip.hipStreamCreate.restype = ctypes.c_int
    hip.hipStreamCreate.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    s = ctypes.c_void_p()
    r = hip.hipStreamCreate(ctypes.byref(s))
    if r != 0:
        print(f'[prewarm] hipStreamCreate failed: {r}', file=sys.stderr); sys.exit(1)
    print('[prewarm] DXG compute context open -- holding until signalled', flush=True)
    # Keep the context alive; parent will SIGTERM us once Ollama is ready
    while True:
        time.sleep(5)
except Exception as e:
    print(f'[prewarm] error: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF
            PREWARM_PID=$!
            echo "[start_services] GPU pre-warm PID $PREWARM_PID -- waiting up to 30 s for context..."
            # Give the pre-warm process time to complete hipInit (the slow part)
            _pw_waited=0
            while [ $_pw_waited -lt 30 ]; do
                sleep 2; _pw_waited=$((_pw_waited + 2))
                # If the process has already exited it failed
                if ! kill -0 "$PREWARM_PID" 2>/dev/null; then
                    echo "[start_services] GPU pre-warm exited early -- Ollama will attempt GPU init unaided."
                    PREWARM_PID=""
                    break
                fi
                break  # still running after 2 s -- context is warm, proceed
            done
            if [ -n "${PREWARM_PID:-}" ] && kill -0 "$PREWARM_PID" 2>/dev/null; then
                echo "[start_services] GPU pre-warm holding DXG context (PID $PREWARM_PID)."
            fi
        else
            echo "[start_services] Skipping GPU pre-warm (HIP lib or python3 not found)."
            PREWARM_PID=""
        fi

        # Gate: verify rocm-smi sees the GPU before starting Ollama
        if command -v rocm-smi >/dev/null 2>&1; then
            echo "[start_services] rocm-smi GPU check:"
            rocm-smi --showuse 2>/dev/null || echo "[start_services] WARNING: rocm-smi --showuse failed -- GPU may not be accessible."
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
    # Ollama has completed GPU init -- release the pre-warm context holder
    if [ -n "${PREWARM_PID:-}" ] && kill -0 "$PREWARM_PID" 2>/dev/null; then
        echo "[start_services] Releasing GPU pre-warm context (PID $PREWARM_PID)."
        kill -TERM "$PREWARM_PID" 2>/dev/null || true
        wait "$PREWARM_PID" 2>/dev/null || true
        PREWARM_PID=""
    fi

    # --------------------------------------------------------
    # Create :copilot model variant for VS Code Copilot agent.
    # num_ctx=262144 provides more working memory for complex repository tasks.
    # Keep reasoning concise so responses remain actionable and within limits.
    # num_predict=2048 prevents runaway output that triggers "Response too long".
    # Always recreate so parameters stay in sync with this script.
    # --------------------------------------------------------
    if [ -n "${AI_MODEL:-}" ]; then
        COPILOT_MODEL="${AI_MODEL%:*}:copilot"
        echo "[start_services] Creating/updating Copilot model ${COPILOT_MODEL}..."
        curl -sSL -X POST "http://localhost:${OLLAMA_BIND_PORT}/api/create" \
            -H 'Content-Type: application/json' \
            -d "{\"model\":\"${COPILOT_MODEL}\",\"from\":\"${AI_MODEL}\",\"system\":\"Use concise reasoning for complex tasks. Keep final answers direct and actionable.\",\"parameters\":{\"num_ctx\":262144,\"num_predict\":2048}}" \
            >> "$OLLAMA_LOG" 2>&1 \
            && echo "[start_services] Copilot model ${COPILOT_MODEL} ready." \
            || echo "[start_services] WARNING: failed to create Copilot model ${COPILOT_MODEL}."
        echo "[start_services] Warming up ${COPILOT_MODEL} in background..."
        ( sleep 5; curl -sS -X POST "http://localhost:${OLLAMA_BIND_PORT}/api/generate" \
            -H 'Content-Type: application/json' \
            -d "{\"model\":\"${COPILOT_MODEL}\",\"prompt\":\"hi\",\"num_predict\":1,\"stream\":false}" \
            >> /var/log/ollama_warmup.log 2>&1 ) &
    fi

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
        # Sleep 5s first to let Ollama finish indexing its model manifests before sending the request.
        payload=$(printf '{"model":"%s","prompt":"startup warmup","num_predict":1,"stream":false}' "${AI_MODEL}")
        # Send the request in the background; capture output to a log for inspection.
        (sleep 5; printf '%s' "${payload}" | curl -sS -X POST "http://localhost:${OLLAMA_BIND_PORT}/api/generate" -H 'Content-Type: application/json' -d @- > /var/log/ollama_warmup.log 2>&1) &
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
