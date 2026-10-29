extends Node

## Autoload singleton ("Api") that talks to the LotR TCG backend
## (server/server/routes/api.py) over HTTP for authentication, registration,
## and two-factor authentication (LOT-007).
##
## All request methods are `await`-able and return a Dictionary shaped like:
##   { "ok": bool, "status": int, "data": Dictionary, "error": String }
## On success `data` holds the parsed JSON response body.

const DEFAULT_BASE_URL := "http://127.0.0.1:8000/api/v1"

## Where the "remember me" refresh token is persisted (LOT-007 auto-login).
## user:// is Godot's per-user app-data directory, not the res:// project dir.
const SESSION_FILE_PATH := "user://session.save"

var base_url: String = DEFAULT_BASE_URL

var access_token: String = ""
var refresh_token: String = ""
var mfa_token: String = ""
var current_user: Dictionary = {}

## Whether a successful login should persist its refresh token to disk so
## the next app launch can auto-login. Set by the login screen from its
## "Remember me" checkbox before calling login()/verify_2fa_login().
var remember_me: bool = true


func _ready() -> void:
	var env_url := OS.get_environment("LOTR_API_BASE_URL")
	if env_url != "":
		base_url = env_url


func is_logged_in() -> bool:
	return access_token != ""


func reset_session() -> void:
	access_token = ""
	refresh_token = ""
	mfa_token = ""
	current_user = {}


# ---------------------------------------------------------------------------
# Low-level request helper
# ---------------------------------------------------------------------------

func _request(method: HTTPClient.Method, path: String, headers: PackedStringArray, body: String) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)

	var err := http.request(base_url + path, headers, method, body)
	if err != OK:
		http.queue_free()
		return {"ok": false, "status": 0, "data": {}, "error": "Could not reach server (error %d)" % err}

	var response: Array = await http.request_completed
	http.queue_free()

	var response_code: int = response[1]
	var raw_body: PackedByteArray = response[3]
	var text := raw_body.get_string_from_utf8()

	var data: Dictionary = {}
	if text.length() > 0:
		var parsed = JSON.parse_string(text)
		if typeof(parsed) == TYPE_DICTIONARY:
			data = parsed

	var ok := response_code >= 200 and response_code < 300
	var error_msg := ""
	if not ok:
		if data.has("detail"):
			var detail = data["detail"]
			error_msg = detail if typeof(detail) == TYPE_STRING else JSON.stringify(detail)
		else:
			error_msg = "Request failed (status %d)" % response_code

	return {"ok": ok, "status": response_code, "data": data, "error": error_msg}


func _http_get(path: String, auth: bool = false) -> Dictionary:
	var headers := PackedStringArray()
	if auth:
		headers.append("Authorization: Bearer " + access_token)
	return await _request(HTTPClient.METHOD_GET, path, headers, "")


func _post_json(path: String, payload: Dictionary, auth: bool = false) -> Dictionary:
	var headers := PackedStringArray(["Content-Type: application/json"])
	if auth:
		headers.append("Authorization: Bearer " + access_token)
	return await _request(HTTPClient.METHOD_POST, path, headers, JSON.stringify(payload))


func _post_form(path: String, fields: Dictionary) -> Dictionary:
	var headers := PackedStringArray(["Content-Type: application/x-www-form-urlencoded"])
	var parts := PackedStringArray()
	for key in fields.keys():
		parts.append(str(key).uri_encode() + "=" + str(fields[key]).uri_encode())
	return await _request(HTTPClient.METHOD_POST, path, headers, "&".join(parts))


func _http_delete(path: String, auth: bool = false) -> Dictionary:
	var headers := PackedStringArray()
	if auth:
		headers.append("Authorization: Bearer " + access_token)
	return await _request(HTTPClient.METHOD_DELETE, path, headers, "")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

func check_email(email: String) -> Dictionary:
	return await _http_get("/auth/check-email?email=" + email.uri_encode())


func check_unique_name(unique_name: String) -> Dictionary:
	return await _http_get("/auth/check-unique-name?unique_name=" + unique_name.uri_encode())


func register(email: String, unique_name: String, password: String, confirm_password: String) -> Dictionary:
	return await _post_json("/auth/register", {
		"email": email,
		"unique_name": unique_name,
		"password": password,
		"confirm_password": confirm_password,
	})


