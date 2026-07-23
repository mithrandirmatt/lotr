# LotR TCG Project — Completed Task Tracker

Only list the current active issue here. This should serve as a reminder of what we are currently working on.

## Behaviors

When shelving an issue to work on another, ensure the current issue is queued in this file.

Ensure when working on an issue, that the issue is listed here while it is being worked on.
Once complete, remove from this file and move it to the issues-completed.md file.


## Current Issue(s) Being Worked:

(none — see issues-completed.md for LOT-007 and LOT-007.1)

## Queued Issues:

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

## Queued Issues:



