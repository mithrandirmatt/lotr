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

- **LOT-003** — Make admin account login. User: lotradmin, password: yourmommalooksfunny.
  - Admin login behavior: Any user with `is_admin=True` can log in using their registered email and password to access the admin panel (not just username/password). This allows multiple administrators while maintaining secure email-based auth.
  - Local admin shortcut behavior: For local development only, login accepts `lotradmin:yourmommalooksfunny` as a direct admin shortcut; all other credentials use normal email/username + password auth.
  - Admin account capabilities:
    - Add/remove cards from database
    - Add/remove users
    - Grant/revoke admin privileges to other users
  - **Status**: ✅ **COMPLETED** — Admin account created with full administrative capabilities, plus dual-mode authentication (local shortcut + standard email/username password login).

- **LOT-004** — Login/auth endpoints implemented. Register, login (JWT), refresh token, logout, and protected route dependency all in `server/server/routes/api.py`.
  - Authentication: All users log in via their registered email address with bcrypt password hashing; JWT tokens issued for session management.
  - Admin access: Any user where `is_admin=True` can authenticate to the admin panel using standard login flow (email + password).
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

- **LOT-007** — Login Screen with Email-Based Authentication for Admins, plus Registration and Mandatory Two-Factor Authentication (2FA).
  - Implemented login and register pages with validation, authentication context, and protected routing.
  - Backend endpoints already exist (see LOT‑004). Front‑end now redirects to dashboard on success.
  - Registration flow fixed end-to-end: backend `RegisterRequest` schema (`email`, `unique_name`, `password`, `confirm_password`) and rewritten `POST /auth/register` endpoint; new `GET /auth/check-email` and `GET /auth/check-unique-name` endpoints; frontend `client.ts`/`RegisterPage.tsx` updated to send matching snake_case fields including `confirm_password`.
  - Mandatory TOTP-based 2FA (RFC 6238; compatible with Google Authenticator, Authy, 1Password) added:
    - `User.totp_secret`, `User.is_2fa_enabled`, `User.totp_recovery_codes` columns added via `server/scripts/migrate_add_2fa_columns.py`.
    - New endpoints under `/api/v1/auth/2fa`: `POST /2fa/setup`, `POST /2fa/enable`, `POST /2fa/disable`, `POST /2fa/verify-login`.
    - `POST /auth/login` now returns `{ requires_2fa: true, mfa_token }` for accounts with 2FA enabled instead of issuing tokens directly (local-admin dev shortcut is unaffected and still bypasses 2FA by design).
    - Frontend: `LoginPage` has a second "enter your 6-digit code" step; new `TwoFactorSetupPage` is shown via a `ProtectedRoute` redirect the first time any authenticated user has `is_2fa_enabled=False`, displaying the QR code, manual-entry secret, and — on success — the 10 single-use recovery codes exactly once.
    - New dependencies: `pyotp`, `qrcode[pil]` (added to `server/pyproject.toml`, installed in the `lotr-server` container).
  - Verified end-to-end via curl (register → login → 2fa/setup → 2fa/enable → login requiring 2FA → 2fa/verify-login → 2fa/disable via recovery code) and via a full browser walkthrough of the actual admin panel UI (registration, mandatory 2FA setup redirect, QR/secret display, recovery codes, sign-out/sign-in MFA challenge, successful Dashboard access).
  - **Status**: ✅ **COMPLETED**
  - **Update**: Same registration + mandatory 2FA feature implemented natively in the Godot client (was originally requested for the game):
    - New `gotdot/scripts/api_client.gd` autoload (`Api`, registered in `project.godot`) — a self-contained HTTP client wrapping every relevant backend endpoint (`check-email`, `check-unique-name`, `register`, `login` form-encoded via `OAuth2PasswordRequestForm`, `2fa/setup`, `2fa/enable`, `2fa/verify-login`, `users/me`), handling JSON/form encoding, bearer auth, and the `requires_2fa`/`mfa_token` login branch.
    - `gotdot/scripts/login.gd` + `gotdot/scenes/login.tscn` fully rewritten (the previous versions were non-functional placeholder/demo code with an auto-advancing timer and no password field): real Welcome → Sign In → Register → MFA-challenge flow, live debounced uniqueness/availability checks for email and username, full client-side validation (email format, password length, confirm-password match), and routing to mandatory 2FA setup after first login for accounts without 2FA enabled.
    - New `gotdot/scripts/two_factor_setup.gd` + `gotdot/scenes/two_factor_setup.tscn` — mandatory first-login 2FA enrollment screen: fetches QR code + manual secret from `/2fa/setup`, decodes the base64 PNG into a `TextureRect` via `Image`/`ImageTexture`, verifies the 6-digit code via `/2fa/enable`, and displays the one-time recovery codes before continuing to the main menu.
    - Verified via headless Godot (`godot --headless --quit --path gotdot`, Godot 4.4.1) inside the dev container: project boots and reaches the login screen with zero script parse/compile errors across `api_client.gd`, `login.gd`, and their scenes. `two_factor_setup.gd` isn't reachable from a cold `--quit` boot (only shown after a live login round-trip), so it was validated by careful manual review plus isolated standalone GDScript checks of its specific API patterns (`String.join()` on both `Array` and `PackedStringArray`, `Marshalls.base64_to_raw`/`Image.load_png_from_buffer`/`ImageTexture.create_from_image`), all confirmed correct. One real bug was found and fixed during this process: a method named `_get()` in `api_client.gd` collided with Godot's built-in `Object._get(property) -> Variant` virtual, breaking autoload instantiation; renamed to `_http_get()`.
    - Not yet performed: a full interactive functional test against the live `lotr-server` backend (register → login → 2FA setup → 2FA login) from within the running game, since headless mode can't drive UI interaction — static validation plus code review were used instead given the constraints of this environment.

