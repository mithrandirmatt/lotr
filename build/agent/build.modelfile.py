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

    corpus_index = load_agent_training_corpus_index(repo_root)
    sections = [base_prompt]
    if corpus_index:
        sections.append(corpus_index)
    return "\n\n".join(section.strip() for section in sections if section.strip())


def load_agent_training_corpus_index(repo_root: Path) -> str:
    """Build a lightweight index (path + one-line description) of the agent
    reference docs instead of concatenating their full contents into the
    permanent SYSTEM prompt. Baking every doc in verbatim made every single
    request pay for tens of thousands of fixed tokens regardless of
    relevance; the model has file-read tools and should pull in only the
    doc(s) actually needed for the task at hand.
    """
    reference_dir = repo_root / "assets" / "reference" / "agent"
    if not reference_dir.exists():
        return ""

    entries: list[str] = []
    for path in sorted(reference_dir.rglob("*.md")):
        relative_path = path.relative_to(repo_root).as_posix()
        entries.append(f"- `{relative_path}` — {describe_reference_doc(path)}")

    if not entries:
        return ""

    return (
        "## Agent Reference Document Index\n\n"
        "The documents below hold detailed rules, plans, and project history. "
        "They are NOT preloaded here -- read only the ones relevant to the "
        "current task with your file-read tool before acting on it.\n\n"
        + "\n".join(entries)
    )


def describe_reference_doc(path: Path) -> str:
    """First non-empty, non-frontmatter line of a doc (heading text), used
    as its index summary."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "(no description)"

    start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                start = i + 1
                break

    for line in lines[start:]:
        line = line.strip()
        if line and line != "---":
            return line.lstrip("#").strip()
    return "(no description)"


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
