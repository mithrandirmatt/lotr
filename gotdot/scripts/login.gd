extends Control

## Intro / Sign In / Register flow for LOT-007.
##
## Talks to the backend through the `Api` autoload (res://scripts/api_client.gd).
## Sign-in accounts with 2FA enabled are challenged for a 6-digit code before
## reaching the main menu; accounts without 2FA yet are redirected to the
## mandatory setup screen (res://scenes/two_factor_setup.tscn) right after
## their first successful login.

const PAGE_WELCOME := 0
const PAGE_SIGN_IN := 1
const PAGE_REGISTER := 2
const PAGE_SIGN_IN_MFA := 3

const COLOR_ERROR := Color(1, 0.35, 0.35, 1)
const COLOR_OK := Color(0.4, 1, 0.4, 1)
const COLOR_MUTED := Color(0.7, 0.7, 0.7, 1)

var current_page: int = PAGE_WELCOME
var _email_regex := RegEx.new()

@onready var _welcome_box: VBoxContainer = $CanvasLayer/WelcomeBox
@onready var _sign_in_box: VBoxContainer = $CanvasLayer/SignInBox
@onready var _mfa_box: VBoxContainer = $CanvasLayer/MfaBox
@onready var _register_box: VBoxContainer = $CanvasLayer/RegisterBox
@onready var _notification: Label = $CanvasLayer/Notification

@onready var _sign_in_email: LineEdit = $CanvasLayer/SignInBox/SignInForm/EmailInput
@onready var _sign_in_password: LineEdit = $CanvasLayer/SignInBox/SignInForm/PasswordInput
@onready var _sign_in_btn: Button = $CanvasLayer/SignInBox/SignInForm/SignInBtn

@onready var _mfa_code: LineEdit = $CanvasLayer/MfaBox/MfaForm/MfaCodeInput
@onready var _mfa_submit_btn: Button = $CanvasLayer/MfaBox/MfaForm/MfaSubmitBtn

@onready var _reg_name: LineEdit = $CanvasLayer/RegisterBox/RegisterForm/NameInput
@onready var _reg_name_status: Label = $CanvasLayer/RegisterBox/RegisterForm/NameStatus
@onready var _reg_email: LineEdit = $CanvasLayer/RegisterBox/RegisterForm/EmailInput2
@onready var _reg_email_status: Label = $CanvasLayer/RegisterBox/RegisterForm/EmailStatus
@onready var _reg_password: LineEdit = $CanvasLayer/RegisterBox/RegisterForm/PasswordInput2
@onready var _reg_confirm_password: LineEdit = $CanvasLayer/RegisterBox/RegisterForm/ConfirmPasswordInput
@onready var _reg_confirm_status: Label = $CanvasLayer/RegisterBox/RegisterForm/ConfirmPasswordStatus
@onready var _reg_btn: Button = $CanvasLayer/RegisterBox/RegisterForm/RegisterBtn

@onready var _email_check_timer: Timer = $EmailCheckTimer
@onready var _name_check_timer: Timer = $NameCheckTimer


