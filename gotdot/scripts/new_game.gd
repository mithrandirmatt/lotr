extends Control

## New Game / gift-opening flow (LOT-018). Lets a new (or backfilled legacy)
## account claim its bootstrap entitlements: 1 starter deck (player picks
## from the curated Set 1 options) + 5 booster packs. The Tolkien welcome
## bonus itself is credited automatically at registration, so this screen
## just displays the resulting balance.
##
## This does NOT start an actual match (Phase 3 / the game engine isn't
## built yet) -- once entitlements are claimed, the player returns to the
## main menu to build a deck with their new cards.

@onready var _notification: Label = $CanvasLayer/Notification
@onready var _tolkien_label: Label = $CanvasLayer/TolkienLabel

@onready var _starter_status_label: Label = $CanvasLayer/ContentBox/StarterSection/StarterStatusLabel
@onready var _deck_options_box: VBoxContainer = $CanvasLayer/ContentBox/StarterSection/DeckOptionsBox

@onready var _booster_status_label: Label = $CanvasLayer/ContentBox/BoosterSection/BoosterStatusLabel
@onready var _open_boosters_btn: Button = $CanvasLayer/ContentBox/BoosterSection/OpenBoostersBtn

const CardRevealScene := preload("res://scenes/card_reveal.tscn")

var _entitlements: Array = []
var _pending_booster_entitlements: Array = []


func _ready() -> void:
	await _refresh()


func _on_back_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/menu.tscn")


func _set_notice(text: String, is_error: bool) -> void:
	_notification.text = text
	_notification.modulate = Color(1, 0.35, 0.35, 1) if is_error else Color(0.6, 1, 0.6, 1)


## Shows each granted card one at a time (large thumbnail + skip option)
## before the caller continues. No-op if `cards` is empty.
func _show_card_reveal(cards: Array) -> void:
	if cards.is_empty():
		return
	var reveal: Control = CardRevealScene.instantiate()
	add_child(reveal)
	reveal.start(cards)
	await reveal.finished


func _refresh() -> void:
	var res: Dictionary = await Api.get_entitlements()
	if not res.ok:
		_set_notice("Failed to load entitlements: %s" % res.error, true)
		return

	_entitlements = res.data.get("items", [])
	await _render_starter_section()
	_render_booster_section()

	var me: Dictionary = await Api.get_me()
	if me.ok:
		_tolkien_label.text = "Tolkiens: %d" % int(me.data.get("tolkien_balance", 0))


func _find_starter_entitlement() -> Variant:
	for e in _entitlements:
		if e.get("product_type") == "starter_deck":
			return e
	return null


func _clear_deck_option_buttons() -> void:
	for child in _deck_options_box.get_children():
		child.queue_free()


func _render_starter_section() -> void:
	var starter_ent = _find_starter_entitlement()

	if starter_ent == null:
		_starter_status_label.text = "No starter deck entitlement on this account."
		_clear_deck_option_buttons()
		return

	if starter_ent.get("status") != "active":
		_starter_status_label.text = "Starter deck: already claimed."
		_clear_deck_option_buttons()
		return

	_starter_status_label.text = "Choose your starter deck:"
	await _load_deck_options(int(starter_ent.get("set_number", 1)), starter_ent.get("id", ""))


func _load_deck_options(set_number: int, entitlement_id: String) -> void:
	var res: Dictionary = await Api.get_starter_deck_options(set_number)
	_clear_deck_option_buttons()

	if not res.ok:
		_starter_status_label.text = "Failed to load deck options: %s" % res.error
		return

	var items: Array = res.data.get("items", [])
	if items.is_empty():
		# Can legitimately happen if this entitlement's set has no curated
		# starter decks available yet (e.g. a set was activated then
		# deactivated again before content was ready) -- show a clear status
		# instead of leaving a blank list under "Choose your starter deck:".
		_starter_status_label.text = "No starter deck options are available for Set %d yet." % set_number
		return

	for opt in items:
		var btn := Button.new()
		btn.text = "%s (%d cards)" % [opt.get("name", ""), int(opt.get("card_count", 0))]
		btn.custom_minimum_size = Vector2(420, 44)
		btn.pressed.connect(_on_deck_option_pressed.bind(entitlement_id, opt.get("deck_key", "")))
		_deck_options_box.add_child(btn)


func _on_deck_option_pressed(entitlement_id: String, deck_key: String) -> void:
	for child in _deck_options_box.get_children():
		child.disabled = true

	_set_notice("Claiming starter deck...", false)
	var res: Dictionary = await Api.claim_entitlement(entitlement_id, deck_key)
	if not res.ok:
		_set_notice("Failed to claim starter deck: %s" % res.error, true)
		await _refresh()
		return

	var card_count: int = res.data.get("cards_granted", []).size()
	await _show_card_reveal(res.data.get("cards_granted", []))
	_set_notice("Granted %s (%d cards)!" % [res.data.get("deck_name", ""), card_count], false)
	await _refresh()


func _render_booster_section() -> void:
	_pending_booster_entitlements.clear()
	for e in _entitlements:
		if e.get("product_type") == "booster_pack" and e.get("status") == "active":
			_pending_booster_entitlements.append(e)

	if _pending_booster_entitlements.is_empty():
		_booster_status_label.text = "No booster packs available to open."
		_open_boosters_btn.disabled = true
	else:
		_booster_status_label.text = "%d booster pack(s) available to open." % _pending_booster_entitlements.size()
		_open_boosters_btn.disabled = false


func _on_open_boosters_pressed() -> void:
	_open_boosters_btn.disabled = true
	var pack_count: int = _pending_booster_entitlements.size()
	var all_cards_granted: Array = []
	var opened_count: int = 0
	var last_error: String = ""

	for e in _pending_booster_entitlements:
		var res: Dictionary = await Api.claim_entitlement(e.get("id", ""))
		if res.ok:
			opened_count += 1
			all_cards_granted.append_array(res.data.get("cards_granted", []))
		else:
			last_error = res.error

	await _show_card_reveal(all_cards_granted)

	# Don't let per-claim failures be silently overwritten by a
	# success-looking summary -- a claim can legitimately fail (e.g. the
	# entitlement's set was deactivated after it was granted but before it
	# was claimed), and the player needs to see why they got fewer cards
	# than expected.
	if opened_count < pack_count:
		_set_notice(
			"Opened %d/%d pack(s), granted %d cards. Some packs failed: %s" % [
				opened_count, pack_count, all_cards_granted.size(), last_error,
			],
			true,
		)
	else:
		_set_notice("Opened %d pack(s), granted %d cards!" % [pack_count, all_cards_granted.size()], false)
	await _refresh()
