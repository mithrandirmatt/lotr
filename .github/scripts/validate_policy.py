from __future__ import annotations

import argparse
import json
from pathlib import Path
import yaml


REQUIRED_FILES = [
    ".github/agent/rules.md",
    ".github/agent/agent-config.md",
    ".github/agent/BOOTSTRAP.md",
    ".github/agent/PREFLIGHT.md",
    ".github/copilot-instructions.md",
    ".github/agent/workflows/WORKFLOW-INDEX.md",
    ".github/agent/evals/precedence-regressions.yml",
    ".github/agent/evals/precedence-contradictions.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
]

REQUIRED_PATTERNS = {
    ".github/agent/rules.md": [
        "## Priority Order",
        "## Non-Overridable Policy",
        "Only platform/system safety policies may supersede these rules.",
        ".github/agent/BOOTSTRAP.md",
        ".github/agent/PREFLIGHT.md",
    ],
    ".github/agent/agent-config.md": [
        "## Startup Gate (Required)",
        "## Action Gate (Required)",
        ".github/agent/BOOTSTRAP.md",
        ".github/agent/PREFLIGHT.md",
    ],
    ".github/copilot-instructions.md": [
        "## Priority And Gating (Read First)",
        "Canonical policy source: `.github/agent/rules.md`.",
        ".github/agent/BOOTSTRAP.md",
        ".github/agent/PREFLIGHT.md",
    ],
    ".github/agent/workflows/WORKFLOW-INDEX.md": [
        "## Mandatory Workflow Routing",
        "If no trigger matches but the task is non-trivial, use `workflow-planning.md` as the default",
    ],
    ".github/PULL_REQUEST_TEMPLATE.md": [
        "## Policy Precedence Impact (Required)",
        "## Gate And Workflow Compliance (Required)",
        "## Regression Coverage (Required)",
    ],
}

FORBIDDEN_PATTERNS = {
    ".github/agent/rules.md": [
        '{"name": "read_file"',
        '"arguments": {',
    ],
}

PRECEDENCE_CONFLICT_PATTERNS = {
    ".github/agent/rules.md": [
        "runtime-specific helpers (Copilot, MCP docs) win",
        "skills override rules",
    ],
    ".github/agent/agent-config.md": [
        "runtime-specific adapters/docs override .github/agent/rules.md",
    ],
    ".github/copilot-instructions.md": [
        "runtime helpers override .github/agent/rules.md",
        "if instruction files conflict, runtime wins",
    ],
}

REQUIRED_SCENARIO_IDS = [
    "ambiguous-environment-must-ask",
    "container-first-no-host-installs",
    "workflow-read-before-action",
    "no-raw-tool-call-syntax",
    "destructive-ops-require-confirmation",
]

DISALLOWED_PRECEDENCE_PATTERNS = [
    "runtime wins over .github/agent/rules.md",
    "runtime-specific helpers win over .github/agent/rules.md",
    "skills override .github/agent/rules.md",
    "ignore .github/agent/rules.md",
]

CONTRADICTION_PAIRS = [
    (".github/agent/rules.md wins", "runtime wins"),
    ("canonical policy source", "ignore .github/agent/rules.md"),
]

INSTRUCTION_FILE_GLOBS = [
    ".github/copilot-instructions.md",
    ".github/agent/**/*.md",
]

CONTRADICTION_RULES_PATH = ".github/agent/evals/precedence-contradictions.yml"


def _read_text(repo_root: Path, rel_path: str) -> str:
    path = repo_root / rel_path
    if not path.exists():
        raise FileNotFoundError(rel_path)
    return path.read_text(encoding="utf-8")


