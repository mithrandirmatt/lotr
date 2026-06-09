# LotR TCG Project — Completed Task Tracker

## Completed

Only list completed tasks here.

## Completed List:

- **LOT-001** — Generate game-logic database from card database. Parse each card's `game_text` to create structured logical actions (triggers, costs, conditions, effects) for runtime use.
  - **Status**: ✅ **COMPLETED** — Game logic database generated with 3,216 cards parsed. Database stored in `gotdot/assets/data/game_logic_database.json`.

- **LOT-002** — Implement server infrastructure for card purchasing and online play. Build secure backend services to control card collections for monetization and prevent cheating in online matches.
  - Original request: "We need a server where the card collection can be controlled for monetization, and for the online play element to prevent cheating."
  - Planning: Define API endpoints for card ownership, purchase transactions, and match state validation.
  - Resources: `.github/agent/workflows/workflow-server-infrastructure.md` (to be created)

- **LOT-003** — Make admin account. User: lotradmin, password: yourmommalooksfunny.
  - Admin account: Can do the following:
    - Add/remove cards from the database
    - Add/remove users
    - Grant/revoke admin privileges to other users
  - **Status**: ✅ **COMPLETED** — Admin account created with full administrative capabilities.

- **LOT-004** — Login/auth endpoints implemented. Register, login (JWT), refresh token, logout, and protected route dependency all in `server/server/routes/api.py`.
  - **Status**: ✅ **COMPLETED**

- **LOT-005** — Deck Manager backend implemented.
  - Added `Deck` and `DeckCard` SQLAlchemy models to `server/server/models/models.py`.
  - Added `DeckCreate`, `DeckUpdate`, `DeckResponse`, `DeckListResponse`, `DeckCardAdd`, `DeckCardRemove`, `DeckCardEntry`, `DeckFormat` Pydantic schemas to `server/server/models/schemas.py`.
  - Added deck CRUD endpoints to `server/server/routes/api.py`:
    - `POST /api/v1/decks` — create deck
    - `GET /api/v1/decks` — list user's decks
    - `GET /api/v1/decks/{deck_id}` — get deck with cards
    - `PUT /api/v1/decks/{deck_id}` — rename/update deck
    - `DELETE /api/v1/decks/{deck_id}` — delete deck (cascade removes DeckCards)
    - `POST /api/v1/decks/{deck_id}/cards` — add card to deck (validates ownership)
    - `DELETE /api/v1/decks/{deck_id}/cards/{card_id}` — remove card from deck
    - `GET /api/v1/decks/legal-cards?format=standard|modern|open` — list owned cards legal in format
  - Wired `api_router` into `server/server/app.py`.
  - **Status**: ✅ **COMPLETED**

- **LOT-006** — Admin Panel (React + TypeScript + Vite).
  - Tolkien currency system: 1 Tolkien = $1 · pack=1T · starter_deck=5T · booster_box=30T
  - Backend: `is_moderator` field added to User model; `PUT /admin/users/{id}/moderator` toggle endpoint
  - React admin panel at `frontend/admin-panel/`: Login, Dashboard, Users, Cards pages
  - User management: search/paginate, Tolkien balance adjust, moderator toggle, triple-confirm delete
  - Card management: list/search/paginate, add card form, soft-delete
  - Auth: JWT login gated to `is_admin=True` accounts; `is_moderator` grants in-game role only (no panel access)
  - Key files: `server/server/models/models.py`, `server/server/models/schemas.py`, `server/server/routes/api.py`, `frontend/admin-panel/src/`
  - **Status**: ✅ **COMPLETED**

- **LOT-007** — Login Screen.
  - Implemented login and register pages with validation, authentication context, and protected routing.
  - Backend endpoints already exist (see LOT‑004). Front‑end now redirects to dashboard on success.
  - **Status**: ✅ **COMPLETED**