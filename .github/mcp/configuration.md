# MCP Configuration for LotR TCG Project

This document describes MCP usage in a runtime-agnostic way.

## Principles

- Prefer native workspace tools first for read/search/edit operations.
- Use MCP tools when native tools are unavailable or when MCP-only capabilities are required.
- Do not assume fixed tool names across runtimes.

## Typical MCP Capability Areas

- Issue/PR management
- Database queries
- Python environment management
- Workspace file operations
- Shell command execution

## Naming Compatibility

Different clients may expose the same capability under different names.
Examples:

- snake_case function names
- namespaced names like `server_tool`
- prefixed names like `mcp_provider_tool`

Always use the names reported by the active runtime.

## Safety Rules

- Follow `.github/agent/rules.md` as canonical policy.
- Ask before destructive operations.
- Keep changes minimal and verify outcomes.
- Never expose secrets.

## Memory Locations

- Repository memory: `memories/repo/`
- Session memory: `memories/session/`
- User/global memory: runtime-dependent

## Verification Checklist

- Runtime reports MCP tools as available.
- Required server/tool category is enabled.
- File paths match runtime expectations.
- Commands run in the correct environment (dev container for development commands).
