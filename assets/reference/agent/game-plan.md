# LotR TCG Digital Game — Project Game Plan

## Mission Statement

Build a fully playable digital implementation of **The Lord of the Rings Trading Card Game** (LotR TCG) that faithfully reproduces the physical card game rules, supports deck building from the full card catalog, and enables play against both human opponents and AI.

---

## Core Features

### 1. Card Database
- Full catalog of all LotR TCG cards (sets 1–19) sourced from the downloaded wiki data.
- Card data includes: title, subtitle, card type, culture, twilight cost, stats (strength/vitality/resistance), keywords, game text, set/rarity/collector number, and card image.
- Cards tagged by format legality (see Supported Formats below).

### 2. Deck Builder
- Visual deck construction interface supporting all formats.
- Enforce deck rules: min 60 draw cards, exactly 9 adventure deck sites, equal FP/Shadow split, 4-copy limit per title, Ring-bearer + The One Ring outside draw deck.
- Format filter: restrict available cards to the selected format (see Supported Formats).
- Save, load, import, and export decks.
- Deck validation with rules feedback.

### 3. Supported Formats

| Format | Sets | Sites | Restrictions |
|--------|------|-------|--------------|
| Fellowship Block | 1, 2, 3 | Sequential | R-List |
| Tower Block | 4, 5, 6 | Sequential | R-List |
| King Block | 7, 8, 10 | Sequential | R-List |
| War of the Ring | 11, 12, 13 | Player choice | R-List |
| Expanded | 10–13 | Player choice | Expanded X-List |
| Standard | 10–19 | Player choice | Standard X-List |
| Open | 0–19 (all sets) | Player choice | R-List |
| Hunters Block *(PC)* | 15, 16, 17 | Sequential | PC Errata required |

- **Set 9 (Reflections)** is a supplemental/reprint set legal in **Open only**.
- **PC Errata (v5.0)** is a per-session flag applied on top of any format — not a separate format tier.
- **Casual Mode**: a lobby/session toggle that disables all X-List, R-List, and errata restrictions for any format. Both players must agree (PvP); freely selectable in PvE vs AI. Planned as a Phase 6 lobby option.

### 4. Game Engine
- Full turn sequence implementation: Fellowship → Shadow(s) → Maneuver → Archery → Assignment → Skirmish(es) → Regroup.
- Twilight pool management (add for FP, remove for Shadow, roaming penalty).
- Wound, burden, and resistance tracking per character.
- Skirmish resolution (strength comparison, damage bonuses, overwhelm, fierce second skirmish).
- Adventure path (sites 1–9), site placement by Shadow players, region twilight bonus.
- Move limit enforcement (2 per turn in 2-3 player, opponents count in 4+).
- Win/loss detection: Ring-bearer killed, Ring-bearer corrupted (resistance 0), fellowship reaches site 9.
- X-List/R-List enforcement per format.

### 5. Card Text Engine
- Parse and execute game text for all card types.
- Support all trigger types: **When**, **Each Time**, **While** (continuous).
- Phase action keywords: **Fellowship:**, **Shadow:**, **Maneuver:**, **Archery:**, **Assignment:**, **Skirmish:**, **Regroup:**, **Response:**.
- Handle special keywords: archer, fierce, damage +X, defender +X, ambush X, aid X, roaming, unhasty, hunter, lurker, etc.

### 6. Multiplayer
- 2-player online play (primary target).
- Support for 3–4 player multiplayer (one FP player, multiple Shadow players per turn).
- Lobby / matchmaking system.
- Turn order and twilight pool synchronized across players.

### 7. AI Opponent
- Basic CPU opponent capable of:
  - Playing a valid Shadow phase (deploy minions within budget).
  - Assigning minions in Assignment phase.
  - Using simple heuristics for skirmish actions.
- Stretch: heuristic-based deck-aware AI; future ML opponent.

### 8. User Accounts & Collection
- User registration and login.
- Card collection tracking (which cards the user owns/has unlocked).
- Saved decks per account.

---

## Technical Approach

**Frontend / Game Engine — Godot 4 (GDScript):**
- **Desktop (Windows / Mac / Linux)**: Godot native export targets.
- **Web**: Godot HTML5 export.
- **Mobile (iOS / Android)**: Godot mobile export targets (future phase).
- **i18n**: Planned for a future phase. Card data model must accommodate per-language name, game text, and lore fields from the outset.

> **Note:** Original plan used React/TypeScript + Tauri/Capacitor. Decision changed to Godot 4 as the single engine for UI, game logic, and all deployment targets.

> **Local Godot Docs:** A local copy of the Godot documentation is available at `assets/reference/godot-docs/`. Consult this before searching the web for Godot API or GDScript usage questions.

**Backend:**
- **API**: Python (FastAPI) — REST endpoints for cards, decks, formats, accounts, and game history.
- **Real-time**: WebSockets (FastAPI native) for live game state and multiplayer events.
- **Game State**: Server-authoritative; all clients receive state updates via WebSocket.

**Data:**
- **PostgreSQL** — persistent storage: cards, decks, users, game history, i18n strings.
- **Redis** — ephemeral: active game sessions, matchmaking queue, WebSocket presence.

**Auth**: JWT — shared across web, mobile, and desktop targets.

**Card Images**: Processed PNGs (white border removed, transparent background) served from `build/do/assets/cards/processed/`. Raw downloaded JPGs remain in `build/do/assets/cards/` as source material.

**Foil cards** (Phase 8): Rendered as a CSS/canvas `mix-blend-mode` overlay on the processed PNG — no separate foil image files required.

---

## Development Phases

| Phase | Scope |
|-------|-------|
| 1 — Data | Card database populated from wiki download; images served |
| 2 — Deck Builder | Deck construction UI with format validation |
| 3 — Engine | Core game engine (single-player, local test) |
| 4 — Card Text | Game text parser and executor for all cards |
| 5 — AI | Basic CPU opponent |
| 6 — Multiplayer | Online 2–4 player matches (1 FP, up to 3 Shadow) |
| 7 — Accounts | User accounts, collections, saved decks |
| 8 — Polish | UI, sound, animations, performance; foil card rendering (CSS/canvas overlay) |
| 9 — Tournaments | Brackets (swiss/elimination), standings, format enforcement, scheduled rounds |

---

## Reference Files

- **Rules**: [rules-reference.md](rules-reference.md) — Comprehensive Rules 4.2 summary
- **Godot docs**: `assets/reference/godot-docs/` — local copy of Godot documentation (API, GDScript, tutorials)
- **Card data source**: `build/do/assets/cards/` — downloaded card HTML and images
- **Wiki source**: `build/do/assets/wiki/` — downloaded wiki pages including rules HTML
