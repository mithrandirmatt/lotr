extends Control


func _on_timer_timeout() -> void:
	# Transition to login screen instead of old menu
	get_tree().change_scene_to_file("res://scenes/login.tscn")