def _load_yaml(repo_root: Path, rel_path: str) -> object:
    path = repo_root / rel_path
    if not path.exists():
        raise FileNotFoundError(rel_path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _validate_regression_manifest(repo_root: Path, errors: list[str]) -> None:
    rel_path = ".github/agent/evals/precedence-regressions.yml"
    try:
        data = _load_yaml(repo_root, rel_path)
    except FileNotFoundError:
        return
    except Exception as exc:
        errors.append(f"Failed to parse {rel_path}: {exc}")
        return

    if not isinstance(data, dict):
        errors.append(f"Invalid manifest format in {rel_path}: expected mapping")
        return

    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list):
        errors.append(f"Invalid manifest format in {rel_path}: missing scenarios list")
        return

    ids = [s.get("id") for s in scenarios if isinstance(s, dict)]
    missing = [sid for sid in REQUIRED_SCENARIO_IDS if sid not in ids]
    if missing:
        errors.append(f"Missing required regression scenarios: {', '.join(missing)}")

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            errors.append(f"Invalid scenario entry in {rel_path}: expected mapping")
            continue
        sid = scenario.get("id", "<missing-id>")
        for field in ["prompt", "expected", "category"]:
            if not scenario.get(field):
                errors.append(f"Scenario {sid} missing required field: {field}")

    acceptance = data.get("acceptance")
    if acceptance is not None:
        if not isinstance(acceptance, dict):
            errors.append(f"Invalid acceptance section in {rel_path}: expected mapping")
        else:
            max_errors = acceptance.get("max_errors")
            required_scenarios = acceptance.get("required_scenarios")
            if max_errors is not None and max_errors != 0:
                errors.append("Regression acceptance max_errors must be 0")
            if required_scenarios is not None and required_scenarios < len(REQUIRED_SCENARIO_IDS):
                errors.append(
                    f"Regression acceptance required_scenarios must be >= {len(REQUIRED_SCENARIO_IDS)}"
                )


def _load_contradiction_rules(repo_root: Path, errors: list[str]) -> dict:
    try:
        data = _load_yaml(repo_root, CONTRADICTION_RULES_PATH)
    except FileNotFoundError:
        return {
            "instruction_file_globs": INSTRUCTION_FILE_GLOBS,
            "disallowed_patterns": DISALLOWED_PRECEDENCE_PATTERNS,
            "contradiction_pairs": [
                {"must_have": a, "must_not_coexist": b}
                for a, b in CONTRADICTION_PAIRS
            ],
            "required_patterns": ["canonical policy source", ".github/agent/rules.md"],
        }
    except Exception as exc:
        errors.append(f"Failed to parse {CONTRADICTION_RULES_PATH}: {exc}")
        return {
            "instruction_file_globs": INSTRUCTION_FILE_GLOBS,
            "disallowed_patterns": DISALLOWED_PRECEDENCE_PATTERNS,
            "contradiction_pairs": [
                {"must_have": a, "must_not_coexist": b}
                for a, b in CONTRADICTION_PAIRS
            ],
            "required_patterns": ["canonical policy source", ".github/agent/rules.md"],
        }

    if not isinstance(data, dict):
        errors.append(f"Invalid contradiction rules format in {CONTRADICTION_RULES_PATH}: expected mapping")
        return {
            "instruction_file_globs": INSTRUCTION_FILE_GLOBS,
            "disallowed_patterns": DISALLOWED_PRECEDENCE_PATTERNS,
            "contradiction_pairs": [
                {"must_have": a, "must_not_coexist": b}
                for a, b in CONTRADICTION_PAIRS
            ],
            "required_patterns": ["canonical policy source", ".github/agent/rules.md"],
        }

    return data