func _ready() -> void:
	_email_regex.compile("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
	_show_welcome()


# ---------------------------------------------------------------------------
# Page navigation
# ---------------------------------------------------------------------------

func _show_welcome() -> void:
	current_page = PAGE_WELCOME
	_welcome_box.visible = true
	_sign_in_box.visible = false
	_mfa_box.visible = false
	_register_box.visible = false
	_notification.text = ""


func _show_sign_in() -> void:
	current_page = PAGE_SIGN_IN
	_welcome_box.visible = false
	_sign_in_box.visible = true
	_mfa_box.visible = false
	_register_box.visible = false
	_notification.text = ""


func _show_sign_in_mfa() -> void:
	current_page = PAGE_SIGN_IN_MFA
	_welcome_box.visible = false
	_sign_in_box.visible = false
	_mfa_box.visible = true
	_register_box.visible = false
	_notification.text = ""
	_mfa_code.text = ""
	_mfa_code.grab_focus()


func _show_register() -> void:
	current_page = PAGE_REGISTER
	_welcome_box.visible = false
	_sign_in_box.visible = false
	_mfa_box.visible = false
	_register_box.visible = true
	_notification.text = ""


func _go_to_welcome() -> void:
	_show_welcome()


func _go_to_sign_in() -> void:
	_show_sign_in()


func _go_to_register() -> void:
	_show_register()


func _on_mfa_back_pressed() -> void:
	Api.mfa_token = ""
	_show_sign_in()


# ---------------------------------------------------------------------------
# Sign In
# ---------------------------------------------------------------------------

func _on_sign_in_pressed() -> void:
	var email := _sign_in_email.text.strip_edges()
	var password := _sign_in_password.text

	if email.is_empty() or password.is_empty():
		_show_notification("Please enter your email and password", true)
		return

	_sign_in_btn.disabled = true
	_show_notification("Signing in...", false)

	var res: Dictionary = await Api.login(email, password)

	_sign_in_btn.disabled = false

	if not res.ok:
		_show_notification(res.error if res.error != "" else "Invalid credentials", true)
		return

	if res.data.get("requires_2fa", false):
		_show_sign_in_mfa()
		return

	_show_notification("", false)
	_go_to_post_login()


func _on_mfa_submit_pressed() -> void:
	var code := _mfa_code.text.strip_edges()
	if code.length() != 6:
		_show_notification("Enter the 6-digit code from your authenticator app", true)
		return

	_mfa_submit_btn.disabled = true
	_show_notification("Verifying...", false)

	var res: Dictionary = await Api.verify_2fa_login(code)

	_mfa_submit_btn.disabled = false

	if not res.ok:
		_show_notification(res.error if res.error != "" else "Invalid authentication code", true)
		return

	_go_to_post_login()


## Accounts always have 2FA enabled by the time they reach this point unless
## it's their very first login after registering (LOT-007: setup is mandatory).
func _go_to_post_login() -> void:
	if Api.current_user.get("is_2fa_enabled", false):
		get_tree().change_scene_to_file("res://scenes/menu.tscn")
	else:
		get_tree().change_scene_to_file("res://scenes/two_factor_setup.tscn")


# ---------------------------------------------------------------------------
# Register — real-time validation
# ---------------------------------------------------------------------------

func _on_register_name_changed(new_text: String) -> void:
	var name := new_text.strip_edges()
	if name.is_empty():
		_reg_name_status.text = ""
		return
	if " " in name:
		_reg_name_status.text = "Please enter a valid unique name (no spaces)."
		_reg_name_status.modulate = COLOR_ERROR
		return
	_reg_name_status.text = "Checking..."
	_reg_name_status.modulate = COLOR_MUTED
	_name_check_timer.start()


func _on_name_check_timer_timeout() -> void:
	var name := _reg_name.text.strip_edges()
	if name.is_empty() or " " in name:
		return
	var res: Dictionary = await Api.check_unique_name(name)
	if not res.ok:
		_reg_name_status.text = ""
		return
	if res.data.get("exists", false):
		_reg_name_status.text = "This unique name is already taken."
		_reg_name_status.modulate = COLOR_ERROR
	else:
		_reg_name_status.text = "Unique name is available!"
		_reg_name_status.modulate = COLOR_OK


func _on_register_email_changed(new_text: String) -> void:
	var email := new_text.strip_edges()
	if email.is_empty():
		_reg_email_status.text = ""
		return
	if not _email_regex.search(email):
		_reg_email_status.text = "Please enter a valid email."
		_reg_email_status.modulate = COLOR_ERROR
		return
	_reg_email_status.text = "Checking..."
	_reg_email_status.modulate = COLOR_MUTED
	_email_check_timer.start()


func _on_email_check_timer_timeout() -> void:
	var email := _reg_email.text.strip_edges()
	if email.is_empty() or not _email_regex.search(email):
		return
	var res: Dictionary = await Api.check_email(email)
	if not res.ok:
		_reg_email_status.text = ""
		return
	if res.data.get("exists", false):
		_reg_email_status.text = "This email is already registered."
		_reg_email_status.modulate = COLOR_ERROR
	else:
		_reg_email_status.text = "Email is available!"
		_reg_email_status.modulate = COLOR_OK


func _on_register_pressed() -> void:
	var name := _reg_name.text.strip_edges()
	var email := _reg_email.text.strip_edges()
	var password := _reg_password.text
	var confirm := _reg_confirm_password.text

	if name.is_empty() or email.is_empty() or password.is_empty() or confirm.is_empty():
		_show_notification("Please fill in all fields", true)
		return

	if " " in name:
		_show_notification("Please enter a valid unique name (no spaces).", true)
		return

	if not _email_regex.search(email):
		_show_notification("Please enter a valid email.", true)
		return

	if password.length() < 8:
		_show_notification("Password must be at least 8 characters.", true)
		return

	if password != confirm:
		_reg_confirm_status.text = "Passwords do not match."
		_reg_confirm_status.modulate = COLOR_ERROR
		_show_notification("Passwords do not match.", true)
		return
	_reg_confirm_status.text = ""

	_reg_btn.disabled = true
	_show_notification("Registering...", false)

	var res: Dictionary = await Api.register(email, name, password, confirm)

	_reg_btn.disabled = false

	if not res.ok:
		_show_notification(res.error if res.error != "" else "Registration failed", true)
		return

	_show_notification("Registration successful. Please log in.", false)
	_sign_in_email.text = email
	_sign_in_password.text = ""
	get_tree().create_timer(2.0).timeout.connect(_show_sign_in)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

func _show_notification(message: String, is_error: bool = false) -> void:
	_notification.text = message
	_notification.modulate = COLOR_ERROR if is_error else COLOR_OK