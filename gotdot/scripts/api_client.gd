extends Node

## Autoload singleton ("Api") that talks to the LotR TCG backend
## (server/server/routes/api.py) over HTTP for authentication, registration,
## and two-factor authentication (LOT-007).
##
## All request methods are `await`-able and return a Dictionary shaped like:
##   { "ok": bool, "status": int, "data": Dictionary, "error": String }
## On success `data` holds the parsed JSON response body.

const DEFAULT_BASE_URL := "http://127.0.0.1:8000/api/v1"

var base_url: String = DEFAULT_BASE_URL

var access_token: String = ""
var refresh_token: String = ""
var mfa_token: String = ""
var current_user: Dictionary = {}


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
