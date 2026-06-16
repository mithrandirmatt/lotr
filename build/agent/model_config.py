import json
from pathlib import Path


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_model_config_path(repo_root: Path, model_config: str) -> Path:
    raw = Path(model_config)
    if raw.is_absolute() and raw.exists():
        return raw

    models_dir = repo_root / "build" / "agent" / "models"
    if raw.suffix == ".json":
        candidate = models_dir / raw.name
    else:
        candidate = models_dir / f"{model_config}.json"

    if not candidate.exists():
        raise FileNotFoundError(f"Model config not found: {candidate}")
    return candidate


def load_model_config(repo_root: Path, model_config: str | None) -> tuple[dict, Path | None]:
    if not model_config:
        return {}, None

    config_path = _resolve_model_config_path(repo_root, model_config)
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data, config_path


def resolve_runtime(profile: dict, model_cfg: dict) -> dict:
    return _deep_merge(profile.get("runtime", {}), model_cfg.get("runtime_overrides", {}))


def resolve_lora(profile: dict, model_cfg: dict) -> dict:
    return _deep_merge(profile.get("lora", {}), model_cfg.get("lora_overrides", {}))


def resolve_base_models(model_cfg: dict) -> tuple[str | None, str | None]:
    return model_cfg.get("ollama_base_model"), model_cfg.get("hf_base_model")
