---
rules:
  - id: canonical_rules_source
    summary: "Use `.github/agent/rules.md` as the single source of truth."
    detail: |
      This file exists only for backward compatibility with legacy agent setups.
      If there is any conflict, `.github/agent/rules.md` wins.
---

# Compatibility Alias

Canonical rules are maintained in `.github/agent/rules.md`.
Do not duplicate rule definitions here.
