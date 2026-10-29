# LotR TCG Project — Issue Tracker

## Issue Tracking

Note, update this file with issues that are active, pending, complete, or new.

## Issues:

### New:

- **LOT-6.5** — Fix issues found in comprehensive review of LOT-001 through LOT-006 (2026-07-23).
  - Review verdicts: LOT-005 and LOT-006 accurately completed; LOT-001, LOT-003, LOT-004 partially complete; LOT-002 falsely marked complete.
  - **Critical (fix first)**:
    - `SECRET_KEY = secrets.token_urlsafe(32)` in `server/server/routes/api.py` is regenerated on every server restart, invalidating all issued JWTs. Must load from env var/config instead.
    - Anti-cheat is non-functional (LOT-002 goal not met): `validate_deck()` in `server/server/engine/validator.py` has no real logic (always valid); `apply_action()` in `server/server/engine/core.py` is a placeholder that only increments the turn counter; `join_match()` never verifies the joining player's deck cards are owned by them; match audit "integrity score" is fabricated, not derived from real analysis.
  - **Data accuracy**:
    - `gotdot/assets/data/game_logic_database.json` contains only ~200 parsed cards, not the claimed 3,216 (LOT-001). Either re-run `scripts/generate_game_logic.py` against the full card database or correct the tracked count.
  - **Missing functionality**:
    - No endpoint exists to grant/revoke `is_admin` status (LOT-003) — only `is_moderator` toggle exists via `PUT /admin/users/{id}/moderator`.
  - **Security hardening**:
    - Default local-admin shortcut password `"yourmommalooksfunny"` is hardcoded as a source fallback in `api.py`; `ENABLE_LOCAL_ADMIN_SHORTCUT` defaults to enabled (`"1"`). Should require explicit opt-in with no source-code default.
    - No password complexity rules beyond 8-char minimum; 24h access token lifetime is long; `is_verified=True` is set on register with no real email verification flow.
  - Full findings saved in repo memory: `/memories/repo/issues-lot001-006-review.md`.

- **LOT-008** - Add AI play.
  - This will allow users to play against an AI opponent locally.
  - The AI should follow the same rules user selects.
  - We should make the AI difficulty adjustable, so users can choose to play against an easier or harder opponent.
    - Decks should be built for each difficulty level, and the AI should use the appropriate deck based on the selected difficulty.
    - Need to classify cards in the database by difficulty level, so we can build appropriate decks for the AI.
  - The AI should be able to make legal moves and should be able to win or lose based on the game state.
  - AI should use the same game logic as the online play, so we can ensure consistency between local and online play.

- **LOT-008.5** — Recapture LOT-003 admin login failure in admin panel.
	- **Type**: bug/auth-integration
	- **Priority**: 1
	- **Problem statement**:
		- `lotradmin:yourmommalooksfunny` login behavior is inconsistent and blocks admin access.
		- Auth contract differs between frontend expectations and backend runtime behavior.
	- **Implementation details**:
		- Standardize canonical auth path and credential handling for local-admin shortcut and normal admin login.
		- Align register/login payload contracts and restore missing availability-check endpoints or adjust frontend usage.
		- Add integration tests for local vs non-local shortcut behavior and admin-only gate checks.
	- **Acceptance criteria**:
		- Admin login works deterministically in intended local-dev scenario.
		- Non-admin users are denied admin panel access with clear message.
		- Auth behavior is documented and covered by tests.

- **LOT-009** — Canonical rules engine core (deterministic state + invariants).
	- **Type**: feature/game-engine
	- **Priority**: 1
	- **Problem statement**:
		- Core game state model is not yet formalized for deterministic rules execution.
	- **Implementation details**:
		- Define normalized state schema: players, board zones, piles, burdens/wounds, twilight, and phase cursor.
		- Add event journal and state-hash checkpoints for replay/debug.
		- Add invariant validators after every state mutation.
	- **Acceptance criteria**:
		- Engine initializes legal match state from validated inputs.
		- Invariant violations are detected and surfaced with actionable diagnostics.
		- State replay reproduces identical state hashes.

- **LOT-010** — Turn and phase state machine (Fellowship to Regroup).
	- **Type**: feature/game-engine
	- **Priority**: 1
	- **Problem statement**:
		- Turn/phase progression must match rules timing and skip behavior exactly.
	- **Implementation details**:
		- Implement deterministic phase transitions and pass-priority loops.
		- Add skip logic for no-minion branches and move-again loop constraints.
		- Support v4.2/v5 timing differences via configurable rules flags.
	- **Acceptance criteria**:
		- Full turn cycle executes correctly under scripted scenarios.
		- Illegal phase actions are rejected with stable error codes.

- **LOT-011** — Action legality and cost-payment engine.
	- **Type**: feature/rules-enforcement
	- **Priority**: 1
	- **Problem statement**:
		- Actions need a unified legality checker and atomic cost resolution.
	- **Implementation details**:
		- Validate timing windows, conditions, targets, and costs in one legality path.
		- Implement costs: exert, burden, discard, twilight pay, and spot checks.
		- Enforce "cannot overrides can" precedence.
	- **Acceptance criteria**:
		- Action attempts return deterministic legal/illegal outcomes and reasons.
		- Failed actions leave no partial state mutation.

- **LOT-012** — Combat resolution (archery, skirmish, overwhelm, fierce).
	- **Type**: feature/combat
	- **Priority**: 1
	- **Problem statement**:
		- Combat stack needs complete implementation for core gameplay.
	- **Implementation details**:
		- Implement archery totals and wound assignment order.
		- Implement skirmish resolution, tie handling, damage bonuses, and overwhelm.
		- Implement fierce second-round behavior and edge cases.
	- **Acceptance criteria**:
		- Combat outcomes match rules fixtures and deterministic snapshots.
		- Edge cases are test-covered and reproducible.

