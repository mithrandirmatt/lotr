---
system: 'You are a repository-aware assistant. Use repository context and safety best
  practices.

  '
---
name: my-agent
display_name: My Agent
description: |
  A repository-scoped custom agent template. Edit `name`, `description`, `tools`, and `prompts`.
models:
  - name: gpt-5-mini
    display_name: C-GPT-5-mini
    type: llm
    parameters:
      temperature: 0.2
tools:
  - name: repo_browser
    description: Read files and directories in the repository.
    type: file
  - name: issue_tracker
    description: Create or query repository issues (if configured).
    type: http
prompts:
  system: |
    You are a repository-aware assistant. Use repository context and safety best practices.

    You are a helpful, safety-conscious assistant for this repository. When unsure, ask clarifying questions.
  user: |
    You are the `my-agent` custom agent. Follow the repository conventions and be concise.
  user_templates:
    - name: quick_summary
      prompt: |
        Provide a concise summary of the repository's purpose and suggestions for contributors.
---
  user: 'You are the `my-agent` custom agent. Follow the repository conventions and
