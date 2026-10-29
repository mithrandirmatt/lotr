extends Control

## Deck editor screen (second screen of the two-screen deck builder flow).
##
## Edits the deck whose id is handed off via `Api.selected_deck_id` (set by
## deck_builder.gd before navigating here). Shows two card pools -- the
## cards already "In Deck" and the cards still "Available" (owned but not
## assigned to ANY deck) -- plus rarity/card-type/culture/set filter
## checkboxes and a preview panel for the currently highlighted card. Desktop
## interactions:
##   - single click on a card: shows it in the preview panel
##   - double click on a card: adds/removes it (moves between pools)
##   - drag and drop a card onto the other pool: adds/removes it
##
## Talks to the backend through the `Api` autoload (res://scripts/api_client.gd).

const RARITY_COLORS := {
	"common": Color(0.75, 0.75, 0.75),
	"uncommon": Color(0.3, 0.8, 0.4),
	"rare": Color(0.35, 0.55, 1.0),
	"epic": Color(0.7, 0.35, 0.9),
	"legendary": Color(1.0, 0.7, 0.2),
	"mythic": Color(1.0, 0.3, 0.3),
}
const RARITIES := ["common", "uncommon", "rare", "epic", "legendary", "mythic"]

# Real `card_type`/`culture` values found in the imported catalog (see
# `Card.attributes` via `migrate_import_card_catalog.py`). The LOT-025 spec's
# wishlist terms "burdens"/"signet"/"weapon" aren't distinct `card_type`
# values in the actual data -- "signet" is a per-card numeric/string field and
# "Weapon" is a `subtypes` entry on some Possession/Artifact cards, not a
# top-level card_type -- so those are intentionally not separate filters here.
const CARD_TYPES := [
	"Ally", "Artifact", "Companion", "Condition", "Event", "Follower",
	"Map", "Minion", "Possession", "Site", "The One Ring",
]
const CULTURES := [
	"Dunland", "Dwarven", "Elven", "Esgaroth", "Gandalf", "Gollum", "Gondor",
	"Gundabad", "Isengard", "Men", "Mirkwood", "Moria", "Orc", "Raider",
	"Ringwraith", "Rohan", "Sauron", "Shire", "Site", "Smaug", "Spider",
	"The One Ring", "Troll", "Uruk-hai",
]

@onready var _notification: Label = $CanvasLayer/Notification
@onready var _deck_name_label: Label = $CanvasLayer/TitleLabel
@onready var _legality_label: Label = $CanvasLayer/MainRow/CenterColumn/LegalityLabel

@onready var _selected_label: Label = $CanvasLayer/MainRow/CenterColumn/PoolsRow/SelectedPanel/SelectedLabel
@onready var _selected_list: ItemList = $CanvasLayer/MainRow/CenterColumn/PoolsRow/SelectedPanel/SelectedList

@onready var _available_label: Label = $CanvasLayer/MainRow/CenterColumn/PoolsRow/AvailablePanel/AvailableLabel
@onready var _available_list: ItemList = $CanvasLayer/MainRow/CenterColumn/PoolsRow/AvailablePanel/AvailableList

@onready var _filters_box: VBoxContainer = $CanvasLayer/MainRow/FiltersPanel/FiltersScroll/FiltersBox

@onready var _preview_rarity_bg: ColorRect = $CanvasLayer/MainRow/PreviewPanel/PreviewBox/ThumbnailArea/RarityBg
@onready var _preview_thumbnail: TextureRect = $CanvasLayer/MainRow/PreviewPanel/PreviewBox/ThumbnailArea/Thumbnail
@onready var _preview_placeholder: Label = $CanvasLayer/MainRow/PreviewPanel/PreviewBox/ThumbnailArea/PlaceholderLabel
@onready var _preview_name: Label = $CanvasLayer/MainRow/PreviewPanel/PreviewBox/NameLabel
@onready var _preview_meta: Label = $CanvasLayer/MainRow/PreviewPanel/PreviewBox/MetaLabel
@onready var _preview_description: Label = $CanvasLayer/MainRow/PreviewPanel/PreviewBox/DescriptionLabel

