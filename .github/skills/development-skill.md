# Development Skill

## Purpose
This skill supplies a repeatable **Plan → Build → Reflect** cycle that can be invoked by the agent to:
1. **Plan** – understand the request, map it to existing project artifacts, and generate a concise plan.
2. **Build** – create or modify files, run tests, and commit changes.
3. **Reflect** – review test results, lint output, and user feedback to refine the next iteration.

The cycle is inspired by the PDCA (Plan‑Do‑Check‑Act) model and Agile retrospectives, ensuring that every change is intentional and validated.

## Skill Structure

```
development-skill:
	plan: function(plan_request)
	build: function(build_plan)
	reflect: function(build_output)
```

### Plan
* Parse the user request and identify affected files or modules.
* Generate a short action list with file paths, line ranges, and intended edits.
* Optionally create a TODO entry in `/memories/session/current-work.md`.

### Build
* Apply patches using `apply_patch`.
* Run any required tests or linters via `run_task`.
* Commit changes with a meaningful message.

### Reflect
* Capture test and lint results.
* Update the session memory to mark the task as completed or note failures.
* If failures occur, automatically generate a new plan that addresses them.

## Example Workflow

1. **User**: "Add a new API endpoint for user profiles."
2. **Plan**: Agent identifies `server/api/user.py`, drafts patch to add route and handler.
3. **Build**: Patch applied, tests run, commit made.
4. **Reflect**: Test output shows failures; agent updates plan to fix missing imports.

Repeat until all tests pass.

---