- **LOT-013** — Runtime card-text execution from `game_logic_database.json`.
	- **Type**: feature/card-text-engine
	- **Priority**: 1
	- **Problem statement**:
		- Parsed card logic must execute in runtime without hand-coded drift.
	- **Implementation details**:
		- Build interpreter for triggers, costs, conditions, effects, and targets.
		- Add ambiguity guardrails and manual override hooks.
		- Add parser-diff regression checks against approved baselines.
	- **Acceptance criteria**:
		- High-confidence parsed cards execute correctly in runtime tests.
		- Ambiguous actions are blocked or routed to explicit fallback handling.

- **LOT-014** — Deck legality and format enforcement service.
	- **Type**: feature/deck-validation
	- **Priority**: 1
	- **Problem statement**:
		- Decks must be validated consistently across client and server.
	- **Implementation details**:
		- ~~Enforce deck size, FP/Shadow split, site rules, uniqueness/copy limits.~~ —
		  **DONE**: `server/server/services/deck_legality.py`'s
		  `evaluate_deck_legality()` (draw-deck size >=60, equal FP/Shadow split,
		  9-site adventure deck) and `check_copy_limit()` (max 4 copies per card
		  title ignoring subtitle, max 1 copy per site), wired into
		  `GET /decks/{deck_id}/legality` and `POST /decks/{deck_id}/cards`
		  respectively. Unit tested in `server/tests/test_deck_legality.py`;
		  verified live end-to-end this session (build a 60-card deck
		  incrementally via the real add-card route, confirm legality
		  transitions correctly, confirm 5th-copy and 2nd-site-copy requests are
		  rejected with precise messages).
		- Enforce format + X-list/R-list/errata constraints. —
		  **PARTIALLY DONE**: format + X-List enforcement is implemented using the
		  real scraped tournament data already imported into `Card.attributes`
		  (`formats`, `on_xlist`, `has_errata` -- see
		  `build/py/wiki/create_card_database.py`/`create_xlist_databases.py` and
		  `server/scripts/migrate_import_card_catalog.py`). `Deck.format`/`DeckFormat`
		  now use the real tournament format names (`Fellowship Block`, `Tower Block`,
		  `King Block`, `Expanded`, `Standard`, `Open`) instead of the old fictional
		  placeholders (`standard`/`modern`/`open`). `deck_legality.is_format_legal()`/
		  `check_format_legality()` reject cards not legal in (or X-listed for) a
		  deck's format, wired into `POST /decks/{deck_id}/cards` and
		  `GET /decks/legal-cards` (which previously validated the format string but
		  never actually filtered -- now fixed). Errata is surfaced as
		  informational-only `errata_notes` on `GET /decks/{deck_id}/legality` (never
		  blocks legality, since there's no card-text engine (LOT-013) to apply
		  corrected text). R-List remains **NOT implemented** -- genuine, permanent
		  documented gap: no R-List data has been scraped anywhere in this repo (see
		  `build/py/wiki/create_xlist_databases.py`, which only builds X-List +
		  errata databases); fabricating one would mean inventing which cards are
		  restricted, which was intentionally avoided. Also fixed a pre-existing
		  FastAPI route-ordering bug where `/decks/{deck_id}` (registered first)
		  swallowed `/decks/legal-cards` requests as `deck_id="legal-cards"`, always
		  404ing; `/decks/legal-cards` is now registered first. A one-off migration
		  (`server/scripts/migrate_update_deck_format_values.py`) updated existing
		  `decks.format` values from `'open'`→`'Open'` (32 rows). Unit tested
		  (`test_deck_legality.py`: `is_format_legal`/`check_format_legality`/format+
		  errata integration in `evaluate_deck_legality`) and verified live
		  end-to-end (register user, seed ownership of real cards with known
		  format/X-list data, confirm format-illegal and X-listed cards are rejected
		  with precise messages, confirm `GET /decks/legal-cards` filters correctly
		  per format, confirm `errata_notes` surfaces without affecting `is_legal`).
		  Godot client (`gotdot/scripts/deck_builder.gd`/`api_client.gd`) updated to
		  send the new capitalized `"Open"` default instead of the old `"open"`.
		- Return structured violations suitable for UI display. — **DONE** via
		  `DeckLegalityResponse` (`is_legal`, `issues: List[str]`, counts).
	- **Acceptance criteria**:
		- Illegal decks fail with precise per-rule diagnostics. — met for the
		  implemented rules (size/split/site-count/copy-limit/format/X-List); R-List
		  remains not applicable since no R-List data exists anywhere to enforce.
		- Legal deck validation is deterministic and shared across consumers —
		  **DONE**: both the `GET /decks/{id}/legality` diagnostics endpoint and
		  the `POST /decks/{id}/cards` add-card route call the same
		  `deck_legality` service functions.

- **LOT-015** — Server-authoritative match protocol and replay audit trail.
	- **Type**: feature/server-infrastructure
	- **Priority**: 1
	- **Problem statement**:
		- Match integrity requires server authority for all game actions.
	- **Implementation details**:
		- Define command protocol with expected state hash and actor context.
		- Validate all commands server-side and broadcast signed deltas.
		- Persist auditable event log for deterministic replay.
	- **Acceptance criteria**:
		- Clients cannot commit illegal transitions.
		- Replays reconstruct final state exactly from recorded events.

- **LOT-016** — Rules regression suite and golden scenarios.
	- **Type**: testing/verification
	- **Priority**: 1
	- **Problem statement**:
		- Rules changes need protection from regressions.
	- **Implementation details**:
		- Build scenario fixtures for turn flow, corruption, overwhelm, fierce, and move limits.
		- Add golden snapshot tests and CI gate.
		- Provide fast smoke + full-suite commands.
	- **Acceptance criteria**:
		- Core rules fixtures pass in CI.
		- Regressions fail with localized diff output.

