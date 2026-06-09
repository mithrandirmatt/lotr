#!/usr/bin/env python
# download_qwen.py
# Run this script inside your dev environment to download the Qwen3.6 model.
import os
import argparse
from huggingface_hub import HfApi, hf_hub_download

repo_id = "mudler/Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-GGUF"
file_name = "Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-I-Compact.gguf"
local_dir = os.path.expanduser("~/Downloads")

parser = argparse.ArgumentParser(description="Download Qwen model with optional debug output")
parser.add_argument("--debug", action="store_true", help="Enable verbose debugging output")
args = parser.parse_args()

if args.debug:
    print(f"[DEBUG] repo_id: {repo_id}")
    print(f"[DEBUG] file_name: {file_name}")
    print(f"[DEBUG] local_dir: {local_dir}")

print(f"Downloading {file_name} from {repo_id} to {local_dir}")
try:
    path = hf_hub_download(repo_id=repo_id, filename=file_name, local_dir=local_dir)
    print("Downloaded to", path)
    if args.debug:
        print(f"[DEBUG] File successfully downloaded at {path}")
except Exception as e:
    print("Error:", e)
    if args.debug:
        import traceback
        traceback.print_exc()
