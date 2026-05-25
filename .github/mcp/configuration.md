# MCP Configuration for LotR TCG Project

## Available MCP Servers

### GitKraken MCP
- **Purpose**: Issue tracking, pull request management, code review
- **Configuration**: Already configured via `.github/agents/` integration
- **Usage**: Automatic when working with GitHub/GitLab issues

### SQL Database MCP
- **Purpose**: PostgreSQL query execution for game data
- **Connection**: `postgresql://postgres:postgres@localhost:5432/lotr_tcg`
- **Usage**:
  ```
  - Query card database: SELECT * FROM cards WHERE set = 'Fellowship'
  - Analyze game logs: SELECT * FROM matches WHERE winner = 'shadow'
  - Export data: SELECT json_agg(to_jsonb(cards)) FROM cards
  ```

### Python MCP
- **Purpose**: Python environment management, import analysis
- **Usage**:
  - Configure environments: `configure_python_environment`
  - Install packages: `install_python_packages`
  - Analyze imports: `activate_python_import_analysis_tools`

### File System MCP
- **Purpose**: Large file operations, workspace management
- **Usage**:
  - List directories: `mcp_lotr-mcp_list_directory`
  - Read files: `mcp_lotr-mcp_read_file`
  - Write files: `mcp_lotr-mcp_write_file`
  - Execute commands: `mcp_lotr-mcp_run_command`

## MCP Tool Integration

### Automatic Invocation
MCP tools are automatically available when:
1. Working with database queries → SQL MCP
2. Managing Python dependencies → Python MCP
3. Large file operations → File System MCP
4. Issue/PR management → GitKraken MCP

### Manual Activation
When needed, activate specific MCP categories:
- `activate_sql_database_tools` — Database queries
- `activate_python_environment_management_tools` — Python env management
- `activate_workspace_file_management_tools` — File operations
- `activate_git_version_control_tools` — Git operations

## Memory Integration

### Repository Memory Location
```
lotr/memories/repo/
├── game-mechanics.md    # TCG rules, triggers, timing
├── architecture-decisions.md  # Design patterns, API design
├── debugging-patterns.md  # Common issues, solutions
└── mcp-tools.md         # This file
```

### Memory Usage Guidelines
- **Repository memory**: Codebase conventions, verified practices
- **Session memory**: Current task progress, pending items
- **User memory**: Preferences, coding style

## Quick Reference

### Database Queries
```sql
-- Find cards by trigger type
SELECT name, game_text FROM cards
WHERE game_text LIKE '%Fellowship%'

-- Get card statistics
SELECT set_name, COUNT(*) as card_count
FROM cards GROUP BY set_name ORDER BY card_count DESC

-- Find duplicate cards
SELECT canonical_id, COUNT(*) as count
FROM card_entries GROUP BY canonical_id HAVING count > 1
```

### Python Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv
```

### GitKraken MCP Usage
```
# View assigned issues
mcp_gitkraken_issues_assigned_to_me provider=github

# Search pull requests
mcp_gitkraken_pull_request_assigned_to_me provider=github

# Create pull request
mcp_gitkraken_pull_request_create provider=github ...
```

## Verification Checklist

- [ ] MCP servers connected and responding
- [ ] Memory directories created and accessible
- [ ] Agent configuration updated
- [ ] Database connection verified
- [ ] Python environment configured
