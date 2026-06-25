# AI Test Prompt Pack

Use this prompt to evaluate an agent’s ability to plan, scaffold, implement, and verify a small software project without extra guidance.

## Task

Create three separate, working web projects in these directories:

- `do/ai-test/easy`
- `do/ai-test/medium`
- `do/ai-test/hard`

Each project must be independently runnable, must display a web page, and must include a polished splash or loading experience that eventually transitions to a visible `hello world` screen.

You are free to choose the framework, language, build tool, and runtime for each project. Do not force a specific stack unless it is the best fit for the implementation. The goal is to test whether you can make good technical choices and follow through, not whether you can satisfy a particular framework preference.

## Shared Rules

1. Do not ask clarifying questions unless the task is truly blocked.
2. Keep all project files inside the relevant `do/ai-test/<difficulty>` directory.
3. Make each project actually work. Placeholder pages, mock-only plans, and unfinished scaffolds are failures.
4. Include a short `README.md` in each project that explains setup and the exact command to launch the app.
5. At the end, provide one single command per project that launches the web page from that project’s root.
6. Your final response must clearly report completion status for each tier.

## Required Workflow

Work in phases and make the phases visible in your output:

1. Plan the project.
2. Scaffold the project.
3. Implement the splash/loading flow.
4. Implement the final `hello world` screen.
5. Verify the project runs.
6. Summarize the result and provide the launch command.

Do not skip directly to code. A good solution should show that you can manage a multi-step process and recover from any implementation issues.

## Difficulty Tiers

### Easy

Build the simplest complete version that still satisfies the goal.

Requirements:

- Single web app.
- One visible splash/loading sequence.
- One final `hello world` page.
- Minimal but polished styling.
- No backend required.

Pass criteria:

- The app launches successfully with one command.
- The splash screen is visible before `hello world` appears.
- The final page clearly shows `hello world`.
- The project can be understood and run from its README.

Fail criteria:

- The page loads directly into `hello world` with no splash experience.
- The project requires manual repair before it can run.
- The implementation is just a static placeholder with no actual transition.

### Medium

Build a more structured project that introduces at least one non-trivial coordination step.

Requirements:

- A richer splash/loading experience than the easy tier.
- At least one meaningful setup or orchestration step before the final page appears.
- A small but real project structure, not a single-file demo.
- Clear visual polish and intentional motion/transition behavior.

Pass criteria:

- The app launches successfully with one command.
- The splash flow uses a real staged process instead of a static timeout only.
- The final page clearly shows `hello world`.
- The project contains enough structure that a reviewer can see deliberate engineering decisions.

Fail criteria:

- The medium project is functionally identical to the easy project.
- There is no visible staging, sequencing, or coordination.
- The app depends on vague manual instructions rather than a real run command.

### Hard

Build the most demanding version. This tier should feel meaningfully more agentic, with multiple coordinated pieces that must work together before the splash resolves.

Requirements:

- Multiple cooperating modules, screens, steps, or runtime phases.
- A splash/loading sequence that reflects actual orchestration, not just cosmetic animation.
- A final `hello world` screen that appears only after the full flow completes.
- The implementation should show thoughtful structure and dependency management.
- The result should still be easy to launch from one command.

Pass criteria:

- The app launches successfully with one command.
- The project demonstrates real multi-step orchestration before the final screen appears.
- The splash/loading experience is clearly more complex than the medium tier.
- The final page clearly shows `hello world`.
- The codebase makes the coordination pattern easy to understand.

Fail criteria:

- The hard project is just a fancier version of the medium project with no added coordination.
- The final screen appears immediately or without a meaningful staged process.
- The project needs multiple manual commands to start.
- The implementation hides complexity instead of demonstrating it.

## Output Requirements

For each tier, provide:

- the project directory path,
- a short explanation of what was built,
- the exact single command used to launch it,
- a pass/fail checklist,
- any notable assumptions or tradeoffs.

At the end, include a short completion summary that says whether each tier is working or not.

## Final Acceptance Standard

The overall task is successful only if all three projects exist, each one launches from a single command, each one shows a splash/loading experience before `hello world`, and each one has clear pass/fail criteria documented in the final report.

If any tier cannot be completed, explain exactly why, what blocked it, and what partial result was achieved.