- **LOT-017** — Set-release schedule and active-set gating (Fellowship-only launch).
	- **Type**: feature/content-release
	- **Priority**: 1
	- **Program linkage**:
		- Backend policy and admin-control foundation for LOT-025. The monthly set availability UI/flow is implemented as part of LOT-025 execution, while this issue remains the canonical source for activation rules and hard constraints.
	- **Problem statement**:
		- Launch must expose only Fellowship, with controlled monthly set activation.
	- **Implementation details**:
		- Add release schedule model with activation status and timestamps.
		- Enforce active-set checks in listing, purchase, and redemption endpoints.
		- Add admin release activation API with idempotency.
		- Add an admin panel "Set Releases" page: a simple list of every set, each with an enable/disable checkbox that calls the activation API directly (no separate save step). The launch set (Fellowship) is hardcoded as always-active — its checkbox renders disabled/read-only client-side, and the activation endpoint independently rejects any attempt to deactivate it server-side, regardless of caller.
	- **Acceptance criteria**:
		- Fellowship-only behavior is enforced at launch.
		- Inactive sets cannot be purchased/redeemed.
		- Release activation is auditable.
		- Admins can toggle any non-launch set's availability from a checkbox list in the admin panel; the launch set's checkbox cannot be unchecked in the UI, and a direct API call attempting to deactivate it is rejected.

