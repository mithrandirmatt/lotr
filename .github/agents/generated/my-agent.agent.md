---
name: my-agent
display_name: my-agent
description: Worker agent (overview). Keeps includes to shared logic and permissions.
prompts:
  user: 'Use the worker agent for repository edits. Refer to included files for full

    prompts, tool definitions, and permissions.'
system: 'You are a repository-aware assistant. Use repository context and safety best
  practices.

  '
user_templates:
- name: quick_summary
  prompt: Provide a concise summary of the repository's purpose and suggestions for
    contributors.
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
---
---


# Instructions / Notes

This is a template agent profile created for this repository. Edit the frontmatter fields above and commit to the default branch so the agent will appear in the GitHub Copilot agents dropdown.
