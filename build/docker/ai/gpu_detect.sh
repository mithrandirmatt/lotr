#!/usr/bin/env bash
# Simple GPU detection utility for container runtime
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia"
elif [ -c /dev/kfd ] || command -v rocminfo >/dev/null 2>&1; then
  echo "amd"
else
  echo "cpu"
fi