- **LOT-007.1** — 2FA account recovery (lost authenticator device with no way to re-enroll).
  - Original request: "2FA is failing for the admin panel. I removed the 2FA from my phone, so now the app is stuck without a mode of recovery. Let's create a LOT-007.1 issue card for setting up 2FA recovery, which basically allows you to scan and set it up again."
  - Root cause: `/auth/2fa/verify-login` already accepted recovery codes as an alternative to a TOTP code, but (1) the admin panel's MFA-challenge input was hardcoded to a 6-digit numeric field (`maxLength=6`, `pattern="[0-9]{6}"`), making it physically impossible to type a recovery code (format `xxxxxxxx-xxxxxxxx`), and (2) even if a recovery code were accepted there, `verify-login` only logs the user back in — it does not clear the stale `totp_secret`, so the user would be locked out again on their very next login since the authenticator entry is already gone.
  - Backend: added `TwoFactorRecoverRequest` schema and `POST /auth/2fa/recover` endpoint (`server/server/routes/api.py`) — takes the same short-lived `mfa_token` issued after the password step plus a recovery code; consumes the code (single-use, same `consume_recovery_code` helper used elsewhere), clears `totp_secret`/`is_2fa_enabled`/`totp_recovery_codes`, and issues real access/refresh tokens in one step.
  - Frontend (admin panel): `client.ts` `recover2fa()`, `AuthContext.tsx` `recoverWithBackupCode()`, and a "Lost access to your authenticator app? Recover with a backup code" toggle on `LoginPage.tsx`'s MFA step that swaps in a plain-text recovery-code input (no 6-digit/numeric restriction). Since the account's `is_2fa_enabled` becomes `false` after a successful recovery, the existing `ProtectedRoute` redirect (`!user.is_2fa_enabled` → `/2fa-setup`) automatically sends the user to scan a fresh QR code — no new redirect logic needed.
  - Maintenance script: added `server/scripts/reset_2fa.py <email-or-username>` for the edge case where an account has lost both the authenticator app *and* all recovery codes (where `/auth/2fa/recover` can't help either, since it still needs one valid code) — clears 2FA state directly in the DB so the account can log in with just its password.
  - Immediate remediation: ran `reset_2fa.py` against the reporter's locked-out account (`mithrandirmatt@yahoo.com`) to restore access right away; confirmed via direct DB read that `is_2fa_enabled`/`totp_secret`/`totp_recovery_codes` were all cleared.
  - Verified end-to-end via a scripted HTTP flow against the live `lotr-server` container: register → login → `/2fa/setup` → `/2fa/enable` → login (now requiring 2FA, returns `mfa_token`) → `/2fa/recover` with a real recovery code (200, tokens returned) → reusing the same recovery code correctly rejected (401) → `/users/me` confirms `is_2fa_enabled: false` post-recovery, ready to re-enroll via the normal setup flow.
  - **Status**: ✅ **COMPLETED**

- **LOT-009** — Fix 500 error when deleting a user from the admin panel.
  - Original request: "trying to delete user in admin panel, get Request failed with status code 500."
  - Root cause: `DELETE /admin/users/{user_id}` (`admin_delete_user` in `server/server/routes/api.py`) calls `db.delete(user)`. `RefreshToken.user` was declared via a plain `backref="refresh_tokens"` with no cascade configured, so SQLAlchemy's default behavior on parent delete is to disassociate children by setting their FK to `NULL` rather than deleting them. `refresh_tokens.user_id` is `nullable=False`, so any user with a live refresh token (i.e. anyone who has ever logged in) hit `sqlite3.IntegrityError: NOT NULL constraint failed: refresh_tokens.user_id` on `db.commit()`, surfacing as a 500. Confirmed via the real `lotr-server` container logs (`docker logs lotr-server`), which captured the exact failing `DELETE /api/v1/admin/users/{id}` request and full traceback.
  - Fix: `server/server/models/models.py` — added `refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")` on `User`, and changed `RefreshToken.user` from `relationship("User", backref="refresh_tokens")` to `relationship("User", back_populates="refresh_tokens")`, matching the existing `back_populates`+`cascade="all, delete-orphan"` pattern already used for `ownerships`/`purchases`/`match_players`/`audit_logs`/`decks`. Now deleting a user also deletes their refresh tokens instead of trying to null out a non-nullable FK.
  - Verified end-to-end against the live `lotr-server` container: registered a fresh test user, logged them in (creating a real `refresh_tokens` row), then deleted them via the admin endpoint using the triple-confirmation payload — returned `200 {"message": "User deleted successfully", ...}` instead of the previous 500.
  - **Status**: ✅ **COMPLETED**