# ---------------------------------------------------------------------------
# Login / 2FA
# ---------------------------------------------------------------------------

## Logs in with an email/username + password. On success, `data.requires_2fa`
## tells the caller whether to show the 6-digit MFA challenge step next.
func login(username_or_email: String, password: String) -> Dictionary:
	var res := await _post_form("/auth/login", {
		"username": username_or_email,
		"password": password,
	})
	if not res.ok:
		return res

	if res.data.get("requires_2fa", false):
		mfa_token = res.data.get("mfa_token", "")
		return {"ok": true, "status": res.status, "data": {"requires_2fa": true}, "error": ""}

	_store_tokens(res.data)
	var me := await get_me()
	return {"ok": true, "status": res.status, "data": {"requires_2fa": false}, "error": "" if me.ok else me.error}


## Completes a login that required 2FA by exchanging the pending mfa_token
## and a 6-digit TOTP (or recovery) code for real tokens.
func verify_2fa_login(code: String) -> Dictionary:
	var res := await _post_json("/auth/2fa/verify-login", {
		"mfa_token": mfa_token,
		"code": code,
	})
	if not res.ok:
		return res

	mfa_token = ""
	_store_tokens(res.data)
	var me := await get_me()
	return {"ok": true, "status": res.status, "data": {}, "error": "" if me.ok else me.error}


func setup_2fa() -> Dictionary:
	return await _post_json("/auth/2fa/setup", {}, true)


func enable_2fa(code: String) -> Dictionary:
	var res := await _post_json("/auth/2fa/enable", {"code": code}, true)
	if res.ok:
		current_user["is_2fa_enabled"] = true
	return res


func get_me() -> Dictionary:
	var res := await _http_get("/users/me", true)
	if res.ok:
		current_user = res.data
	return res


func _store_tokens(token_data: Dictionary) -> void:
	access_token = token_data.get("access_token", "")
	refresh_token = token_data.get("refresh_token", "")
	if remember_me:
		_save_session()


# ---------------------------------------------------------------------------
# "Remember me" session persistence (LOT-007 auto-login)
# ---------------------------------------------------------------------------

func _save_session() -> void:
	var file := FileAccess.open(SESSION_FILE_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({"refresh_token": refresh_token}))
		file.close()


func _load_saved_refresh_token() -> String:
	if not FileAccess.file_exists(SESSION_FILE_PATH):
		return ""
	var file := FileAccess.open(SESSION_FILE_PATH, FileAccess.READ)
	if not file:
		return ""
	var text := file.get_as_text()
	file.close()
	var parsed = JSON.parse_string(text)
	if typeof(parsed) == TYPE_DICTIONARY:
		return parsed.get("refresh_token", "")
	return ""


func clear_saved_session() -> void:
	if FileAccess.file_exists(SESSION_FILE_PATH):
		DirAccess.remove_absolute(SESSION_FILE_PATH)


## Exchanges the current `refresh_token` for a fresh access/refresh token
## pair (the backend rotates refresh tokens on every use -- see
## POST /auth/refresh). Used both for normal session-keepalive and for
## restoring a saved "remember me" session at app startup.
func refresh_session() -> Dictionary:
	var res := await _post_json("/auth/refresh", {"refresh_token": refresh_token})
	if not res.ok:
		return res
	_store_tokens(res.data)
	return res


## Attempts to restore a previously "remembered" session using the refresh
## token saved to disk. Returns the usual {ok, status, data, error} shape;
## on success `current_user` is populated same as after a normal login.
func try_auto_login() -> Dictionary:
	var saved_refresh_token := _load_saved_refresh_token()
	if saved_refresh_token == "":
		return {"ok": false, "status": 0, "data": {}, "error": "No saved session"}

	refresh_token = saved_refresh_token
	var res: Dictionary = await refresh_session()
	if not res.ok:
		# Saved token is expired/revoked -- don't keep retrying with it.
		clear_saved_session()
		reset_session()
		return res

	var me := await get_me()
	return {"ok": me.ok, "status": res.status, "data": {}, "error": "" if me.ok else me.error}


