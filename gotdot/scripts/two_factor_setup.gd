extends Control

## Mandatory 2FA setup screen (LOT-007). Shown right after a user's first
## successful login when their account doesn't have 2FA enabled yet.
## Displays a QR code + manual-entry secret from POST /auth/2fa/setup, then
## confirms with POST /auth/2fa/enable and shows the one-time recovery codes.

@onready var _setup_box: VBoxContainer = $CanvasLayer/SetupBox
@onready var _recovery_box: VBoxContainer = $CanvasLayer/RecoveryBox

@onready var _qr_image: TextureRect = $CanvasLayer/SetupBox/QrImage
@onready var _secret_value: LineEdit = $CanvasLayer/SetupBox/SecretRow/SecretValue
@onready var _code_input: LineEdit = $CanvasLayer/SetupBox/CodeInput
@onready var _enable_btn: Button = $CanvasLayer/SetupBox/EnableBtn
@onready var _status_label: Label = $CanvasLayer/SetupBox/StatusLabel

@onready var _recovery_codes_text: TextEdit = $CanvasLayer/RecoveryBox/RecoveryCodesText


func _ready() -> void:
	_setup_box.visible = true
	_recovery_box.visible = false
	_load_setup()


func _load_setup() -> void:
	_status_label.text = "Loading QR code..."
	_status_label.modulate = Color(0.8, 0.8, 0.8, 1)

	var res: Dictionary = await Api.setup_2fa()
	if not res.ok:
		_status_label.text = "Failed to load 2FA setup: %s" % res.error
		_status_label.modulate = Color(1, 0.35, 0.35, 1)
		return

	_status_label.text = ""
	_secret_value.text = res.data.get("secret", "")

	var png_bytes: PackedByteArray = Marshalls.base64_to_raw(res.data.get("qr_code_png_base64", ""))
	var image := Image.new()
	if image.load_png_from_buffer(png_bytes) == OK:
		_qr_image.texture = ImageTexture.create_from_image(image)


func _on_enable_btn_pressed() -> void:
	var code := _code_input.text.strip_edges()
	if code.length() != 6:
		_status_label.text = "Enter the 6-digit code from your authenticator app"
		_status_label.modulate = Color(1, 0.35, 0.35, 1)
		return

	_enable_btn.disabled = true
	_status_label.text = "Verifying..."
	_status_label.modulate = Color(0.8, 0.8, 0.8, 1)

	var res: Dictionary = await Api.enable_2fa(code)

	_enable_btn.disabled = false

	if not res.ok:
		_status_label.text = res.error if res.error != "" else "Invalid authentication code"
		_status_label.modulate = Color(1, 0.35, 0.35, 1)
		return

	var codes: Array = res.data.get("recovery_codes", [])
	_recovery_codes_text.text = "\n".join(codes)
	_setup_box.visible = false
	_recovery_box.visible = true


func _on_continue_btn_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/menu.tscn")
