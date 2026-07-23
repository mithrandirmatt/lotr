import argparse
import json
from pathlib import Path

from model_config import load_model_config, resolve_base_models, resolve_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Ollama Modelfile from an agentic hardware/profile config")
    parser.add_argument("--repo_root", required=True)
    parser.add_argument("--profile", default="rx7900xtx-agentic")
    parser.add_argument("--model_config", default=None)
    parser.add_argument("--base_model", default=None)
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
        base_prompt = "You are a coding agent. Follow repository rules and use tools correctly."
    else:
        base_prompt = prompt_path.read_text(encoding="utf-8").strip()

    training_corpus = load_agent_training_corpus(repo_root)
    sections = [base_prompt]
    if training_corpus:
        sections.append("## Agent Training Corpus\n\n" + training_corpus)
    return "\n\n".join(section.strip() for section in sections if section.strip())


def load_agent_training_corpus(repo_root: Path) -> str:
    reference_dir = repo_root / "assets" / "reference" / "agent"
    if not reference_dir.exists():
        return ""

    priority_names = [
        "agent.system.md",
        "project-overview.md",
        "training-triggers.md",
        "training-maintenance.md",
        "trigger-workflow.md",
        "reinforcement-lotr.md",
        "reinforcement-generic.md",
        "rules-reference.md",
        "game-plan.md",
        "todo.md",
        "issues-current.md",
        "issues-completed.md",
        "issues-tracker.md",
        "issues.md",
    ]

    sections: list[str] = []
    seen_paths: set[Path] = set()

    for name in priority_names:
        path = reference_dir / name
        if path.is_file():
            sections.append(format_agent_reference_doc(path, repo_root))
            seen_paths.add(path.resolve())

    for path in sorted(reference_dir.rglob("*.md")):
        resolved_path = path.resolve()
        if resolved_path in seen_paths:
            continue
        sections.append(format_agent_reference_doc(path, repo_root))

    return "\n\n---\n\n".join(section for section in sections if section.strip()).strip()


def format_agent_reference_doc(path: Path, repo_root: Path) -> str:
    relative_path = path.relative_to(repo_root).as_posix()
    content = path.read_text(encoding="utf-8").strip()
    return f"## Source: {relative_path}\n\n{content}"


def sanitize_for_modelfile_system(prompt: str) -> str:
    """Sanitize prompt text for Ollama SYSTEM triple-quoted blocks.

    Any embedded triple-double-quote sequence would terminate the SYSTEM block
    early and make subsequent lines parse as Modelfile commands.
    """
    # Preserve semantics while preventing accidental SYSTEM block termination.
    return prompt.replace('"""', "'''")


def build_modelfile(base_model: str, system_prompt: str, runtime: dict, adapter_path: str | None = None) -> str:
    system_prompt = sanitize_for_modelfile_system(system_prompt)
    lines = [
        f"FROM {base_model}",
        "",
        f"PARAMETER num_ctx {runtime.get('num_ctx', 65536)}",
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
        adapter_path = str(Path(adapter_path).resolve())
        # Keep ADAPTER pointed at the adapter directory so Ollama can resolve
        # both adapter_model.safetensors and adapter_config.json together.
        lines.extend([
            f"ADAPTER {adapter_path}",
            "",
        ])

    # Raw GGUF imports can default to a template that ignores system prompts.
    # Force a system-aware template so instruction/training content is honored.
    if str(base_model).lower().endswith(".gguf"):
        lines.extend([
            "TEMPLATE \"\"\"{{- if .System -}}<|im_start|>system",
            "{{ .System }}<|im_end|>",
            "{{- end -}}{{- if .Prompt -}}<|im_start|>user",
            "{{ .Prompt }}<|im_end|>",
            "<|im_start|>assistant",
            "{{- end -}}\"\"\"",
            "PARAMETER stop \"<|im_start|>\"",
            "PARAMETER stop \"<|im_end|>\"",
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
    model_cfg, model_cfg_path = load_model_config(repo_root, args.model_config)
    runtime = resolve_runtime(profile, model_cfg)
    cfg_ollama_model, _ = resolve_base_models(model_cfg)
    base_model = args.base_model or cfg_ollama_model or "qwen2.5-coder:7b"
    system_prompt = load_system_prompt(repo_root)

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = build_modelfile(base_model, system_prompt, runtime, args.adapter_path)
    output_path.write_text(content, encoding="utf-8")

    print(f"Profile: {args.profile}")
    if model_cfg_path:
        print(f"Model config: {model_cfg_path}")
    print(f"Base model: {base_model}")
    print(f"Modelfile written to: {output_path}")


if __name__ == "__main__":
    main()