## Logs out server-side (revokes all refresh tokens for this user) and
## forgets any saved "remember me" session on this device.
func logout() -> void:
	if is_logged_in():
		await _post_json("/auth/logout", {}, true)
	clear_saved_session()
	reset_session()


# ---------------------------------------------------------------------------
# Decks (LOT-005 deck manager / LOT-014 deck legality)
# ---------------------------------------------------------------------------

## Deck id handed off from the deck-selection screen to the deck-editor
## screen (`res://scenes/deck_editor.tscn`) across a scene change.
var selected_deck_id: String = ""

## Lists the current user's decks (DeckListResponse: { items, total }).
func get_decks() -> Dictionary:
	return await _http_get("/decks", true)


func create_deck(deck_name: String, format: String = "Open") -> Dictionary:
	return await _post_json("/decks", {"name": deck_name, "format": format}, true)


## Fetches a single deck with its full card list (DeckResponse).
func get_deck(deck_id: String) -> Dictionary:
	return await _http_get("/decks/" + deck_id.uri_encode(), true)


func delete_deck(deck_id: String) -> Dictionary:
	return await _http_delete("/decks/" + deck_id.uri_encode(), true)


## Runs the LOT-014 legality check (draw deck size, Free Peoples/Shadow
## split, adventure-deck site count) for a deck.
func get_deck_legality(deck_id: String) -> Dictionary:
	return await _http_get("/decks/" + deck_id.uri_encode() + "/legality", true)


func add_card_to_deck(deck_id: String, card_id: String, quantity: int = 1) -> Dictionary:
	return await _post_json(
		"/decks/" + deck_id.uri_encode() + "/cards",
		{"card_id": card_id, "quantity": quantity},
		true
	)


## Removes a card from a deck. Pass `quantity <= 0` to remove the whole slot.
func remove_card_from_deck(deck_id: String, card_id: String, quantity: int = -1) -> Dictionary:
	var path := "/decks/" + deck_id.uri_encode() + "/cards/" + card_id.uri_encode()
	if quantity > 0:
		path += "?quantity=%d" % quantity
	return await _http_delete(path, true)


## Lists every card the current user owns (UserCardList: { cards, total_cards }).
## Ownership is per-copy, so a card owned 3x appears as 3 separate entries.
func get_my_cards() -> Dictionary:
	return await _http_get("/users/me/cards", true)


## Per-card owned/assigned/available breakdown for the deck builder's
## "available pool" (a card has spare copies to add to a deck only if it
## has >=1 unassigned copy across ALL of the user's decks combined).
## OwnedCardAvailabilityListResponse: { items: [{card, owned_quantity,
## assigned_quantity, available_quantity}] }.
func get_available_cards() -> Dictionary:
	return await _http_get("/users/me/cards/available", true)


func get_card(card_id: String) -> Dictionary:
	return await _http_get("/cards/" + card_id.uri_encode())


## Public list of currently-active (purchasable) sets -- used by the deck
## editor to label its "Set" filter checkboxes. ActiveSetsResponse:
## { active_sets: [{set_number, set_code, name, is_active, ...}] }.
func get_active_sets() -> Dictionary:
	return await _http_get("/releases/active-sets")


# ---------------------------------------------------------------------------
# Entitlements (LOT-018 new-user gift claiming / "New Game" flow)
# ---------------------------------------------------------------------------

## Lists the current user's entitlement ledger (starter deck + booster pack
## grants). EntitlementListResponse: { items: [{id, product_type, set_number,
## quantity, status, ...}] }.
func get_entitlements() -> Dictionary:
	return await _http_get("/entitlements", true)


## Lists the curated starter decks available to choose from for a set.
## StarterDeckOptionsResponse: { items: [{deck_key, name, card_count}] }.
func get_starter_deck_options(set_number: int = 1) -> Dictionary:
	return await _http_get("/entitlements/starter-deck-options?set_number=%d" % set_number, true)


## Claims an entitlement, generating and granting its real cards. `deck_key`
## only matters for starter_deck entitlements (see get_starter_deck_options);
## pass "" to let the server pick one at random. Ignored for booster_pack.
func claim_entitlement(entitlement_id: String, deck_key: String = "") -> Dictionary:
	return await _post_json(
		"/entitlements/" + entitlement_id.uri_encode() + "/claim",
		{"deck_key": deck_key},
		true
	)
