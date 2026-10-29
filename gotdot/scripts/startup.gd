extends Control

## Splash screen. After the brief title display, tries to restore a
## "remember me" session (LOT-007) before falling back to the login screen.


func _on_timer_timeout() -> void:
	var res: Dictionary = await Api.try_auto_login()
	if res.ok:
		_go_to_post_login()
	else:
		get_tree().change_scene_to_file("res://scenes/login.tscn")


## Mirrors login.gd's `_go_to_post_login()`: 2FA-enabled accounts go straight
## to the menu; accounts without 2FA yet must complete mandatory setup first.
func _go_to_post_login() -> void:
	if Api.current_user.get("is_2fa_enabled", false):
		get_tree().change_scene_to_file("res://scenes/menu.tscn")
	else:
		get_tree().change_scene_to_file("res://scenes/two_factor_setup.tscn")
