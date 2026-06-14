#!/usr/bin/env python3

from pathlib import Path
import runpy


script_path = Path(__file__).resolve().parent / "build" / "docker" / "check_gpu.py"
runpy.run_path(str(script_path), run_name="__main__")