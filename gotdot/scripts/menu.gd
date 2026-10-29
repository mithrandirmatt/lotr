extends Control


func _on_new_game_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/new_game.tscn")


func _on_deck_builder_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/deck_builder.tscn")


func _on_settings_pressed() -> void:
	pass  # Phase 8 -- will load the settings scene


func _on_quit_pressed() -> void:
	get_tree().quit()