var _deck_id: String = ""
var _deck_cards: Array = []       # raw DeckCardEntry dicts: {card_id, quantity, card}
var _available_cards: Array = []  # raw OwnedCardAvailability dicts: {card, owned_quantity, assigned_quantity, available_quantity}

# Filtered/displayed rows, index-aligned with the ItemList contents.
var _selected_rows: Array = []
var _available_rows: Array = []

var _active_rarities: Dictionary = {}    # rarity -> bool
var _active_card_types: Dictionary = {}  # card_type -> bool
var _active_cultures: Dictionary = {}    # culture -> bool
var _active_sets: Dictionary = {}        # set_number (int) -> bool
var _set_names: Dictionary = {}          # set_number (int) -> display name
var _set_section: VBoxContainer = null   # rebuilt in place as new sets are discovered
var _preview_load_token: int = 0


func _ready() -> void:
	_deck_id = Api.selected_deck_id
	for r in RARITIES:
		_active_rarities[r] = true
	for t in CARD_TYPES:
		_active_card_types[t] = true
	for c in CULTURES:
		_active_cultures[c] = true
	_build_filters()

	_selected_list.list_id = "selected"
	_available_list.list_id = "available"

	if _deck_id.is_empty():
		_set_notice("No deck selected.", true)
		return
	await _fetch_set_names()
	await _load_all()


func _on_back_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/deck_builder.tscn")


func _set_notice(text: String, is_error: bool = false) -> void:
	_notification.text = text
	_notification.modulate = Color(1, 0.45, 0.45) if is_error else Color(0.8, 0.8, 0.8)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

func _build_filters() -> void:
	for child in _filters_box.get_children():
		child.queue_free()
	_add_filter_section("Rarity", RARITIES, _on_rarity_toggled)
	_add_filter_section("Card Type", CARD_TYPES, _on_card_type_toggled)
	_add_filter_section("Culture", CULTURES, _on_culture_toggled)
	# Sets aren't a fixed enum like the above -- populated once the deck's and
	# available pool's cards are loaded, since that's what tells us which
	# set_number values actually appear (see _update_set_filter()).
	_set_section = VBoxContainer.new()
	_filters_box.add_child(_set_section)


func _add_filter_section(title: String, values: Array, on_toggled: Callable) -> void:
	var header := Label.new()
	header.text = title
	header.add_theme_font_size_override("font_size", 15)
	header.add_theme_color_override("font_color", Color(1, 0.85, 0.35, 1))
	_filters_box.add_child(header)
	for value in values:
		var cb := CheckBox.new()
		cb.text = value.capitalize()
		cb.button_pressed = true
		cb.toggled.connect(on_toggled.bind(value))
		_filters_box.add_child(cb)


func _on_rarity_toggled(is_on: bool, rarity: String) -> void:
	_active_rarities[rarity] = is_on
	_render_selected_list()
	_render_available_list()


func _on_card_type_toggled(is_on: bool, card_type: String) -> void:
	_active_card_types[card_type] = is_on
	_render_selected_list()
	_render_available_list()


func _on_culture_toggled(is_on: bool, culture: String) -> void:
	_active_cultures[culture] = is_on
	_render_selected_list()
	_render_available_list()


func _on_set_toggled(is_on: bool, set_number: int) -> void:
	_active_sets[set_number] = is_on
	_render_selected_list()
	_render_available_list()


## Fetches set display names (best-effort -- only covers currently-active
## sets; cards from a since-deactivated set still show as "Set N").
func _fetch_set_names() -> void:
	var res := await Api.get_active_sets()
	if not res.ok:
		return
	for s in res.data.get("active_sets", []):
		_set_names[int(s.get("set_number", 0))] = str(s.get("name", ""))


