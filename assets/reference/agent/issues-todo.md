# In-Progress Working Notes

Rolling checkpoint for whichever issue is actively being implemented. Keep this
updated continuously while working (not just at start/end) so work can be
resumed cleanly after an interruption. Reset this file once the issue is
completed and moved to `issues-completed.md`.

## Current Issue

LOT-025 — Unified player economy, release control, and deck builder experience.

LOT-025 is a huge consolidation issue (economy, release control, gifting,
deck builder UX). Rather than build it all at once, it's delivered as a
series of narrow, independently-verified slices. Deliberately deferred scope
is tracked in **LOT-100** (`issues-tracker.md`), not silently dropped — check
there for the current full backlog list.

Slices completed so far:

- **Slice 1** (previous session): Set Release model + admin
  activate/deactivate API + admin panel "Set Releases" page.
- **Slice 2** (previous session): **Server-authoritative booster pack
  generation + foil tracking + sell-back pathway** (LOT-020 core wired into
  the LOT-025 store surface) — see "Files Touched This Slice" below.
- **Slice 3** (previous session): **`booster_box` purchases now generate
  cards too** (25 packs/box — see "Slice 3" section below).
- **Slice 4** (previous session): **LOT-021 baseline economy/circulation
  telemetry** — `GET /admin/economy/summary` (see "Slice 4" section below).
- **Slice 5** (previous session): **LOT-019 gift ledger and redemption
  lifecycle** — admin-issue/list/redeem/revoke gift APIs for pack/
  booster_box products (see "Slice 5" section below).
- **Slice 6** (previous session, compacted — see repo memory/session
  summary for full detail): Real card catalog import (real ~3,411-card
  LotR TCG catalog via `server/scripts/migrate_import_card_catalog.py`,
  reading `build/do/assets/database/card_database.json`; the 12 placeholder
  Set-1 rows were deactivated, not deleted). **Confirmed still applied** via
  a live DB check this session: `3411` active cards across sets
  0-19/30-32, rarity breakdown common=1014/uncommon=883/rare=1113/
  legendary=186/mythic=215. This closes the "real card catalog import"
  LOT-100 backlog bullet.
- **Slice 7** (previous session, compacted): Pack-opening card-reveal
  overlay (`card_reveal.gd`/`.tscn`) wired into `new_game.gd` for both
  starter-deck and booster-pack entitlement claims — this is the
  "store-surface gift/entitlement claim UX" the LOT-100 backlog called out
  as not-yet-started; it's now done for the claim-flow presentation layer.
- **Slice 8** (previous session, compacted): Deck builder UX rework —
  `deck_builder.gd/tscn` simplified into a deck-selection screen; new
  `deck_editor.gd/tscn` + `dnd_card_list.gd` implement a two-pool
  (selected/available) editor with rarity-only filter checkboxes, a card
  preview panel, and drag-drop/double-click/single-click add-remove
  interactions; backed by a new `GET /users/me/cards/available` endpoint.
  **This is a functional interim deck editor, NOT the LOT-025 spec's exact
  binder-metaphor (9x9 two-page-spread browser) / split-screen deck-summary
  grid with Deck Cards/Sites/Starting Fellowship tabs / grouped
  culture-companion-ally-etc. facet filters / sets checklist / mutually-
  exclusive tournament-ruleset controls.** That full spec is still open —
  left in LOT-100 as "deck builder UX in full", now scoped down since the
  underlying pool/filter/preview/CRUD plumbing already exists and the
  remaining gap is presentation/layout + the grouped-facet filter set +
  ruleset exclusivity + the 25-deck cap. Also found and fixed a real bug
  this segment: `Rarity` enum was missing `'mythic'`, crashing
  `CardResponse` validation for any mythic-rarity card (added `MYTHIC =
  "mythic"`).
- **Slice 9** (this session): Investigated and reconciled this file /
  `issues-tracker.md` against actual server code (found several backlog
  items already done but undocumented: `starter_deck` card generation via
  `_grant_starter_deck_cards()` + `server/data/starter_decks_set1.json`,
  and the LOT-018 new-account bootstrap grant). Then implemented three
  more LOT-100 backlog items:
  - **25-decks-per-user cap**: `MAX_DECKS_PER_USER = 25` enforced in
    `POST /decks` (400 once at the cap). Verified live (created 25 decks,
    26th correctly rejected).
  - **LOT-018 per-set-unlock release bundle**: `_grant_release_bundle_to_all_users()`,
    called from `POST /admin/set-releases/{n}/activate` on an
    inactive->active transition; grants 1 starter_deck + 5 booster_pack
    entitlements to every active user for that set, guarded idempotent by
    checking for any existing entitlement row for that (user, set_number)
    first (so a deactivate/reactivate cycle never double-grants). Verified
    live: activation granted exactly 6 entitlements to a pre-registered
    test user; a deactivate+reactivate cycle afterward left the count
    unchanged at 6.
  - **Weekly active-user random foil reward** (LOT-021/LOT-025): new
    `WeeklyRewardRoll` model/table (`weekly_reward_rolls`, migration
    `migrate_add_weekly_rewards.py`) recording one row per
    `(user_id, week_index)` regardless of win/loss — this is what enforces
    non-stacking/max-1-per-week even across multiple logins in the same
    week. `week_index` is computed from `User.created_at` (registration
    timestamp), not a global calendar week. Rolled lazily inside
    `_issue_tokens_for_user()` (the single choke point for every successful
    login path: password login, local-admin shortcut, 2FA verify-login, 2FA
    recovery — but NOT token refresh, which doesn't call it), wrapped in a
    try/except so a reward-roll bug can never block login. 5% win chance,
    weighted common/uncommon/rare (`WEEKLY_FOIL_REWARD_RARITY_WEIGHTS`,
    placeholder tuning knob like the other economy constants), grants one
    foil `Ownership` row + a `DistributionTransaction(source="reward")`.
    Added `'reward'` to `DistributionTransaction.source`'s enum (was
    missing it; no DB-level CHECK constraint exists on that raw-SQL-created
    column, so this is safe, same pattern as the earlier `Rarity` enum
    drift). Verified via: (a) an in-process script forcing win/loss/
    idempotency by monkeypatching `random.random`, and (b) a real
    register+login HTTP round trip to confirm the hook doesn't break the
    actual login route.

  All three verified via `get_errors` clean + `pytest tests/ -q` (46/46
  passing throughout) + live smoke tests (temporary scripts, deleted after
  use, per repo convention). `issues-tracker.md`'s LOT-100 list and
  `/memories/repo/todos.md` updated to match.

