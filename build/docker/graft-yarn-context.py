#!/usr/bin/env python3
"""
graft-yarn-context.py

Rewrites a GGUF's metadata (NOT its weights -- no re-quantization or
re-training) to enable YaRN RoPE scaling so llama-server can serve it at a
context length beyond the model's originally-trained context.

Why this is needed (confirmed by reading this repo's own llama.cpp
checkout, build/docker/cache/llama.cpp/tools/server/server-context.cpp
lines 1131-1136): llama-server's per-slot context is unconditionally capped
to `<arch>.context_length` (n_ctx_train), regardless of any
--rope-scaling/--rope-scale/--yarn-orig-ctx CLI flags passed at launch.
Passing those flags alone (confirmed via a live manual test) does NOT
raise the effective context -- the GGUF's own `context_length` metadata
field has to be raised too. Raising it alone (without also adding proper
YaRN scaling metadata) would make the model naively extrapolate RoPE
positions past its real trained window, which produces degraded/garbage
output -- so this script always grafts both together.

Usage:
    python build/docker/graft-yarn-context.py \
        --input do/agent/models/qwen35-9b_lotr_lora-q4_k_m.gguf \
        --output do/agent/models/qwen35-9b_lotr_lora-q4_k_m-yarn131k.gguf \
        --target-context 131072 --orig-context 32768
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GGUF_PY = REPO_ROOT / "build" / "docker" / "cache" / "llama.cpp" / "gguf-py"
if str(GGUF_PY) not in sys.path:
    sys.path.insert(0, str(GGUF_PY))

import gguf  # noqa: E402
from gguf.scripts.gguf_new_metadata import copy_with_new_metadata, MetadataDetails  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, help="Source GGUF (unmodified)")
    parser.add_argument("--output", required=True, type=Path, help="Destination GGUF (new file)")
    parser.add_argument("--target-context", type=int, default=131072, help="New effective context length")
    parser.add_argument("--orig-context", type=int, default=32768, help="Model's real trained context length")
    args = parser.parse_args()

    if args.output.exists():
        parser.error(f"--output {args.output} already exists; refusing to overwrite")

    factor = args.target_context / args.orig_context
    if factor != int(factor) or factor < 1:
        parser.error(f"--target-context must be a whole multiple of --orig-context (got factor={factor})")

    reader = gguf.GGUFReader(str(args.input), "r")
    arch = reader.get_field(gguf.Keys.General.ARCHITECTURE).contents()
    print(f"* architecture = {arch}")

    ctx_key = gguf.Keys.LLM.CONTEXT_LENGTH.format(arch=arch)
    scaling_type_key = gguf.Keys.Rope.SCALING_TYPE.format(arch=arch)
    scaling_factor_key = gguf.Keys.Rope.SCALING_FACTOR.format(arch=arch)
    scaling_orig_ctx_key = gguf.Keys.Rope.SCALING_ORIG_CTX_LEN.format(arch=arch)

    print(f"* {ctx_key}: {args.orig_context} -> {args.target_context}")
    print(f"* {scaling_type_key} = yarn, {scaling_factor_key} = {factor}, {scaling_orig_ctx_key} = {args.orig_context}")

    new_metadata = {
        ctx_key: MetadataDetails(gguf.GGUFValueType.UINT32, args.target_context),
        scaling_type_key: MetadataDetails(gguf.GGUFValueType.STRING, "yarn"),
        scaling_factor_key: MetadataDetails(gguf.GGUFValueType.FLOAT32, float(factor)),
        scaling_orig_ctx_key: MetadataDetails(gguf.GGUFValueType.UINT32, args.orig_context),
    }

    writer = gguf.GGUFWriter(str(args.output), arch, endianess=reader.endianess)
    copy_with_new_metadata(reader, writer, new_metadata, remove_metadata=[])
    print(f"* Wrote {args.output}")


if __name__ == "__main__":
    main()
