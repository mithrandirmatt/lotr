"""Reset the ai_test_account account to a fresh, brand-new-account state.

ai_test_account is the repo's standing test account (see
`.github/agent/rules.md` -- "Testing Accounts"). Instead of creating throwaway
test users for every manual/smoke test, use this account and reset it
in-place via the existing `POST /admin/users/{id}/reset` endpoint, which:
  - wipes ownerships, decks (+ deck_cards via cascade), and entitlements
  - zeroes tolkien_balance
  - re-grants the standard new-user bootstrap bundle (1 starter deck +
    5 booster pack entitlements for set 1, + the welcome Tolkien bonus)
while keeping the account's login (email/username/password) unchanged.

Run inside the dev container (server must be up on localhost:8000):
    python scripts/reset_ai_test_account.py
"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/v1"

ADMIN_USERNAME = "lotradmin"
ADMIN_PASSWORD = "yourmommalooksfunny"

AI_TEST_USERNAME = "ai_test_account"
AI_TEST_EMAIL = "ai_test_account@example.com"


def post_form(path, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def request_json(path, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return e.code, {"raw": raw.decode(errors="replace")}


def main():
    token = post_form("/auth/login", {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})["access_token"]

    status, users = request_json(f"/admin/users?search={AI_TEST_USERNAME}", token=token)
    if status != 200 or not users.get("items"):
        raise SystemExit(f"Could not find user '{AI_TEST_USERNAME}' (status {status}): {users}")
    user_id = users["items"][0]["id"]

    status, resp = request_json(
        f"/admin/users/{user_id}/reset", method="POST", token=token,
        body={
            "confirm_user_id": user_id,
            "confirm_username": AI_TEST_USERNAME,
            "confirm_email": AI_TEST_EMAIL,
        },
    )
    if status != 200:
        raise SystemExit(f"Reset failed (status {status}): {resp}")

    print(f"Reset '{AI_TEST_USERNAME}' to a fresh new-account state: {resp}")


if __name__ == "__main__":
    main()
