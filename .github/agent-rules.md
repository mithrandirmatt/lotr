---
rules:
  - id: no_commandline_search
    summary: "Do not search the workspace using command-line tools."
    detail: |
      Agents must not execute shell commands like `grep`, `find`, `rg`, or `ls` to search repository files.
      Use the `repo_browser` or `code_search` tools to find files and contents instead.
  - id: use_search_tools
    summary: "Use dedicated search tools for code discovery."
    detail: |
      Use `code_search` or `repo_browser` to locate files and cite paths/line ranges.
  - id: no_unrestricted_shell
    summary: "Avoid running unrestricted shell commands."
    detail: |
      The `shell` tool is restricted; only run commands when explicitly allowed by maintainers.
  - id: minimal_changes
    summary: "Prefer minimal, style-consistent edits."
    detail: |
      Provide small, well-tested changes matching repository style. Include tests and run instructions.
  - id: no_secrets
    summary: "Never expose secrets or credentials."
    detail: |
      Do not read, include, or store any secrets; redact or refuse if necessary.
  - id: verify_with_tests
    summary: "Include/Update tests for non-trivial changes."
    detail: |
      Add or update tests and include commands to run them locally.
  - id: missing_tools
    summary: "Inform the user when required capabilities or tools are missing."
    detail: |
      If the agent lacks a required capability or tool to complete the user's explicit request (for example, a missing tool integration or required permission), inform the user immediately.
      Explain which capability is missing and suggest next steps to add or enable it (for example, installing a plugin, adding a `tool_definitions` entry, or granting permissions).
      Do not attempt risky workarounds; wait for the user's guidance before proceeding.
---
