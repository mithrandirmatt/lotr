# LotR TCG Digital Game — Project Game Plan

## Mission Statement

Build a fully playable digital implementation of **The Lord of the Rings Trading Card Game** (LotR TCG) that faithfully reproduces the physical card game rules, supports deck building from the full card catalog, and enables play against both human opponents and AI.

---

## Core Features

### 1. Card Database
- Full catalog of all LotR TCG cards (sets 1–19) sourced from the downloaded wiki data.
- Card data includes: title, subtitle, card type, culture, twilight cost, stats (strength/vitality/resistance), keywords, game text, set/rarity/collector number, and card image.
- Cards tagged by format legality (Fellowship block, Tower block, King block, War of the Ring, Open, Standard).

### 2. Deck Builder
- Visual deck construction interface supporting all formats.
- Enforce deck rules: min 60 draw cards, exactly 9 adventure deck sites, equal FP/Shadow split, 4-copy limit per title, Ring-bearer + The One Ring outside draw deck.
- Format filter: restrict available cards to the selected format.
- Save, load, import, and export decks.
- Deck validation with rules feedback.

### 3. Game Engine
- Full turn sequence implementation: Fellowship → Shadow(s) → Maneuver → Archery → Assignment → Skirmish(es) → Regroup.
- Twilight pool management (add for FP, remove for Shadow, roaming penalty).
- Wound, burden, and resistance tracking per character.
- Skirmish resolution (strength comparison, damage bonuses, overwhelm, fierce second skirmish).
- Adventure path (sites 1–9), site placement by Shadow players, region twilight bonus.
- Move limit enforcement (2 per turn in 2-3 player, opponents count in 4+).
- Win/loss detection: Ring-bearer killed, Ring-bearer corrupted (resistance 0), fellowship reaches site 9.
- X-List/R-List enforcement per format.

### 4. Card Text Engine
- Parse and execute game text for all card types.
- Support all trigger types: **When**, **Each Time**, **While** (continuous).
- Phase action keywords: **Fellowship:**, **Shadow:**, **Maneuver:**, **Archery:**, **Assignment:**, **Skirmish:**, **Regroup:**, **Response:**.
- Handle special keywords: archer, fierce, damage +X, defender +X, ambush X, aid X, roaming, unhasty, hunter, lurker, etc.

### 5. Multiplayer
- 2-player online play (primary target).
- Support for 3–4 player multiplayer (one FP player, multiple Shadow players per turn).
- Lobby / matchmaking system.
- Turn order and twilight pool synchronized across players.

### 6. AI Opponent
- Basic CPU opponent capable of:
  - Playing a valid Shadow phase (deploy minions within budget).
  - Assigning minions in Assignment phase.
  - Using simple heuristics for skirmish actions.
- Stretch: heuristic-based deck-aware AI; future ML opponent.

### 7. User Accounts & Collection
- User registration and login.
- Card collection tracking (which cards the user owns/has unlocked).
- Saved decks per account.

---

## Technical Approach

- **Backend**: Python (FastAPI or Django) — game logic, card database, multiplayer state.
- **Frontend**: Web-based (React or similar) — deck builder, game board, card rendering.
- **Game State**: Server-authoritative; clients receive state updates.
- **Card Images**: Served from the downloaded `assets/cards/` directory.
- **Database**: Relational DB (PostgreSQL) for cards, decks, users, game history.
- **Real-time**: WebSockets for live game play.

---

## Development Phases

| Phase | Scope |
|-------|-------|
| 1 — Data | Card database populated from wiki download; images served |
| 2 — Deck Builder | Deck construction UI with format validation |
| 3 — Engine | Core game engine (single-player, local test) |
| 4 — Card Text | Game text parser and executor for all cards |
| 5 — AI | Basic CPU opponent |
| 6 — Multiplayer | Online 2-player matches |
| 7 — Accounts | User accounts, collections, saved decks |
| 8 — Polish | UI, sound, animations, performance |

---

## Reference Files

- **Rules**: [rules-reference.md](rules-reference.md) — Comprehensive Rules 4.2 summary
- **Card data source**: `build/do/assets/cards/` — downloaded card HTML and images
- **Wiki source**: `build/do/assets/wiki/` — downloaded wiki pages including rules HTML
