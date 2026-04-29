# LotR TCG Project — Task Tracker

## In Progress

<!-- Tasks currently being worked on -->

## Todo

### Phase 1 — Data & Environment Setup (remaining)
- [ ] Verify card_database.json completeness — spot-check set coverage, field completeness (title, culture, type, cost, stats, game text, image path)
- [ ] Confirm processed card images cover all sets (sets 0–19 folders exist; verify PNGs inside)
- [ ] Design and document final DB schema (PostgreSQL) for cards, i18n fields, format legality
- [ ] Install Godot 4 and confirm it runs in the WSL2/Docker dev environment (see `assets/reference/godot-docs/` for local API/GDScript reference)
- [ ] Create Godot project scaffold in repo (project root, folder structure, .gitignore)
- [ ] Implement and run a "Hello World" Godot scene to confirm the engine works end-to-end
- [ ] Update game-plan.md Technical Approach to reflect Godot as the frontend/engine (replacing React/Tauri/Capacitor)

### Phase 2 — Deck Builder
- [ ] Backend: FastAPI project scaffold (Python)
- [ ] Backend: `/cards` endpoint serving card_database.json from PostgreSQL
- [ ] Backend: `/decks` CRUD endpoints
- [ ] Frontend: React + TypeScript project scaffold (Vite)
- [ ] Frontend: Card browser UI (search, filter by culture/type/format)
- [ ] Frontend: Deck construction UI (add/remove cards, sidebar)
- [ ] Frontend: Deck validation (60-card min, 9 sites, 4-copy limit, FP/Shadow split, Ring-bearer rules)
- [ ] Frontend: Save/load/import/export deck
- [ ] Frontend: Format selector (Fellowship Block, Standard, Open, etc.)

### Phase 3 — Game Engine
- [ ] Core game state model (players, fellowship, shadow, site path, twilight pool)
- [ ] Turn sequence implementation (Fellowship → Shadow → Maneuver → Archery → Assignment → Skirmish → Regroup)
- [ ] Twilight pool management (add for FP move, remove for Shadow deploy, roaming penalty)
- [ ] Wound/burden/resistance tracking
- [ ] Skirmish resolution (strength, damage, overwhelm, fierce)
- [ ] Win/loss detection (Ring-bearer killed, corrupted, site 9 reached)
- [ ] Move limit enforcement
- [ ] Local single-player test harness

### Phase 4 — Card Text Engine
- [ ] Card text parser (keyword extraction, trigger identification)
- [ ] Effect executor (phase actions, responses, continuous effects)
- [ ] Support all trigger types: When / Each Time / While
- [ ] Support all phase keywords and special keywords (archer, fierce, damage+X, etc.)

### Phase 5 — AI Opponent
- [ ] Basic Shadow AI (deploy minions within twilight budget)
- [ ] Assignment AI (assign minions to companions)
- [ ] Skirmish action heuristics

### Phase 6 — Multiplayer
- [ ] WebSocket game state sync
- [ ] Lobby / matchmaking system
- [ ] 3–4 player support (1 FP, multiple Shadow)

### Phase 7 — Accounts
- [ ] User registration and login (JWT)
- [ ] Card collection tracking
- [ ] Saved decks per account

### Phase 8 — Polish
- [ ] UI polish, sound, animations
- [ ] Foil card rendering (CSS/canvas mix-blend-mode overlay)
- [ ] Performance optimization

### Phase 9 — Tournaments
- [ ] Bracket system (swiss/elimination)
- [ ] Standings and format enforcement
- [ ] Scheduled rounds

---

## Done

### Phase 1 — Data
- [x] Downloaded full card HTML and images from wiki (sets 0–19, `build/do/assets/cards/`)
- [x] Downloaded wiki pages (`build/do/assets/wiki/`)
- [x] Built card database pipeline (`build/py/wiki/create_card_database.py`) → `card_database.json`
- [x] Built starter deck database (`create_starter_database.py`) → `starter_database.json`
- [x] Built X-List / R-List databases (`create_xlist_databases.py`) → `xlist_database.json`
- [x] Built errata database → `errata_database.json`
- [x] Processed card images (white border removed, transparent background) → `build/do/assets/cards/processed/`

### Project Setup
- [x] Makefile build system (`build/makefile`, `build/makefiles/`)
- [x] Docker / WSL2 dev environment (`build/docker/`)
- [x] Agent configuration (Continue + Copilot agents, rules, game-plan, rules-reference)
- [x] Project reference docs (`assets/reference/agent/`)
