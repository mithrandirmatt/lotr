import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Ollama Modelfile from an agentic hardware/profile config")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--base_model", default="qwen2.5-coder:7b")
    parser.add_argument("--output", required=True)
    parser.add_argument("--adapter_path", default=None)
    return parser.parse_args()


def load_profile(repo_root: Path, profile_name: str) -> dict:
    profile_path = repo_root / "build" / "agent" / "profiles" / f"{profile_name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    with profile_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_system_prompt(repo_root: Path) -> str:
    prompt_path = repo_root / ".github" / "copilot-instructions.md"
    if not prompt_path.exists():
        return "You are a coding agent. Follow repository rules and use tools correctly."
    return prompt_path.read_text(encoding="utf-8").strip()


def build_modelfile(base_model: str, system_prompt: str, runtime: dict, adapter_path: str | None = None) -> str:
    lines = [
        f"FROM {base_model}",
        "",
        f"PARAMETER num_ctx {runtime.get('num_ctx', 32768)}",
        f"PARAMETER num_predict {runtime.get('num_predict', 4096)}",
        f"PARAMETER temperature {runtime.get('temperature', 0.2)}",
        f"PARAMETER top_p {runtime.get('top_p', 0.9)}",
        f"PARAMETER top_k {runtime.get('top_k', 40)}",
        f"PARAMETER repeat_penalty {runtime.get('repeat_penalty', 1.08)}",
        f"PARAMETER mirostat {runtime.get('mirostat', 0)}",
        f"PARAMETER seed {runtime.get('seed', 42)}",
        "",
    ]

    if adapter_path:
        lines.extend([
            f"ADAPTER {adapter_path}",
            "",
        ])

    lines.extend([
        "SYSTEM \"\"\"",
        system_prompt,
        "\"\"\"",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    profile = load_profile(repo_root, args.profile)
    runtime = profile.get("runtime", {})
    system_prompt = load_system_prompt(repo_root)

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = build_modelfile(args.base_model, system_prompt, runtime, args.adapter_path)
    output_path.write_text(content, encoding="utf-8")

    print(f"Profile: {args.profile}")
    print(f"Base model: {args.base_model}")
    print(f"Modelfile written to: {output_path}")


if __name__ == "__main__":
    main()
