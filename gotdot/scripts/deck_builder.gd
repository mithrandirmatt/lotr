extends Control

## Deck selection screen (first screen of the two-screen deck builder flow).
##
## Lists the current user's decks and lets them create a new one; picking a
## deck (double-click or the Edit button) hands the deck id off to `Api` and
## navigates to the deck-editor screen where cards are actually added/removed.
##
## Talks to the backend through the `Api` autoload (res://scripts/api_client.gd).

@onready var _notification: Label = $CanvasLayer/Notification
@onready var _decks_list: ItemList = $CanvasLayer/MainRow/DecksPanel/DecksList
@onready var _new_deck_name: LineEdit = $CanvasLayer/MainRow/DecksPanel/NewDeckRow/NewDeckNameInput
@onready var _new_deck_btn: Button = $CanvasLayer/MainRow/DecksPanel/NewDeckRow/NewDeckBtn
@onready var _edit_deck_btn: Button = $CanvasLayer/MainRow/DecksPanel/EditDeckBtn

var _decks: Array = []


func _ready() -> void:
	_set_notice("Loading...")
	await _load_decks()


func _on_back_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/menu.tscn")


func _set_notice(text: String, is_error: bool = false) -> void:
	_notification.text = text
	_notification.modulate = Color(1, 0.45, 0.45) if is_error else Color(0.8, 0.8, 0.8)


func _load_decks() -> void:
	var res := await Api.get_decks()
	if not res.ok:
		_set_notice("Failed to load decks: %s" % res.error, true)
		return
	_decks = res.data.get("items", [])
	_decks_list.clear()
	for deck in _decks:
		_decks_list.add_item(
			"%s (%s) - %d cards" % [deck.get("name", "?"), deck.get("format", "?"), deck.get("total_cards", 0)]
		)
	_edit_deck_btn.disabled = _decks.is_empty()
	_set_notice("%d deck%s." % [_decks.size(), "" if _decks.size() == 1 else "s"])


func _on_new_deck_pressed() -> void:
	var deck_name := _new_deck_name.text.strip_edges()
	if deck_name.is_empty():
		_set_notice("Enter a deck name first.", true)
		return
	var res := await Api.create_deck(deck_name, "Open")
	if not res.ok:
		_set_notice("Could not create deck: %s" % res.error, true)
		return
	_new_deck_name.text = ""
	await _load_decks()
	_set_notice("Deck '%s' created." % deck_name)


func _on_deck_selected(_index: int) -> void:
	_edit_deck_btn.disabled = _decks_list.get_selected_items().is_empty()


func _on_deck_item_activated(index: int) -> void:
	_open_editor(index)


func _on_edit_deck_pressed() -> void:
	var selected := _decks_list.get_selected_items()
	if selected.is_empty():
		_set_notice("Select a deck to edit first.", true)
		return
	_open_editor(selected[0])


func _open_editor(index: int) -> void:
	if index < 0 or index >= _decks.size():
		return
	Api.selected_deck_id = _decks[index].get("id", "")
	get_tree().change_scene_to_file("res://scenes/deck_editor.tscn")
