extends Control

## Full-screen "open a pack" reveal overlay (see New Game LOT-018 flow).
## Instantiated and added as a child by new_game.gd after claiming an
## entitlement; shows each granted card one at a time with a large
## thumbnail (falls back to a rarity-tinted placeholder card face when the
## catalog has no `image_url` yet) and lets the player skip ahead.
##
## Card dicts are the raw GrantedCardSummary JSON from the claim response:
## { card_id, name, rarity, is_foil, image_url }.

signal finished

const RARITY_COLORS := {
	"common": Color(0.75, 0.75, 0.75),
	"uncommon": Color(0.3, 0.8, 0.4),
	"rare": Color(0.35, 0.55, 1.0),
	"epic": Color(0.7, 0.35, 0.9),
	"legendary": Color(1.0, 0.7, 0.2),
	"mythic": Color(1.0, 0.3, 0.3),
}

@onready var _progress_label: Label = $CenterBox/ProgressLabel
@onready var _rarity_bg: ColorRect = $CenterBox/CardPanel/CardPanelBox/ThumbnailArea/RarityBg
@onready var _thumbnail: TextureRect = $CenterBox/CardPanel/CardPanelBox/ThumbnailArea/Thumbnail
@onready var _placeholder_label: Label = $CenterBox/CardPanel/CardPanelBox/ThumbnailArea/PlaceholderLabel
@onready var _name_label: Label = $CenterBox/CardPanel/CardPanelBox/NameLabel
@onready var _rarity_label: Label = $CenterBox/CardPanel/CardPanelBox/RarityRow/RarityLabel
@onready var _foil_label: Label = $CenterBox/CardPanel/CardPanelBox/RarityRow/FoilLabel
@onready var _next_btn: Button = $CenterBox/ButtonRow/NextBtn
@onready var _skip_btn: Button = $CenterBox/ButtonRow/SkipBtn

var _cards: Array = []
var _index: int = 0
var _load_token: int = 0


## Begins the reveal sequence for `cards` (a list of GrantedCardSummary
## dicts). Emits `finished` (and frees itself) once the player has stepped
## through every card or pressed "Skip All".
func start(cards: Array) -> void:
	_cards = cards
	_index = 0
	if _cards.is_empty():
		_finish()
		return
	_skip_btn.visible = _cards.size() > 1
	_show_current()


func _show_current() -> void:
	var card: Dictionary = _cards[_index]
	var rarity: String = str(card.get("rarity", "common"))
	var rarity_color: Color = RARITY_COLORS.get(rarity, Color(0.6, 0.6, 0.6))

	_progress_label.text = "Card %d of %d" % [_index + 1, _cards.size()]
	_name_label.text = str(card.get("name", "Unknown Card"))
	_rarity_label.text = rarity.capitalize()
	_rarity_label.modulate = rarity_color
	_foil_label.visible = bool(card.get("is_foil", false))
	_next_btn.text = "Done" if _index == _cards.size() - 1 else "Next"

	_rarity_bg.color = Color(rarity_color.r, rarity_color.g, rarity_color.b, 0.25)
	_placeholder_label.text = str(card.get("name", "?"))
	_placeholder_label.visible = true
	_thumbnail.texture = null

	var image_url: String = str(card.get("image_url", ""))
	if image_url != "":
		_load_thumbnail(image_url)


func _load_thumbnail(url: String) -> void:
	_load_token += 1
	var my_token := _load_token

	var http := HTTPRequest.new()
	add_child(http)
	var err := http.request(url)
	if err != OK:
		http.queue_free()
		return

	var response: Array = await http.request_completed
	http.queue_free()

	# The player may have advanced (or skipped) while this download was in
	# flight; don't apply a stale image to whatever card is showing now.
	if my_token != _load_token:
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

	_thumbnail.texture = ImageTexture.create_from_image(image)
	_placeholder_label.visible = false


func _on_next_pressed() -> void:
	_index += 1
	if _index >= _cards.size():
		_finish()
	else:
		_show_current()


func _on_skip_pressed() -> void:
	_finish()


func _finish() -> void:
	finished.emit()
	queue_free()