- **LOT-018** — New-user and set-unlock entitlement bundles (1 starter deck + 5 booster packs).
	- **Type**: feature/onboarding-economy
	- **Priority**: 1
	- **Program linkage**:
		- Entitlement definitions and redemption policy are executed as supporting scope inside LOT-025 delivery (still tracked here as the canonical entitlement-policy record).
	- **Problem statement**:
		- New users need deterministic starter grants controlled by server entitlements.
	- **Implementation details**:
		- Add entitlement model and one-time bootstrap grant workflow.
		- Persist a canonical user registration timestamp at account creation time; this timestamp is the anchor for weekly reward windows used by LOT-025.
		- Backfill guardrail: if a legacy user is missing registration timestamp data, populate it on the next successful login before reward-eligibility evaluation.
		- New account baseline rewards: 1 starter deck (chosen from set 1 only) and 5 booster packs (chosen from set 1 only).
		- On every newly unlocked set release, grant the same release gift bundle for that set: 1 starter deck from that set + 5 booster packs from that set.
		- Add entitlement types/state to represent both account-bootstrap bundles and per-release bundles, with idempotent per-user, per-set grant guards.
		- Gate redemption by active set and starter availability.
	- **Acceptance criteria**:
		- Registration timestamp is always captured for newly registered accounts and is available for weekly reward eligibility logic.
		- Legacy accounts missing registration timestamp are backfilled on successful login before any weekly reward checks are run.
		- Every new account receives the exact set-1 bundle once: 1 starter deck + 5 booster packs.
		- On each set activation, each eligible user receives exactly one release bundle for that set: 1 starter deck + 5 booster packs.
		- Entitlement consumption is tracked and idempotent.
		- ~~Bugfix (live report)~~ — **DONE**: deactivating a set now revokes any still-unclaimed ("active") entitlements for that set (`POST /admin/set-releases/{set_number}/deactivate` in `server/server/routes/api.py`), so a player who was granted a release bundle for a set that's later deactivated (before they claimed it) isn't left in a stuck state: the "choose your starter deck" screen was showing a blank options list (no curated decks exist for an unreleased set) and booster-pack claims were 400-rejecting (set not active) with the failure silently masked by `new_game.gd`'s unconditional "Opened N pack(s)!" success message. Also fixed client-side: `new_game.gd`'s `_on_open_boosters_pressed()` now reports actual failures instead of overwriting them, and `_load_deck_options()` shows a clear "no options available for Set N yet" status instead of a blank list. A new idempotent migration (`server/scripts/migrate_revoke_dangling_entitlements.py`) retroactively revoked 156 pre-existing dangling entitlements (mostly LOT-025 release-bundle test data, including the real reporting account's stuck Set-2 grant from earlier manual admin-panel testing). Revoking (not deleting) preserves `_grant_release_bundle_to_all_users`'s idempotency guard, so a later reactivation still won't double-grant (verified live).

- **LOT-019** — Gift ledger and redemption lifecycle tracking.
	- **Type**: feature/gifting
	- **Priority**: 1
	- **Program linkage**:
		- Gift lifecycle and redemption states are executed as supporting scope inside LOT-025 delivery, including booster pack, booster box, starter deck, and promo-card prize redemption surfaces.
	- **Problem statement**:
		- Gifts need a reliable lifecycle to prevent double spend and audit gaps.
	- **Implementation details**:
		- Implement states: created, granted, redeemed, consumed, expired, revoked.
		- Add transaction locks and idempotent state transitions.
		- Expose user gift list/redeem APIs with audit linkage.
	- **Acceptance criteria**:
		- Gift transitions are valid and irreversible where required.
		- Concurrent redemption attempts cannot double-consume gifts.

- **LOT-020** — Unified server-authoritative distribution transaction pipeline.
	- **Type**: feature/inventory-integrity
	- **Priority**: 1
	- **Program linkage**:
		- Canonical issuance/sale transaction engine is executed as supporting scope inside LOT-025 delivery for purchases, redemptions, promo prizes, and sell-back flows.
	- **Problem statement**:
		- Card issuance paths are fragmented and need one source of truth.
	- **Implementation details**:
		- Add distribution transaction records with source metadata and RNG seed support.
		- Route purchase/gift/starter/event issuance through one service.
		- Pricing baseline for LOT-025 storefront operations: starter deck = 5 Tolkien, booster pack = 1 Tolkien, booster box = 25 Tolkien.
		- Sell-back value policy: always 50% of purchase price equivalent. Card-level sell-back values should be derived from normalized rarity-weighted expected pack value, then halved.
		- Card generation is server-side only: gift unlocks, pack openings, and prize grants all generate cards on the server (no client-authored card outcomes).
		- Starter deck generation is deterministic/fixed per set definition.
		- Booster generation baseline (set-overridable later): 11 cards per pack with rarity composition 1 Rare, 3 Uncommon, 7 Common.
		- Add foil flag/variant tracking on owned card instances so foil and non-foil are uniquely tracked even before visual differentiation is implemented.
		- Foil insertion baseline probabilities per opened booster pack (set-overridable later): Common foil 1/13 packs, Uncommon foil 1/18 packs, Rare foil 1/26 packs; enforce at most one foil insertion event per pack.
		- Persist per-user ownership and issuance records sufficient for non-trading economy operations (purchase, gift, prize, sell-back, collection, deck construction).
		- Apply inventory and history updates atomically.
	- **Acceptance criteria**:
		- Every card delta has a transaction ID.
		- All pack/starter/prize card outcomes are generated and auditable server-side.
		- Foil status is uniquely represented and queryable per owned card instance.
		- Rollback behavior is correct on partial failures.

- **LOT-021** — Circulation metrics and balancing telemetry.
	- **Type**: feature/economy-observability
	- **Priority**: 1
	- **Program linkage**:
		- Economy telemetry is executed as supporting scope inside LOT-025 delivery for pricing/balance tuning, set release balancing, foil cadence, and sell-back impact analysis.
	- **Note**:
		- Account-closure reclaim remains future scope.
	- **Problem statement**:
		- Circulation balance cannot be managed without metrics.
	- **Implementation details**:
		- Aggregate circulation by set, rarity, and card ID.
		- Add admin summary endpoint and threshold alerts.
		- Add foil issuance telemetry by rarity/source (booster foil rolls, event prizes, weekly active random rewards).
		- Track weekly active eligibility (logged in at least once in the week), weekly random foil reward trigger rate, and non-stacking enforcement metrics (max 1 reward/week/user).
		- Track registration-timestamp coverage and login-time backfill events for legacy users to ensure weekly reward window anchoring quality.
		- Track sell-back economy metrics by rarity/value-band (total sell-back volume, Tolkien returned, and net circulation impact).
		- Build trend snapshots for release-window monitoring.
	- **Acceptance criteria**:
		- Admin can inspect current totals and trends.
		- Drift alerts trigger on configured thresholds.

- **LOT-022** — Monthly release events and participation schema foundation.
	- **Type**: feature/events
	- **Priority**: 2
	- **Program linkage**:
		- Event definitions and participation records are executed as supporting scope inside LOT-025 delivery, providing the awarding pathway for promo-card prizes and monthly release operations.
	- **Problem statement**:
		- Monthly releases require structured event records and participant tracking.
	- **Implementation details**:
		- Add release event and participation entities.
		- Add scheduled/live/closed status model and API operations.
		- Keep reward policy pluggable for future detail work.
	- **Acceptance criteria**:
		- Set activations are linked to event records.
		- Participation records are queryable and auditable.

- **LOT-023** — Multiplayer lobby, ready-check, and bootstrap.
	- **Type**: feature/multiplayer
	- **Priority**: 2
	- **Problem statement**:
		- Multiplayer requires a deterministic pre-match orchestration layer.
	- **Implementation details**:
		- Build room model, invites, seating, and host controls.
		- Add ready-check flow and pre-match legality validation.
		- Produce deterministic match seed and bootstrap state.
	- **Acceptance criteria**:
		- Players can create/join/start matches with validated setup.
		- Invalid setup fails safely with actionable messages.

- **LOT-024** — Reconnect, pause, and continuity controls.
	- **Type**: feature/multiplayer-resilience
	- **Priority**: 2
	- **Problem statement**:
		- Disconnects must not corrupt match state.
	- **Implementation details**:
		- Add reconnect tokens and resume handshake.
		- Add grace timers and pause policy for non-ranked modes.
		- Verify resumed state hash before continuing turns.
	- **Acceptance criteria**:
		- Reconnect restores exact authoritative match context.
		- Timeout outcomes are deterministic and logged.

- **LOT-025** — Unified player economy, release control, and deck builder experience.
	- **Type**: feature/godot-economy-release-deckbuilder
	- **Priority**: 1
	- **Note**:
		- This is now the primary consolidation issue for release scheduling operations, Tolkien economy surfaces, gifting/prizing, sell-back strategy, store UX, and deck-building UX. Related LOTs remain as domain foundations but execution sequencing and user-facing integration are coordinated here.
		- Live legality diagnostics are still split into LOT-032; LOT-025 defines how legality/rules controls are presented and selected in the builder UX.
		- Supporting dependency work from LOT-017/018/019/020/021/022 is to be worked as part of LOT-025 execution, with those LOTs serving as canonical policy/engine records.
	- **Problem statement**:
		- The game needs one cohesive player/admin experience spanning: manual monthly set release control, store purchases and rewards, currency movement, and a high-clarity deck-building workflow. These areas are interdependent and should be delivered as one coordinated program, not fragmented features.
	- **Release schedule and admin control**:
		- Monthly release activation is manual for now (no automation): admins explicitly enable/disable set availability using checkbox controls in the admin panel.
		- Admin panel needs a dedicated Set Releases area listing each set with availability checkboxes.
		- Fellowship (set 1) is permanently available and hardcoded as non-disableable in both UI and API guardrails.
	- **Economy and store scope**:
		- Tolkien is the primary currency for store operations and should be surfaced clearly in all store actions.
		- Tolkien economy is in-game only for now (no real-money checkout flow in current scope), but pricing/data models should remain monetization-ready for future activation.
		- Store price points (current baseline): starter deck = 5 Tolkien, booster pack = 1 Tolkien, booster box = 25 Tolkien.
		- Store supports product types: booster packs, booster boxes, and starter decks. Promo cards are prize-only for now (random rewards or event prizes), not direct store purchases.
		- Gifts and entitlement claims are handled in the same store surface so claim/spend happens in one place.
		- New account reward bundle: 1 starter deck (from set 1) + 5 booster packs (from set 1).
		- On each set unlock, grant each eligible user the same release bundle for that set: 1 starter deck + 5 booster packs from that set.
		- Card outcomes for gift unlock/opening are server generated: starter decks fixed per set; boosters generated by rarity policy.
		- Booster baseline policy (set-overridable later): 11 cards, composed as 1 Rare, 3 Uncommon, 7 Common.
		- Foil tracking baseline: foil and non-foil must be uniquely marked/tracked in ownership data; no visual distinction required yet.
		- Foil odds baseline (set-overridable later): Common foil 1/13 packs, Uncommon foil 1/18 packs, Rare foil 1/26 packs, with at most one foil insertion event per pack.
		- Weekly active-user random foil reward: active week = user logged in at least once during that week. Weekly windows are anchored to persisted user registration timestamp. Eligible users have a low-probability random reward roll; reward is non-stacking and capped at 1 foil reward per user per week; foil rarity can be Common, Uncommon, or Rare.
		- Add sell-back pathway as preferred alternative to player trading for now: players can sell excess cards back to the store for Tolkien at a fixed 50% value policy relative to purchase-equivalent card valuation.
	- **Card creation and catalog management touchpoint**:
		- Include card-creation/admin catalog hooks in the consolidated plan so new cards and promo variants can be introduced safely into release/store/deck flows.
		- *(Open — add card-authoring workflow details here: review gates, publish states, rarity/economy constraints, and release linking.)*
	- **Deck builder layout and interaction requirements**:
		- Primary card browser uses a binder metaphor: 9x9 grid per page, two-page spread (9x9 x 2), with page-flip navigation.
		- Deck-building workspace is split-screen:
			- Left side: deck summary by unique card entry (show count per card, do not render duplicate tiles for multiples).
			- Left side deck grid layout: 4 columns by N rows (auto-expand rows as needed).
			- Top tabs on deck pane: Deck Cards, Sites, Starting Fellowship.
			- Each tab filters to only that card category; totals still count per game rules.
			- Right side: card browser binder plus a collapsible control panel.
		- Deck count limit: maximum 25 saved decks per user.
		- Card copy limits are enforced by game rules profiles (LOT-014/LOT-032), not hardcoded in LOT-025.
	- **Deck builder control panel (right side, collapsible sections)**:
		- Filters section:
			- Include grouped filters for culture, companion, ally, burdens, signet, event, condition, weapon, possession, and other card facets.
			- Numeric/range-capable filters (example: burdens min/max fields).
		- Sets section:
			- Checkmark list for set inclusion (short code plus number, example: FOTR (1)).
		- Rules section:
			- Checkbox controls for compliance targets.
			- Tournament/block rulesets are mutually exclusive: when tournament mode is enabled, only one tournament ruleset can be selected and cannot be combined with others.
	- **Implementation details**:
		- Integrate release availability from LOT-017 into both admin controls and player storefront visibility.
		- Route all purchase/redeem/sell-back/prize flows through LOT-020 transaction pipeline.
		- Bind entitlement and gift-state behavior from LOT-018 and LOT-019 into store actions.
		- Use LOT-021 metrics to monitor economy impact of release toggles, pricing, and sell-back.
		- Use LOT-022 event plumbing for promo-card prize awarding scenarios.
		- Ensure release-bundle grants are idempotent and set-scoped (no duplicate grants per user per set unlock event).
		- Registration timestamp requirement for weekly rewards: write timestamp on registration; if missing for legacy users, backfill it on successful login before weekly reward eligibility is computed.
		- Keep terminology normalized to "starter deck" for the granted fixed deck product.
		- Keep deck legality diagnostics delegated to LOT-032 + LOT-014 service, but wire builder controls so users can target desired compliance modes.
	- **Acceptance criteria**:
		- Admin can manually control monthly set availability via checkbox list; Fellowship remains always-on and cannot be disabled.
		- Store only exposes active-set products and supports purchase, entitlement/gift claim, promo prize delivery, and sell-back for Tolkien with auditable transactions.
		- Store pricing baseline is implemented as starter deck 5T, booster pack 1T, booster box 25T.
		- Sell-back always resolves to 50% of purchase-equivalent card value, with deterministic rounding behavior documented and applied consistently.
		- Account bootstrap and per-set unlock rewards are granted exactly once per user per scope (bootstrap or set), with server-side card generation and full audit records.
		- Booster and foil outcomes follow configured policy and are ownership-traceable per user.
		- Weekly active random foil reward is non-stacking and never exceeds 1 reward per user per week.
		- Weekly reward windows are consistently computed from persisted registration timestamp; missing legacy timestamps are auto-backfilled on login before reward checks.
		- Deck builder ships with required binder + split-screen layout, tabbed deck categories, and collapsible filter/set/rules controls.
		- Deck creation enforces maximum 25 decks per user.
		- Ruleset selection behavior enforces mutually exclusive tournament-mode selection.
		- Decks can be built, saved, loaded, and passed to legality checks (LOT-032) with user-visible compliance targeting.
	- **Related issues (consolidated under LOT-025 execution)**:
		- Supporting dependencies to be worked as part of this LOT: LOT-017, LOT-018, LOT-019, LOT-020, LOT-021, LOT-022.
		- Legality diagnostics split: LOT-032 (depends on LOT-014).
		- Deck legality service foundation: LOT-014.

- **LOT-026** — Godot gameplay scene architecture and interaction model.
	- **Type**: feature/godot-client
	- **Priority**: 2
	- **Problem statement**:
		- Game client scene model must support full authoritative gameplay loop.
	- **Implementation details**:
		- Build board zones, intent dispatch, and phase-aware UX cues.
		- Add deterministic animation queue that does not own state.
		- Implement snapshot reconciliation on reconnect.
	- **Acceptance criteria**:
		- Full turn loop is playable in Godot against authoritative backend.
		- UI remains synchronized after reconnect and state replay.

- **LOT-027** — AI opponent baseline using shared legality engine.
	- **Type**: feature/ai-gameplay
	- **Priority**: 2
	- **Problem statement**:
		- AI must use the same legal move surface as human players.
	- **Implementation details**:
		- Build legal move generator adapters and baseline heuristics by phase.
		- Add selectable difficulty policy constraints.
		- Integrate with authoritative command protocol.
	- **Acceptance criteria**:
		- AI can complete games without illegal actions.
		- Difficulty settings produce measurable behavior differences.

- **LOT-028** — Match history and replay viewer.
	- **Type**: feature/observability-gameplay
	- **Priority**: 2
	- **Problem statement**:
		- QA and users need deterministic replay and post-match inspection.
	- **Implementation details**:
		- Persist event logs with periodic checkpoints.
		- Build replay viewer with phase/action stepping and state diffs.
		- Add export format for regression bug reports.
	- **Acceptance criteria**:
		- Completed matches replay deterministically.
		- Replays can be exported and attached to issue workflows.

- **LOT-029** — Ranked matchmaking and ratings.
	- **Type**: feature/matchmaking
	- **Priority**: 3
	- **Problem statement**:
		- Ranked play needs fair queueing and auditable rating changes.
	- **Implementation details**:
		- Add format-aware queues and rating lifecycle.
		- Add abandon/dodge policy and anti-smurf heuristics.
		- Add season reset and placement logic.
	- **Acceptance criteria**:
		- Match quality and rating updates meet configured fairness thresholds.

- **LOT-030** — Accessibility and input-system hardening.
	- **Type**: feature/ux-accessibility
	- **Priority**: 3
	- **Problem statement**:
		- Core flows must be accessible beyond mouse-only interaction.
	- **Implementation details**:
		- Add scalable text, contrast presets, and colorblind-safe palettes.
		- Add keyboard/controller navigation maps.
		- Add confirmation UX for high-impact actions.
	- **Acceptance criteria**:
		- Core features are operable with keyboard/controller only.
		- Accessibility QA passes defined baseline checks.

- **LOT-031** — Performance budget and profiling harness.
	- **Type**: feature/performance
	- **Priority**: 3
	- **Problem statement**:
		- Performance regressions must be caught before release.
	- **Implementation details**:
		- Define frame/load/memory budgets for target platforms.
		- Add automated profiling scenarios for key flows.
		- Add regression alarms for spikes and leaks.
	- **Acceptance criteria**:
		- Client meets baseline budgets on agreed test hardware.
		- Performance regressions fail CI checks.

- **LOT-032** — Godot deck-builder legality diagnostics.
	- **Type**: feature/godot-deckbuilder-legality
	- **Priority**: 2
	- **Note**:
		- Split out of the original LOT-025 ("Godot deck builder UX and legality guidance") so live-legality UI work can proceed independently of the Store/Deck Building consolidation happening in LOT-025.
	- **Problem statement**:
		- Deck-building UX must surface legality and collection constraints in real time as a deck is edited, not just pass/fail at save time.
	- **Implementation details**:
		- Integrate live legality diagnostics from the deck validation service (LOT-014) into the deck builder UI, re-checked incrementally as cards are added or removed.
		- Surface violations inline with which rule failed, on which card, and why — not just a generic invalid-deck message.
		- Debounce/re-check on every edit without blocking the UI thread.
	- **Acceptance criteria**:
		- Violations show precise fix guidance in real time as the deck is edited.
		- Legality state shown in the builder always matches what the server independently validates on save.
	- **Related issues**:
		- Split from: LOT-025.
		- Depends on: LOT-014 (deck legality and format enforcement service).
	- **Status: DONE (found already implemented, verified this session)**:
		- `gotdot/scripts/deck_editor.gd`'s `_refresh_legality()` calls
		  `Api.get_deck_legality()` (→ `GET /decks/{deck_id}/legality`) from
		  inside `_load_deck()`, which both `_add_card()` and `_remove_card()`
		  await via `_load_all()` — every add/remove, whether triggered by
		  double-click or drag-drop, re-runs the full live legality check.
		- The `LegalityLabel` UI node shows aggregate counts (draw deck size,
		  Free Peoples/Shadow counts, site count) plus the per-rule issue
		  strings, colored green when legal and orange when not.
		- Copy-limit violations (LOT-014's `check_copy_limit`) are blocked
		  proactively at add-time: the add-card route returns 400 with a
		  specific message (e.g. "...maximum is 4", "...only one copy..."),
		  which `_add_card()` surfaces via `_set_notice(...)`.
		- Verified end-to-end via a live HTTP smoke test exercising the same
		  routes the Godot client calls: empty deck is illegal -> incremental
		  adds converge on a legal 60/30/30/9 deck -> 5th-copy and 2nd-site-copy
		  requests are rejected with the expected messages -> removing a site
		  drops the deck back out of legality.
		- Remaining minor gaps vs. the acceptance criteria (not blocking, not
		  acted on): the aggregate-level rules (size/split/site-count) don't
		  name a specific offending card (they are inherently deck-wide, not
		  per-card); there's no explicit debounce, though none is needed since
		  each edit is a single discrete action rather than rapid-fire input.
		  Format/X-list/R-list/errata diagnostics are out of scope here pending
		  LOT-014 implementing those rules server-side.

- **LOT-100** — LOT-025 follow-up backlog (deferred slice scope).
	- **Type**: backlog/tracking
	- **Priority**: 2
	- **Note**:
		- LOT-025 is delivered as a series of incremental slices rather than one
		  monolithic change. Each slice is scoped deliberately narrow so it can be
		  built, tested, and verified end-to-end before moving on. This issue is
		  the catch-all for scope explicitly deferred out of a completed/
		  in-progress LOT-025 (or supporting LOT-017/018/019/020/021/022) slice,
		  so nothing gets silently dropped. Items move OUT of this list and into
		  `issues-current.md`/`issues-todo.md` when picked up as their own slice.
	- **Problem statement**:
		- Without a running backlog record, incremental slice-based delivery of
		  a large consolidation issue risks losing track of deliberately-deferred
		  scope.
	- **Backlog items (as of Slice 2 — booster generation/sell-back)**:
		- ~~`starter_deck`/`booster_box` server-side card generation~~ — **DONE**
		  (booster_box: Slice 3, `BOOSTER_BOX_PACK_COUNT`; starter_deck: found
		  already implemented in an earlier session, see below). Superseded by
		  the more detailed bullets further down this list.
		- ~~Real card catalog import~~ — **DONE.** `migrate_import_card_catalog.py`
		  imports the real catalog from
		  `build/do/assets/database/card_database.json`; live DB confirmed at
		  3,411 active cards (common=1014/uncommon=883/rare=1113/legendary=186/
		  mythic=215) across sets 0-19 and 30-32. The 12 placeholder Set-1 rows
		  were deactivated (`is_active=0`), not deleted.
		- ~~LOT-018 entitlement bundles~~ — **DONE**: new-account bootstrap grant
		  (1 starter deck + 5 packs from set 1, `_grant_new_user_entitlements`,
		  triggered on `POST /auth/register`) and per-set-unlock release bundles
		  (`_grant_release_bundle_to_all_users`, triggered on
		  `POST /admin/set-releases/{n}/activate`, idempotent per-user/per-set —
		  verified live: a deactivate/reactivate cycle does not double-grant).
		  Registration timestamp is `User.created_at` (always set at insert
		  time; no legacy-backfill gap found in the live schema).
		- ~~`starter_deck` card generation~~ — **DONE** (found already
		  implemented, undocumented, in an earlier session): curated set-1
		  decklist at `server/data/starter_decks_set1.json`, granted via
		  `_grant_starter_deck_cards()` from both `/store/purchase` and
		  entitlement-claim. Other sets have no curated decklist yet (real
		  game-design content, not something to invent here).
		- LOT-019 gift ledger and redemption lifecycle: the core states/API
		  (created/granted/redeemed/consumed/expired/revoked enum, admin
		  create/revoke, user list/redeem, concurrency-safe atomic state
		  transitions, lazy expiry) is DONE (slice 5) for `pack`/`booster_box`
		  products. Still open: `starter_deck`/`promo_card` gift redemption
		  (blocked on the same missing curated-content gap as store purchases
		  of those products). ~~Store-surface gift/entitlement claim UX~~ —
		  **DONE**: `card_reveal.gd`/`.tscn` overlay wired into `new_game.gd` for
		  both starter-deck and booster-pack claim flows.
		- ~~Weekly active-user random foil reward job~~ — **DONE**: rolled
		  lazily at login (`_maybe_roll_weekly_foil_reward`, hooked into
		  `_issue_tokens_for_user`), 5% chance, weighted common/uncommon/rare,
		  windows anchored to `User.created_at`, non-stacking via a unique
		  `(user_id, week_index)` index on the new `weekly_reward_rolls` table
		  (`migrate_add_weekly_rewards.py`) — verified live for win/loss/
		  idempotency paths.
		- ~~LOT-021 telemetry beyond the baseline~~ — **DONE**: new
		  `EconomySnapshot` model/table (`migrate_add_economy_snapshots.py`)
		  captures point-in-time totals (cards in circulation, foil issued,
		  Tolkien net flow, sell-back totals, weekly reward stats) plus the
		  full raw `EconomySummaryResponse` for drill-down. No background
		  scheduler exists in this repo, so capture is lazy: `GET
		  /admin/economy/summary` captures at most one snapshot per calendar
		  day, the first time it's called that day. New
		  `GET /admin/economy/trends` route returns snapshots oldest-first with
		  simple threshold/drift alerts (`ECONOMY_SNAPSHOT_DRIFT_ALERT_THRESHOLD_PCT`,
		  currently 25%) computed between consecutive snapshots per metric.
		  ~~Weekly-active-user reward telemetry~~ — **DONE**:
		  `GET /admin/economy/summary` now also returns `weekly_reward_stats`
		  (total rolls, wins/losses, win rate, distinct users rolled — a proxy
		  for weekly-active users since a roll row is only ever created via a
		  successful login — and wins by rarity), aggregated from the
		  `weekly_reward_rolls` table. The current-totals baseline
		  (`GET /admin/economy/summary` — circulation, foil issuance, Tolkien
		  flow by source, sell-back totals) is DONE (slice 4).
		- ~~LOT-022 release events/participation schema~~ — **DONE**: new
		  `ReleaseEvent`/`EventParticipation` models
		  (`migrate_add_release_events.py`), admin CRUD
		  (`POST /admin/events`, `GET /admin/events`,
		  `POST /admin/events/{id}/activate|close`,
		  `GET /admin/events/{id}/participants`), public
		  `GET /events` + `POST /events/{id}/join` (idempotent per user/event
		  via a unique index), scheduled/live/closed status model, and
		  `reward_policy` left as a pluggable free-form JSON field for future
		  promo-card prize awarding. Set activation now auto-links (creates or
		  reactivates, never duplicates) a `live` event for that set_number
		  via `_ensure_live_release_event` — verified live across a
		  deactivate/reactivate cycle.
		- ~~Card-authoring/admin catalog workflow~~ — **DONE**: `Card` gained
		  `publish_status` (`draft`/`in_review`/`published`, DB default stays
		  `'published'` for the existing bulk-imported catalog, ORM Python-side
		  default is `'draft'` for newly authored cards) and `review_notes`
		  columns (`migrate_add_card_review_gate.py`). Public catalog routes
		  (`GET /cards`, `GET /cards/{id}`) now only return `published` cards.
		  New admin routes: `GET /admin/cards` (any status, filterable),
		  `POST /admin/cards/{id}/submit-review` (draft->in_review),
		  `POST /admin/cards/{id}/publish` (in_review->published),
		  `POST /admin/cards/{id}/reject` (in_review->draft, records
		  `review_notes`) — each enforces the expected prior state (400
		  otherwise). Release linking: `CardBase`/`CardCreate`/`CardUpdate`
		  gained `set_number`, validated against `SetRelease` on create/update
		  (400 if the set doesn't exist) — this also fixed a pre-existing schema
		  gap where the card schemas had no `set_number` field at all. Also
		  fixed two pre-existing bugs surfaced while building this: (1)
		  `CardCreate`/`CardUpdate` expose a `stats` field with no matching
		  `Card` column (`Card` has `attributes`) — `create_card`/`update_card`
		  now explicitly remap `stats`->`attributes`; (2) `CardResponse`
		  serialization of raw ORM `Card` objects always returned `stats: null`
		  regardless of actual data, because `CardBase` had no
		  `from_attributes` config and there's no ORM attribute literally named
		  `stats` — fixed by adding `model_config = ConfigDict(from_attributes=True)`
		  to `CardBase` plus a `Card.stats` Python `@property` alias for
		  `attributes`. Verified live end-to-end (create as draft ->
		  hidden from public catalog -> submit-review -> reject with notes ->
		  resubmit -> publish -> now visible in public catalog, plus the
		  release-linking 400 and admin-queue filter).

		- Deck builder UX — **partially done**: a functional interim editor
		  exists (`deck_builder.gd/tscn` deck-selection screen +
		  `deck_editor.gd/tscn` two-pool selected/available editor, card
		  preview, drag-drop/double-click add-remove, backed by
		  `GET /users/me/cards/available`).
		  ~~Grouped culture/card-type filters~~ — **DONE**: the filter panel
		  now has three checkbox groups (Rarity, Card Type, Culture) instead
		  of rarity-only, reading `card.stats.card_type`/`card.stats.culture`
		  (already serialized by the server, no API change needed) and wrapped
		  in a `ScrollContainer` since there are ~41 checkboxes total. The
		  spec's wishlist terms "burdens"/"signet"/"weapon" aren't distinct
		  `card_type` values in the real imported catalog (signet is a
		  per-card field, Weapon is a `subtypes` entry) — intentionally not
		  modeled as separate filters; see `/memories/repo/godot-dev-gotchas.md`
		  for the full real-data taxonomy. Verified via two Godot headless
		  checks (full project boot with zero errors; a temp `-s` script that
		  loads+instantiates `deck_editor.tscn` to confirm the new
		  `FiltersScroll/FiltersBox` node path resolves and the script
		  compiles) — no visual/screenshot verification was possible in this
		  environment (disclosed, not claimed).
		  **Still open**: the exact
		  binder-metaphor card browser (9x9, two-page spread), split-screen
		  deck-summary grid (4 cols x N rows, no duplicate tiles) with Deck
		  Cards/Sites/Starting Fellowship tabs, mutually-exclusive
		  tournament-ruleset selection.
		  ~~Sets checklist~~ — **DONE**: a dynamic "Set" filter section is
		  appended to the filter panel, built from whichever `set_number`
		  values actually appear across the deck's + available pool's cards
		  (not a fixed list, since the catalog only has Set 1 today), labeled
		  via `GET /releases/active-sets` (falls back to "Set N" for cards
		  from a since-deactivated set). New `Api.get_active_sets()` client
		  method added (public route, no auth). Verified the same way as the
		  card-type/culture filters (Godot headless full-boot + a temp
		  SceneTree script instantiating `deck_editor.tscn`) — no live
		  multi-set data exists yet to exercise more than one checkbox, but
		  the code path is identical to the already-working rarity filter.
		  ~~25-decks-per-user cap~~ — **DONE**: enforced in `POST /decks`
		  (`MAX_DECKS_PER_USER = 25`), verified live (26th deck creation
		  correctly rejected with 400).
		- ~~Wiring live legality diagnostics (LOT-032/LOT-014) into the deck
		  builder once it exists.~~ — **DONE (found already implemented,
		  verified this session)**: see the LOT-032 entry's "Status" note
		  above for full details. No code changes were needed; this slice was
		  a verification-and-documentation pass (the tracker had gone stale —
		  the feature was already built).
	- **Acceptance criteria**:
		- Every bullet above is either completed (moved into
		  `issues-completed.md` as its own slice/issue with its own
		  verification) or explicitly cut with a documented reason before this
		  issue itself is closed.
		- This list stays current: new deferrals discovered mid-slice are added
		  here rather than left undocumented in code comments alone.

- **Removed As Overlap (Not Started)**
	- **OLD-LOT-022 (pre-renumber)** — merged into LOT-018 and LOT-019.
	- **OLD-LOT-023 (pre-renumber)** — merged into LOT-020 and LOT-021.
	- **OLD-LOT-026 (pre-renumber)** — merged into LOT-017 and LOT-022.
	- **OLD-LOT-028 (pre-renumber)** — superseded by LOT-022 now; tournament operations to be reintroduced after event foundation.
	- **OLD-LOT-037 (pre-renumber)** — consumed by this consolidation update.

### Active:

### Pending

### Complete