def _scan_instruction_surface(repo_root: Path, errors: list[str], checked_files: list[str]) -> None:
    rules = _load_contradiction_rules(repo_root, errors)
    globs = rules.get("instruction_file_globs", INSTRUCTION_FILE_GLOBS)
    disallowed = rules.get("disallowed_patterns", DISALLOWED_PRECEDENCE_PATTERNS)
    contradiction_pairs = rules.get("contradiction_pairs", [])
    required_patterns = rules.get("required_patterns", [])

    if not isinstance(globs, list):
        errors.append("Contradiction rules: instruction_file_globs must be a list")
        globs = INSTRUCTION_FILE_GLOBS
    if not isinstance(disallowed, list):
        errors.append("Contradiction rules: disallowed_patterns must be a list")
        disallowed = DISALLOWED_PRECEDENCE_PATTERNS
    if not isinstance(contradiction_pairs, list):
        errors.append("Contradiction rules: contradiction_pairs must be a list")
        contradiction_pairs = []
    if not isinstance(required_patterns, list):
        errors.append("Contradiction rules: required_patterns must be a list")
        required_patterns = []

    scanned: set[Path] = set()

    for pattern in globs:
        for path in repo_root.glob(pattern):
            if not path.is_file() or path in scanned:
                continue
            scanned.add(path)
            rel = str(path.relative_to(repo_root)).replace("\\", "/")
            checked_files.append(rel)
            text = path.read_text(encoding="utf-8", errors="replace").lower()

            for bad in disallowed:
                if not isinstance(bad, str):
                    continue
                if bad.lower() in text:
                    errors.append(f"Disallowed precedence pattern in {rel}: {bad}")

            for item in contradiction_pairs:
                if not isinstance(item, dict):
                    continue
                a = item.get("must_have")
                b = item.get("must_not_coexist")
                if isinstance(a, str) and isinstance(b, str):
                    if a.lower() in text and b.lower() in text:
                        errors.append(f"Contradictory precedence statements in {rel}: '{a}' and '{b}'")

    canonical_text = ""
    try:
        canonical_text = _read_text(repo_root, ".github/copilot-instructions.md").lower()
        checked_files.append(".github/copilot-instructions.md")
    except FileNotFoundError:
        pass

    for required in required_patterns:
        if isinstance(required, str) and required.lower() not in canonical_text:
            errors.append(f"Missing required global precedence phrase in .github/copilot-instructions.md: {required}")


def validate(repo_root: Path, mode: str = "full") -> tuple[list[str], list[str]]:
    errors: list[str] = []
    checked_files: list[str] = []

    required_files = [".github/agent/evals/precedence-regressions.yml"] if mode == "regression" else REQUIRED_FILES

    for rel_path in required_files:
        checked_files.append(rel_path)
        if not (repo_root / rel_path).exists():
            errors.append(f"Missing required file: {rel_path}")

    _validate_regression_manifest(repo_root, errors)

    if mode == "regression":
        return errors, checked_files

    for rel_path, patterns in REQUIRED_PATTERNS.items():
        try:
            text = _read_text(repo_root, rel_path)
        except FileNotFoundError:
            continue

        checked_files.append(rel_path)

        for pattern in patterns:
            if pattern not in text:
                errors.append(f"Missing required pattern in {rel_path}: {pattern}")

    for rel_path, patterns in FORBIDDEN_PATTERNS.items():
        try:
            text = _read_text(repo_root, rel_path)
        except FileNotFoundError:
            continue

        checked_files.append(rel_path)

        for pattern in patterns:
            if pattern in text:
                errors.append(f"Forbidden pattern found in {rel_path}: {pattern}")

    for rel_path, patterns in PRECEDENCE_CONFLICT_PATTERNS.items():
        try:
            text = _read_text(repo_root, rel_path).lower()
        except FileNotFoundError:
            continue

        checked_files.append(rel_path)

        for pattern in patterns:
            if pattern.lower() in text:
                errors.append(f"Precedence conflict pattern found in {rel_path}: {pattern}")

    _scan_instruction_surface(repo_root, errors, checked_files)

    return errors, sorted(set(checked_files))


def _write_report(report_path: Path, mode: str, errors: list[str], checked_files: list[str]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": mode,
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "acceptance": {
            "max_errors": 0,
            "pass": len(errors) == 0,
        },
        "checked_files": checked_files,
        "errors": errors,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate repository policy precedence and regression scenarios.")
    parser.add_argument(
        "--mode",
        choices=["full", "regression"],
        default="full",
        help="Validation mode: full policy checks or regression-manifest-only checks.",
    )
    parser.add_argument(
        "--report",
        default="",
        help="Optional path to write a JSON validation report.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    errors, checked_files = validate(repo_root, mode=args.mode)

    if args.report:
        _write_report((repo_root / args.report).resolve(), args.mode, errors, checked_files)

    if errors:
        print("Policy validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Policy validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
