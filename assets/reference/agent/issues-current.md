# LotR TCG Project — Completed Task Tracker

## Completed

Only list the current active issue here. This should serve as a reminder of what we are currently working on.

### Behaviors

When shelving an issue to work on another, ensure the current issue is queued in this file.

Ensure when working on an issue, that the issue is listed here while it is being worked on.
Once complete, remove from this file and move it to the issues-completed.md file.


## Current Issue(s) Being Worked:

- **LOT-003** — Make admin account. User: lotradmin, password: yourmommalooksfunny.
  - Admin acount: Can do the following:
    - Add/remove cards from the database
    - Add/remove users
    - Grant/revoke admin privileges to other users
  - **Status**: In Progress

- **LOT-004** — Add login, make the landing page a sign up or sign in page.
  - Once logged in, go to main menu.
  - Main Menu Options should include:
    - Deck Manager
    - Play Online (vs other players)
    - Play vs AI (local)
    - Admin Panel (only visible to admins)
  - Play options should be grayed out if no valid deck is available.
  - **Status**: In Progress

- **LOT-005** — Add deck manager. Allow users to create and manage decks.
  - Will have ui that allows users to add/remove cards from their collection and from their decks.
  - Can have selection of rules that the user wants to build the deck for (e.g. standard, modern, open, etc.) and only show cards that are legal in those formats.
  - Decks should be saved to the database and associated with the user's account.
    - Each deck should have a unique name.
  - You can select a deck, and move cards to and from your collection.
    - Cards in the deck are not in the collection, and cards in the collection are not in the deck.
  - You can have multiple decks, but each deck must have a unique name.
  - **Status**: In Progress

- **LOT-006** - Add AI play.
  - This will allow users to play against an AI opponent locally.
  - The AI should follow the same rules user selects.
  - We should make the AI difficulty adjustable, so users can choose to play against an easier or harder opponent.
    - Decks should be built for each difficulty level, and the AI should use the appropriate deck based on the selected difficulty.
    - Need to classify cards in the database by difficulty level, so we can build appropriate decks for the AI.
  - The AI should be able to make legal moves and should be able to win or lose based on the game state.
  - AI should use the same game logic as the online play, so we can ensure consistency between local and online play.
  - **Status**: In Progress

## Queued Issues:

- **LOT-001** — Generate game-logic database from card database. Parse each card's `game_text` to create structured logical actions (triggers, costs, conditions, effects) for runtime use.
  - Original request: "I would like to work on generating another database for game logic. The idea would be to parse the existing card database, then for each card read the game text for that card to create logical actions for that card to be used at a later time. This was we are creating a fixed expectation once we get to runtime."
  - Planning: Consult `.github/agent/workflows/workflow-generate-game-logic.md` for implementation steps.
  - Resources: `gotdot/assets/data/card_database.json`, `assets/reference/agent/rules-reference.md`

- **LOT-002** — Implement server infrastructure for card purchasing and online play. Build secure backend services to control card collections for monetization and prevent cheating in online matches.
  - Original request: "We need a server where the card collection can be controlled for monetization, and for the online play element to prevent cheating."
  - Planning: Define API endpoints for card ownership, purchase transactions, and match state validation.
  - Resources: `.github/agent/workflows/workflow-server-infrastructure.md` (to be created)

