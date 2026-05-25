# LotR TCG Project — Completed Task Tracker

## Completed

Only list the current active issue here. This should serve as a reminder of what we are currently working on.

### Behaviors

When shelving an issue to work on another, ensure the current issue is queued in this file.

Ensure when working on an issue, that the issue is listed here while it is being worked on.
Once complete, remove from this file and move it to the issues-completed.md file.


## Current Issue Being Worked:

- **LOT-001** — Generate game-logic database from card database. Parse each card's `game_text` to create structured logical actions (triggers, costs, conditions, effects) for runtime use.
  - Original request: "I would like to work on generating another database for game logic. The idea would be to parse the existing card database, then for each card read the game text for that card to create logical actions for that card to be used at a later time. This was we are creating a fixed expectation once we get to runtime."
  - Planning: Consult `.github/agent/workflows/workflow-generate-game-logic.md` for implementation steps.
  - Resources: `gotdot/assets/data/card_database.json`, `assets/reference/agent/rules-reference.md`

## Queued Issues:

- **LOT-002** — Implement server infrastructure for card purchasing and online play. Build secure backend services to control card collections for monetization and prevent cheating in online matches.
  - Original request: "We need a server where the card collection can be controlled for monetization, and for the online play element to prevent cheating."
  - Planning: Define API endpoints for card ownership, purchase transactions, and match state validation.
  - Resources: `.github/agent/workflows/workflow-server-infrastructure.md` (to be created)

