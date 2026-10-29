extends ItemList

## Small ItemList subclass adding drag-and-drop support between two lists
## (used by the deck editor's "In Deck" / "Available" pools). Each row's
## metadata (set via set_item_metadata) must be a Dictionary containing at
## least a "card_id" key; on a successful drop the `card_dropped` signal is
## emitted with that payload plus a "from_list" key naming the source list.

signal card_dropped(payload: Dictionary)

## Identifies this list to drop targets/handlers (e.g. "selected", "available").
## Set by the owning screen right after instancing/`_ready()`.
var list_id: String = ""


func _get_drag_data(at_position: Vector2) -> Variant:
	var idx := get_item_at_position(at_position, true)
	if idx < 0:
		return null
	var raw: Variant = get_item_metadata(idx)
	if typeof(raw) != TYPE_DICTIONARY:
		return null

	var payload: Dictionary = (raw as Dictionary).duplicate()
	payload["from_list"] = list_id

	var preview := Label.new()
	preview.text = get_item_text(idx)
	set_drag_preview(preview)

	select(idx)
	item_selected.emit(idx)
	return payload


func _can_drop_data(_at_position: Vector2, data: Variant) -> bool:
	return typeof(data) == TYPE_DICTIONARY and data.has("card_id") and data.get("from_list", "") != list_id


func _drop_data(_at_position: Vector2, data: Variant) -> void:
	card_dropped.emit(data)
