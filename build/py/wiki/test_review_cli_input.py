#!/usr/bin/env python3
import importlib.util
import builtins
import json
import sys

spec = importlib.util.spec_from_file_location('review_cli_mod','build/py/wiki/review_cli.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Prepare fake inputs: 'p' to preview, then 'q' to quit
inputs = iter(['p', 'q'])
original_input = builtins.input

def fake_input(prompt=''):
    try:
        v = next(inputs)
        print(prompt + v)
        return v
    except StopIteration:
        return 'q'

builtins.input = fake_input
try:
    sys.exit(mod.main(['--preview', 'browser', '--dry-run']))
finally:
    builtins.input = original_input
