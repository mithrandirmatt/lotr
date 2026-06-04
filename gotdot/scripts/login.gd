extends Control

var current_page: int = 0  # 0 = Welcome, 1 = Sign In, 2 = Register
var user_data: Dictionary = {}

# Page transitions
const PAGE_WELCOME = 0
const PAGE_SIGN_IN = 1
const PAGE_REGISTER = 2

func _ready() -> void:
	# Auto-transition after 0.5 seconds for demo purposes
	# In production, this would be triggered by user interaction
	get_node_or_null("Timer").start()

func _on_timer_timeout() -> void:
	# For demo: auto-advance through pages
	if current_page == PAGE_WELCOME:
		current_page = PAGE_SIGN_IN
		_show_sign_in()
		get_node_or_null("Timer").start()
	elif current_page == PAGE_SIGN_IN:
		# In production: validate credentials and either login or show register
		current_page = PAGE_REGISTER
		_show_register()
		get_node_or_null("Timer").start()
	else:
		# In production: after registration, show success and transition to main menu
		print("Login complete - would transition to main menu")
		get_tree().change_scene_to_file("res://scenes/menu.tscn")

# Page display methods
func _show_welcome() -> void:
	$WelcomeBox.visible = true
	$SignInBox.visible = false
	$RegisterBox.visible = false
	$Notification.text = ""

func _show_sign_in() -> void:
	$WelcomeBox.visible = false
	$SignInBox.visible = true
	$RegisterBox.visible = false
	$Notification.text = ""

func _show_register() -> void:
	$WelcomeBox.visible = false
	$SignInBox.visible = false
	$RegisterBox.visible = true
	$Notification.text = ""

# Navigation methods
func _go_to_welcome() -> void:
	current_page = PAGE_WELCOME
	_show_welcome()

func _go_to_sign_in() -> void:
	current_page = PAGE_SIGN_IN
	_show_sign_in()

func _go_to_register() -> void:
	current_page = PAGE_REGISTER
	_show_register()

# Sign In button
func _on_sign_in_pressed() -> void:
	var email = $SignInBox/SignInForm/EmailInput.text.strip_edges()

	if email.is_empty():
		_show_notification("Please enter your email", true)
		return

	# In production: validate against server/database
	# For demo: auto-advance to register
	_show_notification("Signing in... (demo mode)", false)
	get_tree().create_timer(0.5).timeout.connect(_go_to_register)
	get_tree().create_timer(0.5).timeout.connect(_on_timer_timeout)

# Register button
func _on_register_pressed() -> void:
	var name = $RegisterBox/RegisterForm/NameInput.text.strip_edges()
	var email = $RegisterBox/RegisterForm/EmailInput2.text.strip_edges()
	var password = $RegisterBox/RegisterForm/PasswordInput.text

	if name.is_empty() or email.is_empty() or password.is_empty():
		_show_notification("Please fill in all fields", true)
		return

	# In production: send to server for registration
	# For demo: auto-advance to sign in
	_show_notification("Creating account... (demo mode)", false)
	get_tree().create_timer(0.5).timeout.connect(_go_to_sign_in)
	get_tree().create_timer(0.5).timeout.connect(_on_timer_timeout)

# Back buttons
func _on_back_to_welcome_pressed() -> void:
	_go_to_welcome()

func _on_back_to_welcome_2_pressed() -> void:
	_go_to_welcome()

# Notification helper
func _show_notification(message: String, is_error: bool = false) -> void:
	var notif = $Notification
	notif.text = message
	notif.theme_override_colors/font_color = Color(1, 0.3, 0.3, 1) if is_error else Color(0.3, 1, 0.3, 1)
	notif.visible = true