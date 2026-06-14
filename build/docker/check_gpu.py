import torch, sys, os
print("torch:", torch.__version__)
print("LD_PRELOAD:", os.environ.get("LD_PRELOAD", "<not set>"))
print("LD_LIBRARY_PATH:", os.environ.get("LD_LIBRARY_PATH", "<not set>"))
print("HSA_ENABLE_DXG_DETECTION:", os.environ.get("HSA_ENABLE_DXG_DETECTION", "<not set>"))
print("HSA_OVERRIDE_GFX_VERSION:", os.environ.get("HSA_OVERRIDE_GFX_VERSION", "<not set>"))
print("cuda_available:", torch.cuda.is_available())
print("device_count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("device_name:", torch.cuda.get_device_name(0))
else:
    try:
        import ctypes
        for lib in (
            "libamdhip64.so.6",
            "libamdhip64.so.5",
            "/usr/local/lib/ollama/rocm/libamdhip64.so.7",
            "/usr/local/lib/ollama/rocm_v7_2/libamdhip64.so.7",
        ):
            try:
                hip = ctypes.CDLL(lib, use_errno=True)
                hip.hipGetDeviceCount.restype = ctypes.c_int
                hip.hipGetDeviceCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
                n = ctypes.c_int(0)
                rc = hip.hipGetDeviceCount(ctypes.byref(n))
                print(f"hipGetDeviceCount ({lib}) rc={rc} count={n.value}")
            except OSError as e:
                print(f"CDLL {lib} failed: {e}")
    except Exception as e:
        print("hip check error:", e)
    import subprocess
    try:
        r = subprocess.run(["rocminfo"], capture_output=True, text=True)
        if r.returncode == 0:
            lines = [l for l in r.stdout.splitlines() if "Agent" in l or "Name" in l or "gfx" in l]
            print("rocminfo:", "\n".join(lines[:10]))
        else:
            print("rocminfo rc:", r.returncode, r.stderr[:200])
    except FileNotFoundError:
        print("rocminfo: not installed")