## Discovers which set_number values actually appear across the deck's and
## available pool's cards, adds any newly-seen ones to `_active_sets`
## (default checked), and rebuilds the "Set" checkbox section in place.
func _update_set_filter() -> void:
	var seen := {}
	for entry in _deck_cards:
		_note_card_set(entry.get("card", {}), seen)
	for row in _available_cards:
		_note_card_set(row.get("card", {}), seen)
	for set_number in seen.keys():
		if not _active_sets.has(set_number):
			_active_sets[set_number] = true

	for child in _set_section.get_children():
		child.queue_free()
	if _active_sets.is_empty():
		return
	var header := Label.new()
	header.text = "Set"
	header.add_theme_font_size_override("font_size", 15)
	header.add_theme_color_override("font_color", Color(1, 0.85, 0.35, 1))
	_set_section.add_child(header)
	var set_numbers := _active_sets.keys()
	set_numbers.sort()
	for set_number in set_numbers:
		var cb := CheckBox.new()
		cb.text = _set_names.get(set_number, "Set %d" % set_number)
		cb.button_pressed = _active_sets[set_number]
		cb.toggled.connect(_on_set_toggled.bind(set_number))
		_set_section.add_child(cb)


func _note_card_set(card: Dictionary, seen: Dictionary) -> void:
	var set_number = card.get("set_number")
	if set_number != null:
		seen[int(set_number)] = true


func _passes_filters(card: Dictionary) -> bool:
	var rarity: String = str(card.get("rarity", "common"))
	if not _active_rarities.get(rarity, true):
		return false
	var stats: Dictionary = card.get("stats", {})
	if stats == null:
		stats = {}
	# Card type/culture are only present on cards that actually have them
	# (e.g. The One Ring has no culture) -- an empty/unknown value always
	# passes rather than being filtered out by an unrelated checkbox group.
	var card_type: String = str(stats.get("card_type", ""))
	if not card_type.is_empty() and not _active_card_types.get(card_type, true):
		return false
	var culture: String = str(stats.get("culture", ""))
	if not culture.is_empty() and not _active_cultures.get(culture, true):
		return false
	var set_number = card.get("set_number")
	if set_number != null and not _active_sets.get(int(set_number), true):
		return false
	return true


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

func _load_all() -> void:
	_set_notice("Loading...")
	await _load_deck()
	await _load_available_cards()
	_update_set_filter()
	_set_notice("Ready.")


func _load_deck() -> void:
	var res := await Api.get_deck(_deck_id)
	if not res.ok:
		_set_notice("Failed to load deck: %s" % res.error, true)
		return
	_deck_name_label.text = "Editing: %s" % res.data.get("name", "?")
	_deck_cards = res.data.get("cards", [])
	_render_selected_list()
	await _refresh_legality()


func _load_available_cards() -> void:
	var res := await Api.get_available_cards()
	if not res.ok:
		_set_notice("Failed to load available cards: %s" % res.error, true)
		return
	_available_cards = res.data.get("items", [])
	_render_available_list()


func _refresh_legality() -> void:
	var res := await Api.get_deck_legality(_deck_id)
	if not res.ok:
		_legality_label.text = "Legality: unknown (%s)" % res.error
		_legality_label.modulate = Color(0.8, 0.8, 0.8)
		return

	var data: Dictionary = res.data
	var counts := "Draw deck: %d | Free Peoples: %d | Shadow: %d | Sites: %d" % [
		data.get("draw_deck_size", 0), data.get("free_peoples_count", 0),
		data.get("shadow_count", 0), data.get("site_count", 0),
	]
	if data.get("is_legal", false):
		_legality_label.text = "LEGAL\n%s" % counts
		_legality_label.modulate = Color(0.4, 1, 0.4)
	else:
		var issues: Array = data.get("issues", [])
		_legality_label.text = "NOT LEGAL\n%s\n- %s" % [counts, "\n- ".join(issues)]
		_legality_label.modulate = Color(1, 0.65, 0.35)


# ---------------------------------------------------------------------------
# Rendering the two pools
# ---------------------------------------------------------------------------

func _render_selected_list() -> void:
	_selected_list.clear()
	_selected_rows.clear()
	for entry in _deck_cards:
		var card: Dictionary = entry.get("card", {})
		if not _passes_filters(card):
			continue
		var rarity: String = str(card.get("rarity", "common"))
		var card_id: String = entry.get("card_id", "")
		var qty: int = entry.get("quantity", 0)
		var idx := _selected_list.add_item("%s x%d  [%s]" % [card.get("name", card_id), qty, rarity.capitalize()])
		_selected_list.set_item_metadata(idx, {"card_id": card_id, "card": card})
		_selected_rows.append({"card_id": card_id, "card": card})
	_selected_label.text = "In Deck (%d)" % _deck_cards.size()