`starter_deck` purchases generate real cards from a curated set-1 decklist
(done, see Slice 9 above), but gifting `starter_deck`/`promo_card` products
is still blocked on the same missing curated-content gap for other sets
(tracked in LOT-100). The exact deck-builder binder/tabs/ruleset-exclusivity
spec (25-deck cap is now done) is the main remaining LOT-100 follow-up slice
(card-authoring workflow and LOT-021 historical trend snapshots/alerting are
now also done — see Slices 12 and 13 below).

### Slice 10 (this session): weekly-active-user reward telemetry (LOT-021)

`GET /admin/economy/summary` now also returns `weekly_reward_stats`
(`WeeklyRewardStats` schema): `total_rolls`, `total_wins`, `total_losses`,
`win_rate`, `distinct_users_rolled`, `wins_by_rarity`, aggregated from the
`weekly_reward_rolls` table added in Slice 9. `distinct_users_rolled` is a
proxy for weekly-active users, since a roll row (win or loss) is only ever
created via a successful login. Historical trend snapshots and
threshold/drift alerting remain open (need a time-series storage/config
decision) and are still tracked in LOT-100.

Verified via: (a) `pytest tests/ -q` (47/47 passing after updating the two
existing `EconomySummaryResponse` construction tests to supply the new
required field, plus a new `test_weekly_reward_stats` unit test), (b) a live
smoke test hitting the real `lotr-server` container (`admin login ->
GET /admin/economy/summary`, asserting the new field's shape), temp script
deleted after use. `get_errors` clean on `api.py`/`schemas.py`.
`issues-tracker.md`'s LOT-100 list updated to mark this item done and to
correct a stale bullet that still claimed `starter_deck`/`booster_box`
purchases only deducted Tolkien (superseded by later, more detailed bullets
in the same list). `/memories/repo/todos.md` updated to match.

### Slice 11 (this session): release events + participation schema (LOT-022)

New `ReleaseEvent`/`EventParticipation` models
(`migrate_add_release_events.py`, idempotent raw-SQL migration). Lifecycle:
`scheduled -> live -> closed`. Routes added:
- `POST /admin/events` (create, starts `scheduled`), `GET /admin/events`
  (optional `set_number` filter), `POST /admin/events/{id}/activate`,
  `POST /admin/events/{id}/close` (both idempotent no-ops if already in the
  target status), `GET /admin/events/{id}/participants` (auditable list).
- `GET /events` (public/any-authenticated-user list), `POST
  /events/{id}/join` (400 if the event isn't `live`; otherwise idempotent —
  rejoining returns the existing `EventParticipation` row rather than
  erroring or duplicating; a unique `(event_id, user_id)` index plus an
  `IntegrityError` catch handles the concurrent-join race).
- `admin_activate_set_release` now calls a new `_ensure_live_release_event`
  helper on every activation: reuses the most recent event already
  recorded for that `set_number` (reactivating it to `live`) instead of
  creating a duplicate, so "Set activations are linked to event records"
  holds even across a deactivate/reactivate cycle.
- `reward_policy` is a free-form nullable JSON column/field, deliberately
  left pluggable — this slice only builds the event/participation
  plumbing, not a reward-policy engine (that's future LOT-100 scope, e.g.
  wiring promo-card prize awarding through `EventParticipation
  .reward_transaction_id`).

Verified via: (a) `pytest tests/ -q` (47/47, unchanged since no existing
schema was modified), (b) a live smoke test covering create -> join-rejected
-while-scheduled -> activate -> join -> idempotent rejoin (same
participation id) -> admin participants list (exactly 1) -> close -> public
list visibility, and (c) a second live smoke test specifically confirming
set activation auto-links exactly one reused `live` event across a
deactivate/reactivate cycle (no duplicate event rows). Both temp scripts
deleted after use. `get_errors` clean on all touched files.
`issues-tracker.md`'s LOT-100 list and `/memories/repo/todos.md` updated to
match.

### Slice 12 (this session): card-authoring review-gate workflow (LOT-100)

New `Card` columns: `publish_status` (`draft`/`in_review`/`published`,
DB-level default stays `'published'` so the existing bulk-imported catalog
needs no backfill; ORM Python-side default is `'draft'` so newly authored
cards start unpublished) and `review_notes`
(`migrate_add_card_review_gate.py`, idempotent — checks
`PRAGMA table_info(cards)` before each `ALTER TABLE ADD COLUMN` since
SQLite has no `ADD COLUMN IF NOT EXISTS`).

Public catalog gating: `GET /cards` and `GET /cards/{id}` now filter on
`publish_status == 'published'` — drafts/in-review cards are invisible
until published.

New admin routes:
- `GET /admin/cards` — any status, optional `publish_status` filter,
  paginated, newest first.
- `POST /admin/cards/{id}/submit-review` — `draft -> in_review` (400 if
  not currently `draft`).
- `POST /admin/cards/{id}/publish` — `in_review -> published` (400 if not
  currently `in_review`).
- `POST /admin/cards/{id}/reject` — `in_review -> draft`, records
  `review_notes` from the request body (400 if not currently `in_review`).

Release linking: `CardBase`/`CardCreate`/`CardUpdate` gained a `set_number`
field (previously missing entirely from the card schemas, despite `Card`
already having the column for booster generation). New
`_validate_card_set_number` helper 400s if the `set_number` doesn't match
an existing `SetRelease`; wired into both `create_card` and `update_card`.

Two pre-existing bugs found and fixed while building this (both blocked
end-to-end verification of `create_card`, so fixing them was necessary,
not scope creep):
1. `CardCreate`/`CardUpdate` expose a `stats` field with no matching `Card`
   column (`Card` has `attributes`, not `stats`) — `Card(**card_data
   .model_dump())` in `create_card` would have raised `TypeError` for the
   unexpected `stats` kwarg (untested code path, no existing test
   exercised it). Fixed by explicitly remapping `stats` -> `attributes`
   in both `create_card` and `update_card`.
2. `CardResponse` had no `model_config = ConfigDict(from_attributes=True)`
   on `CardBase`, and even with it added, an ORM `Card` object has no
   attribute literally named `stats` (it's `attributes`) — so
   `CardResponse.model_validate(card)` / returning `card` directly for
   `response_model=CardResponse` always silently serialized `stats: null`
   regardless of actual data. Fixed by adding
   `model_config = ConfigDict(from_attributes=True)` to `CardBase` plus a
   `Card.stats` Python `@property` that returns `self.attributes`, so
   ORM->schema serialization now round-trips real data.

Verified via: (a) `pytest tests/ -q` (47/47, unchanged), (b) migration run
live against the DB (`Added 'publish_status' column`, `Added
'review_notes' column`, index created), (c) a live smoke test covering:
release-linking 400 on a bogus `set_number`, create as `draft` with real
`set_number` and `stats` payload (verified `stats` round-trips correctly),
hidden from public `GET /cards/{id}` (404) while draft, `publish` rejected
with 400 while still `draft`, `submit-review` -> `in_review`, `reject` ->
`draft` with `review_notes` recorded, resubmit -> `publish` ->
`published`, now visible via public `GET /cards/{id}` and `GET
/cards?search=...`, and the admin `GET /admin/cards?publish_status=draft`
filter. Temp smoke script deleted after use. `get_errors` clean on all
touched files (only pre-existing host-side sqlalchemy import-resolution
noise in `models.py`, unrelated to these changes).

### Slice 13 (this session): economy trend snapshots + drift alerting (LOT-021)

New `EconomySnapshot` model/table (`migrate_add_economy_snapshots.py`,
idempotent). This repo has no job-scheduling infra (same reasoning as the
weekly foil reward), so instead of a background cron, `GET
/admin/economy/summary` now lazily captures at most one snapshot per
calendar day via `_maybe_capture_economy_snapshot` — the first admin call
to that endpoint on a given day persists a row; subsequent calls the same
day are no-ops. Each snapshot stores promoted scalar totals (cards in
circulation, foil issued, Tolkien net flow, sell-back cards/Tolkien
returned, weekly reward rolls/wins/distinct users) plus the full raw
`EconomySummaryResponse` JSON for drill-down.

New `GET /admin/economy/trends` route: returns snapshots oldest-first
(`limit` query param, default 30, max 365) plus `total` (full table count,
independent of the page). Simple threshold/drift alerting: for each
snapshot after the first, compares 4 key metrics (cards in circulation,
foil issued, Tolkien net flow, weekly-active users) against the previous
snapshot; if the percentage change is >= `ECONOMY_SNAPSHOT_DRIFT_ALERT_THRESHOLD_PCT`
(currently a single tunable constant, 25%), an `alerts` string is added to
that snapshot's response (e.g. "Tolkien net flow up 40% since previous
snapshot"). Deliberately a single tunable constant rather than a full
alerting-rules engine — no alerting config/notification infra exists yet
to wire further (out of scope for this slice).

Verified via: (a) `pytest tests/ -q` (47/47, unchanged), (b) migration run
live against the DB, (c) a live smoke test confirming: calling `/summary`
captures exactly one new snapshot, a second `/summary` call the same day
does NOT capture a duplicate, the captured snapshot's scalar totals match
the live summary that triggered it, and the `limit` query param caps the
page size while `total` still reflects the full table. Temp smoke script
deleted after use. `get_errors` clean on all touched files.

### Slice 14 (this session): verified live legality diagnostics (LOT-032/LOT-014) — already implemented, no code changes

Picked "Wiring live legality diagnostics (LOT-032/LOT-014) into the deck
builder" as the next LOT-100 item and investigated before implementing (per
the pattern from Slice 9: several backlog items have turned out to already
be built but undocumented). Found the entire feature already exists and is
already wired end-to-end:

- **Server (LOT-014)**: `server/server/services/deck_legality.py`'s
  `evaluate_deck_legality()` (draw-deck size >=60, equal FP/Shadow split,
  9-site adventure deck) and `check_copy_limit()` (max 4 copies per card
  title, max 1 copy per site) are both implemented and unit tested
  (`server/tests/test_deck_legality.py`). `GET /decks/{deck_id}/legality`
  exposes the former; `POST /decks/{deck_id}/cards` calls the latter before
  inserting, converting a `ValueError` to an HTTP 400 with the precise
  message. Format/X-list/R-list/errata constraints are **not** implemented
  (confirmed genuine remaining gap, left open in `issues-tracker.md`'s
  LOT-014 entry).
- **Client (LOT-032)**: `gotdot/scripts/deck_editor.gd`'s
  `_refresh_legality()` calls `Api.get_deck_legality()` from inside
  `_load_deck()`, which both `_add_card()` and `_remove_card()` await via
  `_load_all()` — every add/remove (double-click or drag-drop) re-runs the
  full live legality check and updates the `LegalityLabel` UI node
  (aggregate counts + issue list, green when legal / orange when not).
  Copy-limit violations are blocked proactively at add-time and surfaced
  via `_set_notice(...)`.

No code changes were needed. Verified via: (a) `pytest tests/ -q` (47/47,
unchanged), (b) a live HTTP smoke test exercising the exact routes the
Godot client calls — seeded a test user's ownership directly via the ORM
(no HTTP ownership-grant route exists) with a hand-picked 10 Free
Peoples + 10 Shadow + 10 Site cards, then drove the same
create-deck/add-card/get-legality/remove-card routes the client uses:
empty deck starts illegal (size 0, 0 sites) -> adding 3x each of 10 FP + 10
Shadow cards yields a correct 60/30/30 draw deck still illegal on site
count -> adding 9 sites makes it legal with an empty issues list -> a 5th
copy of an FP card is rejected 400 ("...maximum is 4...") -> a 2nd copy of
an already-decked site is rejected 400 ("...only one copy...") -> removing
a site drops site_count to 8 and flips `is_legal` back to false. Temp smoke
script deleted after use. `get_errors` not needed (no files changed).
`issues-tracker.md`'s LOT-100 list, LOT-014 entry, and LOT-032 entry all
updated to document this finding and its verification.

### Slice 15 (this session): grouped card-type/culture deck-builder filters (LOT-100/LOT-025)

`gotdot/scripts/deck_editor.gd`'s filter panel previously only had rarity
checkboxes. Replaced `_build_filters()` with a generic
`_add_filter_section(title, values, on_toggled)` helper, called three times
(Rarity, Card Type, Culture), reading the real distinct values found in the
imported catalog: `CARD_TYPES` (Ally/Artifact/Companion/Condition/Event/
Follower/Map/Minion/Possession/Site/"The One Ring") and `CULTURES` (~24
values: Gondor/Rohan/Isengard/Sauron/Shire/Elven/Dwarven/Orc/Men/Raider/
Uruk-hai/Gollum/Moria/Dunland/Gundabad/Smaug/Esgaroth/Spider/Troll/Mirkwood/
Ringwraith/Gandalf/"The One Ring"/Site). Both are read from
`card.get("stats", {}).get("card_type"/"culture")` — `stats` is the card's
full `attributes` JSON, already serialized by the server (`CardResponse
.stats = card.attributes`), so **no server changes were needed**, only the
Godot client reading a field it wasn't reading before. New combined
`_passes_filters(card)` helper replaces the old inline rarity-only check in
both `_render_selected_list()`/`_render_available_list()`. Since ~41 total
checkboxes no longer fit in the fixed-height sidebar, `deck_editor.tscn`'s
`FiltersBox` is now wrapped in a `FiltersScroll` `ScrollContainer` (panel
widened 160->200px).

The LOT-025 spec's wishlist phrasing ("grouped culture/companion/ally/
burdens/signet/event/condition/weapon/possession filters") doesn't match
the real card taxonomy: "signet" is a per-card field (not a card_type),
"Weapon" is a `subtypes` entry on some Possession/Artifact cards (not a
top-level card_type), and no "Burden" card_type exists at all. Implemented
what maps to real data (Card Type + Culture groups) rather than inventing
fake categories; documented in `/memories/repo/godot-dev-gotchas.md`.

No automated visual/screenshot testing exists for Godot scenes in this
repo. Verified instead via two Godot headless checks (new pattern, written
up in `/memories/repo/godot-dev-gotchas.md` for reuse): (a) a full project
boot (`--headless --path gotdot --quit`) with zero script/scene errors, and
(b) a temp `_tmp_validate_deck_editor.gd` (`-s` SceneTree script, deleted
after use) that `load()`s + `instantiate()`s `deck_editor.tscn` directly —
this is the check that actually exercises the new `@onready var
_filters_box = $.../FiltersScroll/FiltersBox` node path and confirms the
script still compiles with the `Api` autoload singleton resolvable (note:
must override `_initialize()`, not `_init()`, or `Api` isn't registered yet
and you get a false-positive compile error — also documented in the gotcha
file). Both checks passed cleanly. `get_errors` clean on both touched
files. This UI-layout change was NOT screenshot-verified (no tooling
available) — disclosed rather than claimed as visually confirmed.
`issues-tracker.md`'s LOT-025/LOT-100 "Deck builder UX" bullet updated to
mark the grouped-filters sub-item done and explain the scoping decision.

### Slice 16 (this session): Sets checklist filter in the deck editor (LOT-100/LOT-025)

Added a fourth filter group ("Set") to `deck_editor.gd`, following the same
`_passes_filters()` pattern as Rarity/Card Type/Culture, but unlike those
three it's NOT a fixed compile-time list — `Card.set_number` is open-ended
(the spec plans through Set 19; only Set 1 has real cards today), so the
checkbox list is built dynamically from whatever `set_number` values
actually appear across the loaded deck + available-pool cards
(`_update_set_filter()`, called once per `_load_all()` after both pools are
fetched). New `_set_section` `VBoxContainer` is created once in
`_build_filters()` and only its own children get cleared/rebuilt on
subsequent reloads, so toggled Rarity/Card Type/Culture checkboxes aren't
reset by repeated set-discovery passes. Checkbox labels use the real set
name from the new `Api.get_active_sets()` client method
(`GET /releases/active-sets`, public/no-auth route, fetched once in
`_ready()`), falling back to "Set N" for any card belonging to a
since-deactivated set not in that list. `_active_sets` entries persist
across reloads (never reset), so a user's filter choice survives
add/remove-card actions the same way the other three filter groups already
did.

No server changes were needed (`CardResponse`/`CardBase` already exposed
`set_number` top-level, confirmed by reading `schemas.py`). Verified via
the same two Godot headless checks established in Slice 15 (full project
boot with zero errors; a temp `-s` SceneTree script instantiating
`deck_editor.tscn` directly) — hit one new gotcha not seen before: Godot's
static type inference rejects `var x := load(...)` / `var y := scene
.instantiate()` in a plain `SceneTree` script with
`"Cannot infer the type of ... variable because the value doesn't have a
set type"`; fixed by explicitly typing them (`var scene: PackedScene =
load(...)`, `var inst: Node = scene.instantiate()`). Since the real catalog
only has Set 1 active today, this could only be checked for "exactly one
checkbox, always checked" — the multi-set code path itself is untested
against live multi-set data (there isn't any yet), but it's structurally
identical to the already-proven card-type/culture filters.
`issues-tracker.md`'s "Deck builder UX" bullet updated; "sets checklist"
removed from the "Still open" list.

### Slice 17 (this session): format + X-List enforcement + errata disclosure (LOT-014)

Picked LOT-014's remaining gap ("Enforce format + X-list/R-list/errata
constraints") as the next item. Research first (per the Slice 9/14 pattern)
revealed the tracker's assumption was only half-true: real X-List/errata/
format data already existed — `build/py/wiki/create_xlist_databases.py`/
`create_card_database.py` build `card_database.json` with per-card
`formats` (real tournament format names), `on_xlist` (X-List format
names), and `has_errata` (bool), and `migrate_import_card_catalog.py`
already copies this wholesale into live `Card.attributes` (confirmed via
live DB query: 3411/3426 cards have `formats` populated). So only
enforcement logic was missing, not a new data model. No R-List data exists
anywhere in the repo (confirmed via grep across `build/py/wiki/**` for
"r_list|R-List|RList|restricted" — zero matches) — left as a documented
permanent gap rather than inventing fake restricted-card data.

Scope: enforce format + X-List for real (using the scraped data already in
`Card.attributes`); treat errata as informational-only (no card-text
engine exists to apply corrected effects); explicitly leave R-List
unimplemented with the reasoning documented in code and tracker docs.

Changes:
- `models.py`: `Deck.format` enum values changed from the fictional
  `standard`/`modern`/`open` placeholders to the real tournament format
  names (`Fellowship Block`, `Tower Block`, `King Block`, `Expanded`,
  `Standard`, `Open`), matching the real `formats` values found across the
  catalog (`War of the Ring`/`Hunters Block` from `game-plan.md`'s spec
  table are NOT included — no card in the current catalog lists them, so
  adding them would be unenforceable).
- `schemas.py`: `DeckFormat` enum updated to match; `DeckLegalityResponse`
  gained `errata_notes: List[str]`.
- `deck_legality.py`: new `is_format_legal(card, format_name)` / 
  `check_format_legality(card, format_name)` (X-List membership overrides
  an otherwise-legal `formats` membership; cards with no scraped `formats`
  data — e.g. dev-seed placeholders — are treated as legal everywhere so
  missing data never silently bans a card). `evaluate_deck_legality()`
  gained an optional `format_name` param (backward compatible — existing
  callers without it are unaffected) plus `errata_notes` population.
- `api.py`: removed the old broken/unused `FORMAT_LEGAL_SETS` placeholder
  dict. `POST /decks/{deck_id}/cards` now calls `check_format_legality`
  before inserting (400 on rejection). `GET /decks/{deck_id}/legality`
  passes `deck.format` through. `GET /decks/legal-cards` was completely
  rewritten — it previously validated the format string but never actually
  filtered cards by it (dead functionality); now filters via
  `is_format_legal`. **Also found and fixed a real pre-existing routing
  bug** while live-testing: `/decks/{deck_id}` was registered before
  `/decks/legal-cards`, so FastAPI matched `/decks/legal-cards` requests as
  `deck_id="legal-cards"` and always 404'd ("Deck not found") — reordered
  so `/decks/legal-cards` is registered first.
- New `server/scripts/migrate_update_deck_format_values.py` (idempotent
  one-off): updates existing `decks.format` rows from the old lowercase
  placeholder values to the new real ones (`'open'`->`'Open'`,
  `'standard'`->`'Standard'`, `'modern'`->`'Open'` as a safe default for a
  fictional value with no real equivalent). Run live: updated 32 existing
  rows (`'open'`->`'Open'`; zero rows used the other two old values).
- Godot client: `deck_builder.gd`/`api_client.gd` hardcoded the old
  lowercase `"open"` default when creating a deck — updated to the new
  capitalized `"Open"` (this would have broken deck creation with a
  Pydantic validation 422 otherwise, since the new `DeckFormat` enum is
  case-sensitive and no longer accepts lowercase values).

Verified via: (a) new unit tests in `test_deck_legality.py` covering
`is_format_legal`/`check_format_legality` (legal, illegal, X-listed,
no-formats-data-is-legal-everywhere cases) and `evaluate_deck_legality`'s
new `format_name`/`errata_notes` behavior — `pytest tests/ -q` went from
47 to 55 passing, zero regressions; (b) a live end-to-end HTTP smoke test
(temp script, deleted after use): ran the format-value migration, then
registered a user, seeded ownership of real cards with known
format/X-list data queried directly from the DB, created decks in
different real formats, and confirmed: a card only legal in "Fellowship
Block" is rejected (400, precise message) when added to a "King Block"
deck but accepted into an "Open" deck; a card that's X-listed for
"Standard" AND otherwise legal in "Standard" is rejected with the X-List-
specific message (had to pick a card where the X-listed format overlaps
its own `formats` list, since for most X-listed cards the plain
not-in-formats check fires first — both are correct rejections, just
different reasons); `GET /decks/legal-cards?format=King Block` correctly
excludes/includes cards per format (previously 404'd entirely due to the
routing bug above); `GET /decks/{id}/legality` exposes `errata_notes`
without it affecting `is_legal`. `get_errors` clean on all 5 touched
Python files (only pre-existing host-side sqlalchemy import-resolution
noise in `models.py`, unrelated to these changes). Both temp diagnostic/
smoke scripts deleted after use. `issues-tracker.md`'s LOT-014 entry
updated to reflect: format+X-List DONE, errata DONE (informational-only),
R-List explicitly still NOT implemented with the "no data source exists"
reasoning preserved.

## Live bug report: empty starter deck options / "0 cards granted" from boosters

User report: a new game showed no options on the "choose your starter deck"
screen, and opening 5 booster packs produced "Opened 5 pack(s), granted 0
cards!". Instructed to only fix if in-scope of an already-completed LOT
(LOT-018/LOT-025 here), otherwise leave alone and resume backlog work.

Investigation (all via live DB queries + live HTTP smoke tests against the
running `lotr-server` container, scripts deleted after use):
- Set 1 ("Fellowship") is active with full common/uncommon/rare/legendary/
  mythic catalog coverage; `server/server/data/starter_decks_set1.json`
  (3 curated decks) loads correctly into `STARTER_DECKS_BY_SET`. A clean
  fresh-registration repro (register -> login -> list entitlements -> list
  starter-deck-options -> claim all 5 boosters -> claim starter) succeeded
  perfectly end-to-end (3 deck options returned, 55 cards across 5 boosters,
  full starter deck granted) — so the core generation/claim logic itself has
  no bug.
- Root cause found by inspecting the actual reporting user's
  (`mithrandirmatt`) entitlement rows directly: they'd already fully
  consumed their Set-1 bundle back in August. Separately, during earlier
  LOT-025 release-bundle testing, Set 2 was briefly activated (admin panel),
  which auto-granted this account a Set-2 release bundle (1 starter_deck +
  5 booster_pack, `_grant_release_bundle_to_all_users`), then Set 2 was
  deactivated again — but `POST /admin/set-releases/{n}/deactivate` never
  touched those already-granted entitlement rows, leaving them permanently
  `status='active'` while referencing a set that's no longer active and has
  no curated starter decks.
  - `new_game.gd`'s `_find_starter_entitlement()` picks the most-recent
    starter_deck entitlement regardless of its set, so the screen tried to
    load deck options for Set 2 -> `STARTER_DECKS_BY_SET.get(2, {})` is
    empty -> header shows "Choose your starter deck:" with zero buttons
    (matches "does not have any options").
  - `_render_booster_section()` counts ALL active booster_pack entitlements
    regardless of set, found the 5 stale Set-2 ones -> `pack_count=5`, but
    each claim 400-rejects server-side (set not active) -> `_pending_
    booster_entitlements` loop's per-failure `_set_notice("Failed to open a
    pack: ...")` was unconditionally overwritten by the final `_set_notice(
    "Opened %d pack(s), granted %d cards!" ...)` line that always runs after
    the loop regardless of outcome -- silently hiding the real 400 errors
    and showing a misleading "success" message with 0 cards (exact literal
    match to the user's report).
- Confirmed in-scope: both LOT-018 (entitlement bundles) and LOT-025 (set
  release control) are marked DONE in `issues-tracker.md`; this is a real
  interaction bug between the two completed features, not an unimplemented
  gap -- fixed per the user's instruction.

Fix (3 changes):
1. `server/server/routes/api.py` — `admin_deactivate_set_release` now bulk-
   updates all `status='active'` entitlements for that `set_number` to
   `status='revoked'` (with `revoked_at`/`revocation_reason`) immediately
   after flipping `is_active=False`. Uses `revoked` (not a hard delete) so
   `_grant_release_bundle_to_all_users`'s "already granted" dedup check
   (which queries ANY entitlement row for that user+set, any status) still
   sees the row and skips re-granting on a later reactivation.
2. `gotdot/scripts/new_game.gd` — `_on_open_boosters_pressed()` now tracks
   `opened_count` vs `pack_count` and shows an accurate failure message
   (including the real server error) when fewer packs succeeded than were
   attempted, instead of always showing the success-shaped summary.
   `_load_deck_options()` now shows "No starter deck options are available
   for Set N yet." when the server legitimately returns zero items, instead
   of silently leaving a blank list under the "Choose your starter deck:"
   header.
3. `server/scripts/migrate_revoke_dangling_entitlements.py` (new, idempotent)
   — retroactively applies the same revocation to all pre-existing dangling
   active entitlements referencing inactive sets. Run live: revoked 156 rows
   (mostly LOT-025 test-account artifacts across many sets activated/
   deactivated during earlier testing), including `mithrandirmatt`'s 6 stuck
   Set-2 rows, which are now correctly `revoked`. No new cards were granted
   to compensate (the Set-1 bundle was already legitimately fully claimed by
   this account; Set 2 was never actually released).

Verification: full `pytest tests/ -q` still 55/55 passing (no regressions —
this area has no existing pytest route coverage, consistent with the
repo's live-smoke-test convention for DB-backed route behavior). Live smoke
test (`activate set 3 -> confirm 6 active entitlements -> deactivate ->
confirm all 6 now revoked -> claim a revoked entitlement returns 409 (not a
silent 0-card success) -> reactivate -> confirm still only 6 entitlement
rows total (no double-grant)`) passed every assertion; script deleted after
use, Set 3 left deactivated again (test hygiene). `issues-tracker.md`'s
LOT-018 acceptance criteria updated with a bugfix bullet documenting this.

## Slice 2 Summary: Booster Generation + Sell-Back

Implemented server-side card generation for `POST /store/purchase`
(product=pack only) and a new `POST /store/sell-back` endpoint, per LOT-020's
"every card delta has a transaction ID" / "foil status uniquely represented"
acceptance criteria and LOT-025's sell-back requirement.

Key design decisions (documented in code comments too):
- `Card.set_number` (new nullable column) filters the catalog to the
  requesting purchase's active set.
- `Card.rarity` enum extended with `'uncommon'` (previously only had
  common/rare/epic/legendary/mythic — no way to express the LOT-025 pack
  composition of 1 Rare/3 Uncommon/7 Common). Safe to add: the live DB has no
  CHECK constraint on this column (tables predate any `Base.metadata.create_all()`
  call, which is never invoked anywhere in this repo).
- `Ownership.is_foil` (new column) + unique index changed from
  `(card_id, user_id)` to `(card_id, user_id, is_foil)` so foil/non-foil
  copies are tracked as distinct rows. NOTE: the live DB actually had NO
  unique index on ownerships at all before this migration (only
  `ix_ownerships_user_id`) — the model's declared unique index was never
  applied, confirmed via direct sqlite inspection.
- New `DistributionTransaction` model/table: one row per purchase/sell-back
  event with a JSON `cards` delta list, optional `rng_seed`, `tolkien_delta`.
- `server/server/engine/booster.py` (new, pure/seedable): `RARITY_COMPOSITION`
  (1 rare/3 uncommon/7 common per pack), `FOIL_ODDS` (rare 1/26, uncommon
  1/18, common 1/13 — checked in that priority order, first hit wins, so
  "at most one foil per pack" is enforced; priority order is an
  implementation choice since the design doc doesn't specify precedence),
  `generate_booster_pack()`, `compute_sell_back_value_tolkiens()`.
- Sell-back value formula (own design decision, since the doc only says
  "normalized rarity-weighted expected pack value, then halved" with no
  numbers): split pack price evenly across rarity *tiers*, then evenly across
  cards of that tier, times a tunable `SELL_BACK_VALUE_SCALE_TOLKIENS = 30`
  scale knob (needed because native $1/pack pricing is too coarse to yield
  non-zero per-card fractions), times 0.5, rounded half-up. At the current
  pack price (1 Tolkien) this yields **common=1, uncommon=2, rare=5 Tolkien**
  sell-back — flagged to the user as a placeholder economy tuning knob to
  revisit during playtesting, not a value from the design doc.
- `starter_deck` purchases still only deduct Tolkien (old behavior,
  unchanged) — see Slice 3 below for `booster_box`, which now generates
  cards too.
- `StorePurchaseRequest.set_number` is optional (not required) so the
  existing `test_store_purchase_defaults_and_enum` test (no set_number)
  keeps passing; the route itself requires it (400) only when
  product=pack.

## Files Touched This Slice

Backend:
- `server/server/models/models.py` — `Card.set_number` column +
  `idx_card_set_number` index; `Card.rarity` enum gains `'uncommon'`;
  `Ownership.is_foil` column + `idx_ownership_card_user_foil` unique index
  (replacing `idx_ownership_card_user`); new `DistributionTransaction` model.
- `server/server/models/schemas.py` — `StorePurchaseRequest.set_number`
  (optional); new `GrantedCardSummary`; `StorePurchaseResponse.cards_granted`
  + `.transaction_id`; new `StoreSellBackRequest`/`StoreSellBackResponse`.
- `server/server/engine/booster.py` — new module (generation + valuation,
  pure/seedable, no DB access).
- `server/server/engine/__init__.py` — added `"booster"` to `__all__`.
- `server/server/routes/api.py` — imported `DistributionTransaction`,
  `booster` engine module, `StoreProduct`, new schemas; added `import random`;
  rewrote `/store/purchase` to generate+grant cards for product=pack
  (set-number validation against active `SetRelease`, catalog fetch by
  set_number+rarity, quantity-consolidated Ownership upsert, transaction
  record); added new `/store/sell-back` route.
- `server/scripts/migrate_add_booster_economy.py` — new idempotent
  migration: adds the two columns, recreates the ownerships unique index,
  creates `distribution_transactions`, and seeds a **placeholder** Set 1
  test catalog (12 cards: 7 common/3 uncommon/2 rare) only if `cards` was
  empty (it was — the real ~3,216-card catalog import is separate, larger,
  not-yet-started future work).
- `server/tests/test_booster_engine.py` — new: composition, missing-rarity
  ValueError, no-foil/forced-foil-priority-order, sell-back value/edge cases.
- `server/tests/test_store_economy_schemas.py` — new: schema
  defaults/optionality/round-trips for the new/changed schemas.

Verification done:
- `get_errors` clean on all changed/new Python files.
- `python3 -m pytest tests/ -q` inside `lotr-server` (run as
  `docker exec -w /workspace/server lotr-server ...`): **26 passed** (13 new).
- Ran the migration against the live dev DB (see gotcha below); confirmed via
  `docker logs lotr-server` the app reloaded cleanly after every edit (no
  import/startup errors).
- Live end-to-end smoke test (register -> login -> admin Tolkien grant ->
  `POST /store/purchase` product=pack set_number=1 -> `POST
  /store/sell-back`): purchase returned 11 cards (1 rare/3 uncommon/7
  common, some duplicate commons as expected from sampling-with-replacement);
  sell-back of the rare card returned 5 Tolkien and updated the balance
  correctly. Found and fixed a real bug during this smoke test (see below).
  Smoke-test script was temporary and has been deleted (not committed).

## Bugs Found & Fixed This Slice

- **Duplicate-card ownership insert crash (500)**: initial `/store/purchase`
  implementation looped over each individual generated card and did a
  query-then-insert-or-increment per card. Because `SessionLocal` is created
  with `autoflush=False` (`server/server/core/database.py`), a second
  occurrence of the same (card_id, is_foil) within one pack (very likely,
  since packs sample commons with replacement from a small pool) wasn't
  visible to the follow-up query, so it tried to INSERT the same
  `(card_id, user_id, is_foil)` twice and hit the new unique index ->
  `IntegrityError` -> 500. **Fixed** by first consolidating per-key
  quantities in a plain Python dict, then doing exactly one
  query-or-insert per unique (card_id, is_foil) with the summed delta.
- A related bug in the same fix pass: `cards_granted` (the per-card list
  returned to the client) was originally being appended inside the
  consolidation loop using a stale leftover loop variable, which would have
  produced fewer/wrong entries. Fixed by building `cards_granted` from the
  original per-card `generated_cards` list before consolidation.

## Gotcha: running one-off scripts against the live dev DB

`DATABASE_URL` defaults to `sqlite:///./lotr.db` (relative path). The actual
live DB file is at `/workspace/server/lotr.db`, but a plain
`docker exec lotr-server python3 scripts/foo.py` runs with cwd `/workspace`
(the container's default WORKDIR), which resolves `./lotr.db` to
`/workspace/lotr.db` -- a **different, silently-created-empty** file. This
happened during this slice (empty `/workspace/lotr.db` and a stray
`/workspace/users.db` were found and the former was deleted). **Always** run
one-off scripts with the working directory pinned to `server/`:
`docker exec -w /workspace/server lotr-server python3 scripts/<name>.py`.
(Saved to repo memory as well.)

## Decisions / Notes Carried Over From Slice 1

- Two competing economy model efforts exist in `server/server/models/`: the
  canonical, routes-wired `models.py` and a separate, NOT wired-in
  `models/economy/` package. Slice 2 continues to build on `models.py` only.
- No Alembic migrations exist anywhere in this repo; schema changes are
  raw-SQL one-off Python scripts under `server/scripts/`.
- The real ~3,216-card LotR TCG catalog (from
  `gotdot/assets/data/card_database.json`) had NOT been imported into the
  `cards` SQL table as of this slice — it was empty aside from this slice's
  12 placeholder test cards. Booster generation raised a 400 for any
  set/rarity combination with no catalog rows. **UPDATE (Slice 6, a later
  session): this has since been done** via
  `server/scripts/migrate_import_card_catalog.py`, which imports from
  `build/do/assets/database/card_database.json` (3,411 active cards as of
  the last live check).
- Remaining LOT-025 scope not yet started is tracked in **LOT-100**
  (`issues-tracker.md`) rather than duplicated here. Each item there should
  become its own follow-up slice with its own issues-todo.md checkpoint,
  and move to `issues-completed.md` when done.

## Slice 4: LOT-021 Baseline Economy/Circulation Telemetry

Added `GET /admin/economy/summary` (admin-only), giving visibility into the
current economy state built up by slices 2-3, per LOT-021's "Admin can
inspect current totals" acceptance criterion.

Returns:
- `circulation`: current owned quantity per card (split foil/non-foil),
  aggregated via a SQL `GROUP BY` join of `Ownership` + `Card` (no JSON
  parsing needed here — this is current state, not audit history).
- `foil_issuance_by_rarity`: total foil cards ever issued, by rarity.
- `distribution_by_source`: transaction count + total Tolkien delta per
  `DistributionTransaction.source` (purchase/sell_back/gift/starter/event/
  admin).
- `sell_back_by_rarity`: cards sold back + total Tolkien returned, by
  rarity.

**Scope deliberately left out of this slice** (moved to LOT-100, since they
depend on work not yet built):
- Historical trend snapshots and threshold/drift alerting (need a
  time-series storage/config decision — a separate design question).
- Weekly active-user reward telemetry and registration-timestamp coverage
  tracking (both depend on the LOT-018 entitlement/registration-timestamp
  work, which hasn't been built yet).

**Implementation note**: `distribution_by_source`/`foil_issuance_by_rarity`/
`sell_back_by_rarity` are aggregated by iterating `DistributionTransaction`
rows in Python (its `cards` column is JSON, and SQLite JSON aggregation
isn't worth the complexity at current dataset sizes). Flagged as a perf
follow-up (LOT-100) if the audit table grows large enough to matter.

Files touched: `server/server/models/schemas.py` (added `CirculationEntry`,
`DistributionSourceTotals`, `SellBackRarityTotals`, `EconomySummaryResponse`);
`server/server/routes/api.py` (added the route + schema imports);
`server/tests/test_economy_summary_schemas.py` (new, schema-level tests).

Verification: `get_errors` clean; `pytest tests/ -q` → **31 passed** (5 new);
live smoke test against the already-populated dev DB (from slices 2-3's
prior test purchases) confirmed correct aggregation — 12 unique cards
across 3 rarities, foil counts matching prior test data, 2 purchase
transactions (-26 Tolkien total) and 1 sell-back transaction (+5 Tolkien,
rare rarity) all correctly totaled. Temporary smoke script deleted after use.

## Slice 3: `booster_box` Card Generation

Extended `/store/purchase` so `product=booster_box` also generates and
grants cards server-side, reusing the exact same generation/consolidation/
transaction-recording logic as `product=pack` (just looped more times).

- **Design decision**: a booster box = **25 packs**. Not specified anywhere
  in the design docs. Inferred from the existing pricing baseline (booster
  box = 25 Tolkien, pack = 1 Tolkien, no bulk discount modeled) — i.e. box
  price already implies 25 packs 1:1. Documented in code as
  `BOOSTER_BOX_PACK_COUNT = 25` in `server/server/routes/api.py`, flagged
  as a placeholder tuning knob like the Slice 2 sell-back scale constant.
- `starter_deck` was deliberately NOT touched in this slice — unlike
  booster_box (mechanical: N more calls to the existing random-pack
  generator), a starter deck needs a curated, fixed, non-random decklist
  per set (real game-design content), which isn't something to fabricate.
  Moved to the LOT-100 backlog.
- Files touched: only `server/server/routes/api.py` (added
  `BOOSTER_BOX_PACK_COUNT` constant; changed the `if payload.product ==
  StoreProduct.PACK:` branch condition to `in (StoreProduct.PACK,
  StoreProduct.BOOSTER_BOX)` and added a `pack_count` multiplier).
- Verification: `get_errors` clean; `pytest tests/ -q` → 26 passed
  (unchanged — no new unit tests needed, this reuses Slice 2's already-
  tested generation code path); live end-to-end smoke test (temporary
  script, deleted after use) — purchased 1 booster box of Set 1, got
  exactly 275 granted cards (25 packs × 11) with rarity split 25
  rare/75 uncommon/175 common (exactly 25×1/25×3/25×7, as expected), balance
  correctly deducted 25→0, and a valid transaction_id was returned.

## Slice 5: LOT-019 Gift Ledger and Redemption Lifecycle

Added a `gifts` table + admin/user gift APIs so store products can be
gifted to a specific user and redeemed by them, per LOT-019's "gift ledger
and redemption lifecycle tracking" acceptance criteria.

**Lifecycle design decisions** (documented in `models.py::Gift` docstring
too):
- Full state set `created/granted/redeemed/consumed/expired/revoked` is
  kept in the `status` enum, but `created` and `granted` collapse into one
  step at creation time — admin-created gifts start directly in `granted`
  status, since there's no draft/scheduled-send workflow requested yet.
  `created` is reserved for that future use.
- `consumed` is reserved for a future multi-step fulfillment flow (e.g. a
  gift that grants an entitlement needing separate redemption). Today's
  pack/booster_box redemption is a single atomic step, so gifts go directly
  `granted` → `redeemed` (terminal success state used today).
- Only `pack`/`booster_box` gifts are redeemable right now — they reuse the
  exact same card-generation logic as `/store/purchase` (extracted into a
  shared `_generate_and_grant_packs()` helper in `api.py`). `starter_deck`/
  `promo_card` gifts raise HTTP 400 on redeem (content gap, tracked in
  LOT-100) — same reason `starter_deck` purchases don't generate cards yet.
- **Concurrency/idempotency**: redemption uses an atomic conditional
  `UPDATE gifts SET status='redeemed' ... WHERE id=:id AND status='granted'`
  (via SQLAlchemy Core `.update()` + rowcount check), not
  `SELECT ... FOR UPDATE` (not meaningfully supported by SQLite, and this
  compare-and-swap pattern works identically on Postgres). If zero rows are
  updated, someone already redeemed/revoked/expired it and we report a 409
  instead of double-granting cards.
- **Expiry**: optional `expires_at`, checked lazily on redeem attempt (no
  background sweep job) — if expired, the gift is atomically flipped to
  `expired` status and a 400 is returned. Background expiry sweeping is
  deferred to LOT-100 if ever needed.
- `Ownership.source` has no `'gift'` enum value (only
  purchase/trade/reward/event/admin), so gift-redemption Ownership rows use
  `source="reward"` — the actual `'gift'` provenance is recorded
  independently on the `DistributionTransaction` the redeem route creates
  (`source="gift"`), which is what LOT-020's "every card delta has a
  transaction ID" requirement actually needs.
- `AdminGiftCreateRequest.product` reuses the existing `StoreProduct` enum
  (pack/starter_deck/booster_box) — it has no `promo_card` value, so
  promo-card gifting isn't reachable yet either (also LOT-100, needs a
  promo-card catalog concept that doesn't exist).

**Routes added** (`server/server/routes/api.py`):
- `POST /admin/gifts` — admin issues a gift to a recipient (starts `granted`).
- `GET /gifts` — current user's own gift ledger (any status).
- `POST /gifts/{gift_id}/redeem` — recipient redeems their own gift.
- `POST /admin/gifts/{gift_id}/revoke` — admin cancels an un-redeemed gift.

**Files touched**: `server/server/models/models.py` (new `Gift` model +
`idx_gift_recipient`/`idx_gift_recipient_status` indexes);
`server/server/models/schemas.py` (new `GiftStatus`, `AdminGiftCreateRequest`,
`GiftSummary`, `GiftListResponse`, `GiftRedeemResponse`);
`server/server/routes/api.py` (new `_generate_and_grant_packs()` helper
extracted from `/store/purchase` and reused by `/gifts/{id}/redeem`; 4 new
routes); `server/scripts/migrate_add_gifts.py` (new, idempotent `gifts`
table migration); `server/tests/test_gift_schemas.py` (new, 5 schema tests).

**Bug found & fixed this slice**: `admin_create_gift` initially didn't set
`created_at` explicitly, relying on the `Gift` model's `server_default=
func.now()` — but since the `gifts` table was created via a raw-SQL
migration script (not `Base.metadata.create_all()`), the actual column had
no DB-level default, so newly-inserted rows got `created_at=NULL`, which
then failed `GiftSummary` pydantic validation (`created_at` is required) on
both the create-gift response and any later `GET /gifts` list containing
that row. Fixed by explicitly setting `created_at=datetime.utcnow()` in the
route (also added `DEFAULT CURRENT_TIMESTAMP` to the migration SQL for new
installs, though the already-created live table wasn't retroactively
altered since the app-level fix makes that unnecessary). Two orphaned NULL-
`created_at` gift rows created during debugging were deleted from the dev
DB via a temporary cleanup script (deleted after use).

**Verification**: `get_errors` clean; `pytest tests/ -q` → **36 passed** (5
new); live end-to-end smoke test (temporary script, deleted after use, plus
a temporary cleanup script also deleted after use) against the live dev
server confirmed: admin-created gift starts `granted`; recipient's `GET
/gifts` lists it; redeem grants exactly 11 cards (1 pack) and records a
`DistributionTransaction(source='gift')`, transitioning status to
`redeemed`; a second redeem attempt on the same gift correctly returns 409
(idempotency guard verified); a separately-created, never-redeemed gift is
successfully revoked by admin (200, status→`revoked`) and a subsequent
redeem attempt on it correctly returns 409; a `starter_deck` gift correctly
returns 400 on redeem attempt (content-gap block verified).

