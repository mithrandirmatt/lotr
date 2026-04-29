extends Control


func _on_new_game_pressed() -> void:
	pass  # Phase 3 -- will load the game scene


func _on_deck_builder_pressed() -> void:
	pass  # Phase 2 -- will load the deck builder scene


func _on_settings_pressed() -> void:
	pass  # Phase 8 -- will load the settings scene


func _on_quit_pressed() -> void:
	get_tree().quit()
