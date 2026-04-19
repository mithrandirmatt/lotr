---
system: 'You are a repository-aware assistant. Use repository context and safety best
  practices.

  '
user_templates:
- name: quick_summary
  prompt: 'Provide a concise summary of the repository''s purpose and suggestions
    for contributors.

    '
tools:
  repo_browser:
    description: Read files and directories in the repository and return paths/snippets.
    type: file
    permissions: read
  code_search:
    description: Search source files by keyword, regex, or symbol and return matching
      file paths and excerpts.
    type: file
    permissions: read
  file_editor:
    description: Propose file edits as unified diffs or full file replacements.
    type: file
    permissions: write
  run_tests:
    description: Run the repository test suite or specific test commands and report
      results.
    type: command
    command: pytest
  pr_manager:
    description: Create or update pull requests with provided patches.
    type: http
  issue_tracker:
    description: Create, update, or query repository issues.
    type: http
  shell:
    description: Execute restricted shell commands; use only when explicitly allowed
      by repo maintainers.
    type: shell
    restricted: true
permissions:
  allowed_tools:
  - repo_browser
  - code_search
  - file_editor
  - run_tests
  - pr_manager
  - issue_tracker
  - shell
  - execute
  restricted_tools:
    shell:
      requires_approval: true
      note: Shell (execute) is restricted; require maintainer approval before running
        shell commands.
  tool_scopes:
    repo_browser:
      read: true
      write: false
    file_editor:
      read: true
      write: true
    run_tests:
      run: true
  runtime_mapping:
    github:
    - repo_browser
    - code_search
    - file_editor
    - pr_manager
    - issue_tracker
    local:
    - repo_browser
    - code_search
    - file_editor
    - run_tests
name: my-agent
display_name: my-agent
description: Worker agent (overview). Keeps includes to shared logic and permissions.
prompts:
  user: 'Use the worker agent for repository edits. Refer to included files for full

    prompts, tool definitions, and permissions.

    '
---

---


# Instructions / Notes

This is a template agent profile created for this repository. Edit the frontmatter fields above and commit to the default branch so the agent will appear in the GitHub Copilot agents dropdown.
