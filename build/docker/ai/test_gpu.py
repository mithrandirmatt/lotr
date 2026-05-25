import ctypes, os
print("ROCR_VISIBLE_DEVICES:", os.environ.get("ROCR_VISIBLE_DEVICES", "NOT SET"))
lib = ctypes.CDLL("/usr/local/lib/ollama/rocm/libggml-hip.so", ctypes.RTLD_GLOBAL)
lib.ggml_backend_cuda_get_device_count.restype = ctypes.c_int
count = lib.ggml_backend_cuda_get_device_count()
print("GPU count:", count)
