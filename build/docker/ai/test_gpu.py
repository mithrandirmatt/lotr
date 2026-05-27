#!/usr/bin/env python3
"""
test_gpu.py -- verify ROCm/HIP GPU visibility inside the lotr-ai container.

Checks:
  1. hipGetDeviceCount() > 0  (HIP / ROCm runtime sees the GPU)
  2. rocm-smi --showuse        (AMD system management interface reports the card)
  3. GET /api/ps               (Ollama reports loaded model layers; shows GPU vs CPU split)

Run from inside the container:
  python3 /app/test_gpu.py
"""
import ctypes, os, subprocess, sys, json, urllib.request

ROCm_LIB = "/usr/local/lib/ollama/rocm/libamdhip64.so.7"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def check_hip():
    print("\n--- HIP device count ---")
    if not os.path.exists(ROCm_LIB):
        print(f"  SKIP: {ROCm_LIB} not found (not a ROCm build)")
        return False
    try:
        hip = ctypes.CDLL(ROCm_LIB)
        hip.hipGetDeviceCount.restype = ctypes.c_int
        hip.hipGetDeviceCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
        count = ctypes.c_int(0)
        rc = hip.hipGetDeviceCount(ctypes.byref(count))
        if rc != 0:
            print(f"  FAIL: hipGetDeviceCount returned error {rc}")
            return False
        print(f"  OK: {count.value} HIP device(s) detected")
        return count.value > 0
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def check_rocm_smi():
    print("\n--- rocm-smi GPU utilisation ---")
    try:
        result = subprocess.run(
            ["rocm-smi", "--showuse"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(result.stdout.strip() or "  (no output)")
            return True
        else:
            print(f"  FAIL (exit {result.returncode}): {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("  SKIP: rocm-smi not found")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def check_ollama_ps():
    print(f"\n--- Ollama /api/ps (loaded models) ---")
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=5) as resp:
            data = json.loads(resp.read())
        models = data.get("models", [])
        if not models:
            print("  No models currently loaded in Ollama.")
            return True
        for m in models:
            name = m.get("name", "?")
            details = m.get("details", {})
            size_vram = m.get("size_vram", 0)
            size      = m.get("size", 0)
            gpu_pct   = round(100 * size_vram / size, 1) if size else 0
            cpu_pct   = 100 - gpu_pct
            print(f"  {name}: {gpu_pct}% GPU / {cpu_pct}% CPU  "
                  f"(vram={size_vram//1024//1024}MB total={size//1024//1024}MB)")
            if cpu_pct > 0:
                print(f"  WARNING: {cpu_pct}% of layers are running on CPU!")
        return True
    except Exception as e:
        print(f"  SKIP: could not reach Ollama at {OLLAMA_URL} ({e})")
        return False


if __name__ == "__main__":
    hip_ok  = check_hip()
    smi_ok  = check_rocm_smi()
    ps_ok   = check_ollama_ps()
    print()
    if hip_ok:
        print("RESULT: GPU accessible via HIP/ROCm")
    else:
        print("RESULT: GPU NOT detected via HIP (ROCm build may be missing or DXG unavailable)")
    sys.exit(0 if hip_ok else 1)