func _render_available_list() -> void:
	_available_list.clear()
	_available_rows.clear()
	for row in _available_cards:
		var available_qty: int = row.get("available_quantity", 0)
		if available_qty <= 0:
			continue
		var card: Dictionary = row.get("card", {})
		if not _passes_filters(card):
			continue
		var rarity: String = str(card.get("rarity", "common"))
		var card_id: String = card.get("id", "")
		var idx := _available_list.add_item(
			"%s (%d available)  [%s]" % [card.get("name", card_id), available_qty, rarity.capitalize()]
		)
		_available_list.set_item_metadata(idx, {"card_id": card_id, "card": card})
		_available_rows.append({"card_id": card_id, "card": card})
	_available_label.text = "Available"


# ---------------------------------------------------------------------------
# Interactions: single click (preview), double click (add/remove), drag-drop
# ---------------------------------------------------------------------------

func _on_selected_item_selected(index: int) -> void:
	if index >= 0 and index < _selected_rows.size():
		_show_preview(_selected_rows[index].get("card", {}))


func _on_available_item_selected(index: int) -> void:
	if index >= 0 and index < _available_rows.size():
		_show_preview(_available_rows[index].get("card", {}))


func _on_selected_item_activated(index: int) -> void:
	if index >= 0 and index < _selected_rows.size():
		await _remove_card(_selected_rows[index].get("card_id", ""))


func _on_available_item_activated(index: int) -> void:
	if index >= 0 and index < _available_rows.size():
		await _add_card(_available_rows[index].get("card_id", ""))


func _on_card_dropped(payload: Dictionary) -> void:
	var card_id: String = payload.get("card_id", "")
	var from_list: String = payload.get("from_list", "")
	if from_list == "available":
		await _add_card(card_id)
	elif from_list == "selected":
		await _remove_card(card_id)


func _add_card(card_id: String) -> void:
	if card_id.is_empty():
		return
	var res := await Api.add_card_to_deck(_deck_id, card_id, 1)
	if not res.ok:
		_set_notice("Could not add card: %s" % res.error, true)
		return
	await _load_all()
	_set_notice("Card added to deck.")


func _remove_card(card_id: String) -> void:
	if card_id.is_empty():
		return
	var res := await Api.remove_card_from_deck(_deck_id, card_id, 1)
	if not res.ok:
		_set_notice("Could not remove card: %s" % res.error, true)
		return
	await _load_all()
	_set_notice("Card removed from deck.")


# ---------------------------------------------------------------------------
# Preview panel
# ---------------------------------------------------------------------------

func _show_preview(card: Dictionary) -> void:
	var rarity: String = str(card.get("rarity", "common"))
	var rarity_color: Color = RARITY_COLORS.get(rarity, Color(0.6, 0.6, 0.6))

	_preview_name.text = str(card.get("name", "?"))
	_preview_meta.text = "Cost: %s | Rarity: %s" % [str(card.get("cost", "-")), rarity.capitalize()]
	_preview_meta.modulate = rarity_color
	_preview_description.text = str(card.get("description", ""))

	_preview_rarity_bg.color = Color(rarity_color.r, rarity_color.g, rarity_color.b, 0.25)
	_preview_placeholder.text = str(card.get("name", "?"))
	_preview_placeholder.visible = true
	_preview_thumbnail.texture = null

	var image_url: String = str(card.get("image_url", ""))
	if image_url != "":
		_load_preview_thumbnail(image_url)


func _load_preview_thumbnail(url: String) -> void:
	_preview_load_token += 1
	var my_token := _preview_load_token

	var http := HTTPRequest.new()
	add_child(http)
	var err := http.request(url)
	if err != OK:
		http.queue_free()
		return

	var response: Array = await http.request_completed
	http.queue_free()

	if my_token != _preview_load_token:
		return

	var result: int = response[0]
	var response_code: int = response[1]
	var body: PackedByteArray = response[3]
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		return

	var image := Image.new()
	var load_err := image.load_png_from_buffer(body)
	if load_err != OK:
		load_err = image.load_jpg_from_buffer(body)
	if load_err != OK:
		return

	_preview_thumbnail.texture = ImageTexture.create_from_image(image)
	_preview_placeholder.visible = false
